
from sbs_utils.agent import Agent, get_story_id
from sbs_utils.procedural.execution import get_variable, task_schedule, jump, AWAIT
from sbs_utils.procedural.query import to_object, to_id
from sbs_utils.procedural.links import link, unlink
from sbs_utils.procedural.brain import brain_clear
from sbs_utils.procedural.timers import delay_sim


from sbs_utils.helpers import FrameContext

from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value
from sbs_utils.vec import Vec3


import sbs
from sbs_utils.procedural.routes import  RouteDamageObject
from sbs_utils.procedural.query import to_object_list
from sbs_utils.procedural.roles import role


# Per-captain truce (Open Universe, Epic D): a fleet ignores captains who have
# earned high enough reputation with the fleet's clan. Reads the per-ship
# "reputation" inventory directly, so it's a no-op where there's no reputation
# (non-universe missions) and needs no cross-addon import.
TRUCE_THRESHOLD = 60


def fleet_reputation_standing(ship_id, clan):
    """Overall favorability of a captain (ship) with a clan (sum of axes)."""
    reps = get_inventory_value(ship_id, "reputation", None) or {}
    cm = reps.get(clan)
    return sum(cm.values()) if isinstance(cm, dict) else 0


def truced_ships(clan):
    """Player-ship ids at truce with a clan (standing >= threshold); excluded
    from that clan's fleet targeting. Empty when there's no reputation."""
    out = set()
    if not clan:
        return out
    for s in to_object_list(role("__player__")):
        if fleet_reputation_standing(s.id, clan) >= TRUCE_THRESHOLD:
            out.add(s.id)
    return out

class Fleet(Agent):
    #--------------------------------------------------------------------------------------
    def __init__(self, position, side):
        super().__init__()

        self.id = get_story_id()
        self.add()
        self.side = side
        self.position = Vec3(position.x, position.y, position.z) #Vec3(0,0,0)
        self.destination = Vec3(0,0,0)
        self.anger_dict = {}
        self.add_role("fleet")
        self.name = f"fleet {self.id&0x0000FFFFFFFFFFFF}"

        if side is not None:
            if isinstance(side, str):
                roles = side.split(",")
            else:
                roles = side
            side = roles[0].strip()
            if side != "#":
#                obj.side = side
                self.side = side
#            self.update_comms_id()
            for role in roles:
                self.add_role(role)
        
        
        #task_schedule(self.tick)


    @property
    def was_populated(self):
        """True once this fleet has held at least one member ship.

        A Fleet is an Agent, not a space object, so nothing reaps it when its last
        member dies - that is what `fleet_purge_empty` is for. But "zero live members"
        alone cannot tell an emptied fleet from one that is still being FILLED
        (`prefab_fleet_empty` spawns a fleet and the mission adds ships afterwards,
        possibly frames later).

        The link COLLECTION is created by the first `link(fleet,"ship_list",...)` and
        survives being emptied, so its presence - not its size - is the discriminator.
        This is the one place that reaches into `links.collections` for it.
        """
        return "ship_list" in self.links.collections

    def get_best_anger(self):
        sim = FrameContext.sim
        if sim is None:
            return
        best_id = None
        best_anger = 0
        new_anger = {}
        for e in self.anger_dict:
            if 0 == e:
                continue
            if to_object(e) is None:
                continue

            end_time = self.anger_dict[e]
            time_now = sim.time_tick_counter
            that_anger = (end_time - time_now) # Not needed// 30 # 30 Sim FPS
            that_anger = max(0, that_anger)
            if best_anger < that_anger:
                best_anger = that_anger
                best_id = e
            # Keep it in angry if still angry
            if that_anger >0:
                new_anger[e] = end_time
        self.anger_dict = new_anger

        return best_id

    #--------------------------------------------------------------------------------------
    def ship_takes_damage(self, my_ship_id, attacker_id):
        if 0 == attacker_id:
            print(f"0 == attacker_id:     WTF!")
            return

        self.make_enraged_by(attacker_id) 
        #self.anger_dict[attacker_id] = 100  # how long I will be angry

    def get_heat_for(self, an_id_or_obj):
        sim = FrameContext.sim
        if sim is None:
            return
        id = to_id(an_id_or_obj)
        end_time =  self.anger_dict.get(id, None)
        if end_time is None:
            return 0
        time_now = sim.time_tick_counter
        left = max(end_time-time_now, 0)
        left //= 30
        return left
    
    def make_enraged_by(self, an_id_or_obj):
        id = to_id(an_id_or_obj)
        if 0 == id or id is None:
            return
        sim = FrameContext.sim
        if sim is None:
            return
        # 30 Per Second and 120 seconds
        end_time = sim.time_tick_counter + 30 *120

        self.anger_dict[id] = end_time  # how long I will be angry

#--------------------------------------------------------------------------------------
@RouteDamageObject 
def ship_takes_damage():#event):
    event = get_variable("EVENT")
#    print(f"fleet  ship_takes_damage {event.tag} {event.sub_tag}")

    # parent is 0 for ship as origin, ship for ordinance 
    attacker_id = event.parent_id
    if 0 == attacker_id:
        attacker_id = event.origin_id

    if 0 == attacker_id:
         # Probably a mine
        return
    victim_id = event.selected_id
    my_fleet = to_object(get_inventory_value(victim_id, "my_fleet_id"))
    if None != my_fleet:
        my_fleet.ship_takes_damage(victim_id, attacker_id)

#--------------------------------------------------------------------------------------
def fleet_spawn(position, side):
    return Fleet(position, side)


def fleet_add(fleet_id, npc_id):
    fleet_id = to_id(fleet_id)
    fleet_obj = to_object(fleet_id)
    

    npc_id = to_id(npc_id)
    npc_obj = to_object(npc_id)

    if fleet_obj is None or npc_obj is None:
        return
    
    # Make sure it is on the proper side
    npc_obj.side = fleet_obj.side
    
    set_inventory_value(npc_id, "my_fleet_id", fleet_id)
    link(fleet_id,"ship_list", npc_id)


def fleet_remove(fleet_id, npc_id):
    fleet_id = to_id(fleet_id)
    npc_id = to_id(npc_id)

    set_inventory_value(npc_id, "my_fleet_id", None)
    unlink(fleet_id,"ship_list", npc_id)
    


#--------------------------------------------------------------------------------------
# Reaping empty fleets
#
# A Fleet is a class-level Agent (Agent.all), NOT a space object, so `delete_object`
# never touches one and `object_exists(fleet_id)` is False for a perfectly live fleet.
# Nothing garbage-collected an orphaned Fleet, so a long mission that spawns waves - or
# the per-ship "ship_fleet" the GM makes, or the fleet-of-one every basic enemy prefab
# builds - accumulated dead Fleet agents forever: a slow leak plus stale entries in
# every `role("fleet")` walk and in the brain registry (each fleet carries a brain that
# went on ticking with nothing to command).
#
# A fleet carrying the "fleet_persist" role is never reaped - the opt-out for a mission
# that deliberately keeps an empty fleet handle around to refill later.
#--------------------------------------------------------------------------------------

FLEET_PERSIST_ROLE = "fleet_persist"

# How often the sweep runs, in sim seconds. A fleet outliving its last member by a few
# seconds costs nothing; the point is that it does not outlive it forever.
FLEET_REAP_INTERVAL = 5


def fleet_live_members(fleet_id_or_obj):
    """Live member ids of a fleet, culling dead ones from the ship_list link.

    `delete_object` purges a dead object as a link OWNER but leaves incoming links, so
    a destroyed member stays in the raw ship_list as a dangling id. This resolves each
    one and drops the ids that no longer resolve, which is the same cull
    `ai_fleet_init_blackboard` does - done here too so a fleet with no brain (or one
    whose brain never runs again) still gets tidied.
    """
    fleet = to_object(to_id(fleet_id_or_obj))
    if fleet is None:
        return []
    live = []
    for member_id in fleet.get_link_list("ship_list"):
        if to_object(member_id) is None:
            fleet.remove_link("ship_list", member_id)
        else:
            live.append(member_id)
    return live


def fleet_destroy(fleet_id_or_obj):
    """Remove a Fleet agent from the story. Returns True if one was removed.

    Safe to call on a fleet that still has live members - they are released (their
    `my_fleet_id` back-reference cleared) rather than left pointing at a dead id.
    """
    fleet_id = to_id(fleet_id_or_obj)
    fleet = to_object(fleet_id)
    if not isinstance(fleet, Fleet):
        return False

    for member_id in fleet.get_link_list("ship_list"):
        if get_inventory_value(member_id, "my_fleet_id", None) == fleet_id:
            set_inventory_value(member_id, "my_fleet_id", None)
    fleet.remove_link_all("ship_list")
    fleet.anger_dict = {}
    # Stop the behavior tree before the agent goes. Agent.remove_id purges the
    # class-level `__BRAIN__` inventory mirror anyway (that mirror IS the brain tick
    # loop's registry), so this is belt-and-braces - and it drops the Brain tree's own
    # reference to the agent.
    brain_clear(fleet_id)
    Agent.remove_id(fleet_id)
    return True


def fleet_purge_empty():
    """Reap every fleet whose last member is gone. Returns how many were removed.

    Skips a fleet that has never held a member (still being filled) and one wearing
    the `fleet_persist` role.
    """
    reaped = 0
    for fleet_id in list(role("fleet")):
        fleet = to_object(fleet_id)
        if not isinstance(fleet, Fleet):
            continue
        if fleet.has_role(FLEET_PERSIST_ROLE):
            continue
        if not fleet.was_populated:
            continue
        if len(fleet_live_members(fleet_id)) > 0:
            continue
        if fleet_destroy(fleet_id):
            reaped += 1
    return reaped


def fleet_reap_tick():
    """The periodic empty-fleet sweep. Started by `fleet_reap_start`."""
    fleet_purge_empty()
    yield AWAIT(delay_sim(seconds=FLEET_REAP_INTERVAL))
    yield jump(fleet_reap_tick)


def fleet_reap_start():
    """Start the sweep, once per mission.

    The latch lives on `Agent.SHARED`, not in a module global: the engine forks a fresh
    process per mission but the dev runner REUSES the interpreter, so a module-level
    "already started" flag would survive into the next mission and the sweep would
    never run again from run 2 onward. Agent.SHARED is rebuilt per mission, so the
    latch resets with it - while a second `game_started` emit still cannot double-schedule.
    """
    if get_inventory_value(Agent.SHARED, "fleet_reaper_started", False):
        return
    set_inventory_value(Agent.SHARED, "fleet_reaper_started", True)
    task_schedule(fleet_reap_tick)




"""

Fleet

contains a list of ships that belong to it
position
destination
path to target
anger management



Tick()
get average center of all my ships
that's my point
move my point in the direction I want to go (perhaps 1000m?)
tell all my ships to go to that point (and go throttle 1.0)

make decisions about where the fleet goes
	naviagitn ghte existing path
	refreshing a stale path

reduce all heats by 1

anger:
ship takes damage from emeny:
	set enemy heat to 100

if best heat > 0
	tell all ships to move to and attack heat target


"""
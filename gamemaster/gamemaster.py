from sbs_utils.procedural.gui.section import gui_sub_section
from sbs_utils.procedural.gui.ship import gui_ship
from sbs_utils.procedural.ship_data import get_ship_data, get_ship_data_for
from sbs_utils.procedural.gui.button import gui_button
from sbs_utils.procedural.gui.icon import gui_icon
from sbs_utils.procedural.inventory import  get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import get_science_selection, get_weapons_selection, to_object, get_comms_selection, get_data_set_value
from sbs_utils.procedural.links import linked_to
from sbs_utils.helpers import FrameContext, gui_text_escape
from sbs_utils.vec import Vec3
from sbs_utils import yaml
from sbs_utils.procedural.gui.listbox import gui_list_box
from sbs_utils.procedural.gui.dropdown import gui_drop_down
from sbs_utils.procedural.comms import comms_broadcast
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.gui import gui_task_for_client, gui_region
from sbs_utils.procedural.execution import gui_sub_task_schedule, labels_get_type, gui_get_variable


def gamemaster_show_nav_area(ORIGIN_ID, pos, size_delta, text, selection_type, color):
    x = pos.x
    y = pos.z

    sim = FrameContext.context.sim

    size = get_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_SIZE", 5000)
    size += size_delta
    size = max(min(50000, size), 2000)
    if size_delta == 0:
        size = 5000

    set_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_SIZE", size)
    set_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_x", x)
    set_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_y", y)
    
    nav_id = get_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_SELECT_ID", None)
    if nav_id:
        sim.delete_navpoint_by_id(nav_id)

    nav_id = sim.add_navarea(x-size, y-size,x+size, y-size,x-size, y+size,x+size, y+size, text, color)
    nav = sim.get_navpoint_by_id(nav_id)

    nav.visibleToShip = ORIGIN_ID
    set_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_SELECT_ID", nav_id)

def gamemaster_get_pos(ORIGIN_ID, selection_type):
    x = get_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_x", 0)
    y = get_inventory_value(ORIGIN_ID, f"GAMEMASTER_{selection_type}_y", 0)

    _other = 0
    if selection_type == "rmb":
        _other = get_weapons_selection(ORIGIN_ID)
    elif selection_type == "lmb":
        _other = get_science_selection(ORIGIN_ID)

    if _other==0:
        return Vec3(x,0,y)
    _obj = to_object(_other)
    if _obj is None:
        return Vec3(x,0,y)
    return _obj.pos
    

    

from sbs_utils.procedural.gui import gui_row, gui_text, gui_text_area

def old_property_lb(item):
    gui_row("row-height: 1.2em;padding:13px;")
    gui_text(f"$text:{item['label']};justify: left;")
    gui_row("row-height: 1.5em;padding:13px;")
    gui_c = item['control']

    
    gui_c = FrameContext.task.get_variable(gui_c)
    if gui_c:
        gui_c(item['props'], var=item['var'])

from sbs_utils.procedural.gui import gui_panel_widget_show, gui_panel_widget_hide, gui_slider, gui_blank, gui_message_label

def gamemaster_panel_camera_show(cid, left,top,width, height):
    gui_panel_widget_show(cid, left,top,width, height, "3dview")
    # For 3D view
    gui_blank()

    dl = gui_slider("low: 0; high:300.0;", style="col-width:20px;", var="dolly")
    gui_row("row-height: 20px;")
    ob = gui_slider("low: 0.0; high:360.0;", var="orbit")
    gui_message_label(dl, "gamemaster_move_camera")
    gui_message_label(ob, "gamemaster_move_camera")


def gamemaster_panel_camera_hide(cid, left,top,width, height):
    gui_panel_widget_hide(cid, left,top,width, height, "3dview")


def gamemaster_panel_instructions(cid, left,top,width, height):
    task = FrameContext.task
    if task is None:
        return
    gm_text = task.get_variable("GAMEMASTER_INSTRUCTIONS", "Game Master instructions^set the variable GAMEMASTER_INSTRUCTIONS to see it here.")

    gui_text_area(gm_text)

def ship_details_show(cid, left, top, width, height):
    """
    Show the ship details stuff
    """
    task = FrameContext.task
    if task is None:
        return
    gm = role("gamemaster")
    l = len(gm)
    gui_text_area(f"GMs: {l}")
    region = gui_region()
    gui_sub_task_schedule("gm_build_info", {"ui_element": region})
    return
    if gm is None:
        gui_text_area("GM is None")
        return
    sel = get_inventory_value(gm, "gamemaster_prev_selection", None)
    
    ship = to_object(sel)
    if not ship:
        gui_text_area(f"Ship is None^{sel}")
        return
    items = []
    # gui_blank()
    ship_name = gui_text_area(f"$text:{ship.name}")
    # items.append(ship_name)
    
    # side = gui_drop_down("$text:{ship.side};list:TSN,CIV,Kralien,Torgoth,Arvonian,Skaraan,Ximni,Pirate")
    # items.append(side)

    # gui_list_box(items,"")
def ship_details_tick(info_panel):
#     """
#     Show the ship details stuff
#     """
    task = gui_task_for_client(info_panel.client_id)
    if task is None:
        gui_text_area("Task is none")
        return 1
    gm = info_panel.client_id
    # return
    if gm is None:
        gui_text_area("GM is None")
        return 1
    sel = get_inventory_value(gm, "gamemaster_prev_selection", None)
    
    ship = to_object(sel)
    if not ship:
        gui_text_area(f"Ship is None^{sel}")
        return 1
    items = []
    # gui_blank()
    ship_name = gui_text_area(f"$text:{ship.name}")
    return 1

def gm_get_menu_items_tree(parent_menu=None):
    """
    Get the menu items for the gamemaster
    Args:
        parent_menu: The path of the parent_menu, e.g. `"gm_menu/terrain"`
    """
    if parent_menu is None:
        labels = labels_get_type("gm_menu")
    else:
        labels = labels_get_type(parent_menu)
    items = {}
    for label in labels:
        path = label.get_inventory_value("type")
        if parent_menu is not None:
            items[path] = label
            continue
        tree = path.split("/")
        if len(tree) == 2:
            items[path] = label
    return items

def gm_show_menu_contents(cid, left, top, width, height, widget):
    """
    Build the menu for the gamemaster
    """
    newItems = []
    items = gm_get_menu_items_tree()
    for k, v in items.items():
        data = {"name": k, "on_press": "GM_Menu_Select", "args": {"label": v.name}}
        newItems.append(data)
    return newItems

def gm_build_menu_icons(item):
    """Builds the icons to press to go to each menu"""
    icon = item.get_inventory_value("icon_index")
    icon_color = item.get_inventory_value("icon_color")
    if icon_color is None:
        icon_color = "#14749aa8"
    if icon is not None:
        GAMEMASTER_CONSOLE_ICON_SIZE = gui_get_variable("GAMEMASTER_CONSOLE_ICON_SIZE")
        gui_row(f"row-height: {GAMEMASTER_CONSOLE_ICON_SIZE}px;")
        gui_icon(f"icon_index: {icon};color: {icon_color};")
    else:
        gui_text(item.get_inventory_value("type"))
        print("Icon is None")

def sort_menu_labels(a,b):
    print("Sorting")
    if a is None and b is not None:
        return False
    if b is None and a is not None:
        return True
    if a is None and b is None:
        return True
    a1 = a.get_inventory_value("priority")
    b1 = b.get_inventory_value("priority")
    return a1 > b1


def filter_ship_data_generically(text):
    """
    Filters ship data for any usage of the provided text. Includes name, origin, side, roles, and description.
    Args:
        text (str): The text for which to search.
    
    Returns:
        list: The list of ship keys
    
    """
    data = get_ship_data()
    if data is None:
        return []

    if text is None:
        text = ""
    needle = str(text).strip().lower()

    # Blank search returns all known ship keys in load order.
    if needle == "":
        return [ship for ship in data.get("#ship-list", []) if ship.get("key")]

    results = []
    for ship in data.get("#ship-list", []):
        key = ship.get("key", "")
        name = ship.get("name", "")
        origin = ship.get("origin", "")
        side = ship.get("side", "")
        roles = ship.get("roles", "")
        long_desc = ship.get("long_desc", "")
        short_desc = ship.get("desc", "")

        # Join all the text into one string
        haystack = "|".join([
            str(key),
            str(name),
            str(origin),
            str(side),
            str(roles),
            str(long_desc),
            str(short_desc),
        ]).lower()

        if needle in haystack:
            results.append(ship)

    return results

def gm_ship_spawn_select_template(item):
    gui_row("padding:13px;")
    # print(f"{item}")
    art = item.get("art_id", "")
    # gui_ship(f"{art}", style="col-width:50px;padding:0,0,5px,0;")
    dat = get_ship_data_for(art)
    desc = "A fine ship"
    roles = "No roles found"
    if dat is not None:
        desc = dat.get("name")
        origin = dat.get("origin")
        if origin is not None:
            desc = f"{origin} - {desc}"
        else:
            desc = f"{desc}"
        roles = dat.get("roles",roles)

    with gui_sub_section():
        # gui_row("row-height:1em;")
        # # Escape the user-entered ship name so a ':' or ';' in it can't inject
        # # style properties or break the justify/font that follow (issue #569).
        # ship_label = gui_text_escape(f"{item.name} - {item.side}")
        # gui_text(f"$text:{ship_label};justify: left;font:gui-3;")
        gui_row("row-height:1em;")
        gui_text(f"$text:{desc};justify: left;font:gui-2;color:#bbb;")
        gui_row("row-height: 1em;")
        gui_text(f"$text: {roles};")


_SYSTEM_INDEX_NAMES = {
    0: "Weapons",
    1: "Engines",
    2: "Sensors",
    3: "Shields",
}

_ELITE_ABILITY_LABELS = {
    "elite_low_vis": "LowVis",
    "elite_main_scn_invis": "MainScanInvis",
    "elite_drone_launcher": "DroneLauncher",
    "elite_anti_mine": "AntiMine",
    "elite_anti_torpedo": "AntiTorpedo",
}


def _gm_get_ship_data_fields(obj):
    ship_key = getattr(obj, "ship_data_key", None) or getattr(obj, "art_id", "")
    sd = get_ship_data_for(ship_key) if ship_key else None
    if not isinstance(sd, dict):
        sd = {}

    ship_type = sd.get("name") or ship_key or obj.name
    origin = sd.get("origin") or getattr(obj, "origin", "") or "unknown"
    side = sd.get("side") or getattr(obj, "side", "") or "unknown"
    return ship_type, origin, side, sd


def _gm_format_shields(obj_id):
    count = int(get_data_set_value(obj_id, "shield_count", 0) or 0)
    if count <= 0:
        return "none"

    parts = []
    for i in range(count):
        cur = get_data_set_value(obj_id, "shield_val", i)
        mx = get_data_set_value(obj_id, "shield_max_val", i)
        if cur is None:
            cur = 0
        if mx is None:
            mx = 0
        parts.append(f"{i + 1}:{round(float(cur), 1)}/{round(float(mx), 1)}")
    return ", ".join(parts)


def _gm_format_roles(obj):
    try:
        roles = sorted(obj.get_roles())
    except Exception:
        roles = []
    return ", ".join(roles) if roles else "none"


def _gm_format_system_damage(obj_id):
    rows = []
    seen_indices = set()

    for i in range(30):
        label = get_data_set_value(obj_id, "eng_control_label", i)
        if not label:
            continue
        sys_index = int(get_data_set_value(obj_id, "eng_control_type_index", i) or i)
        if sys_index in seen_indices:
            continue
        seen_indices.add(sys_index)

        cur = float(get_data_set_value(obj_id, "system_damage", sys_index) or 0)
        mx = float(get_data_set_value(obj_id, "system_max_damage", sys_index) or 0)
        rows.append(f"{label}: {round(cur, 1)}/{round(mx, 1)}")

    if not rows:
        for idx, name in _SYSTEM_INDEX_NAMES.items():
            mx = float(get_data_set_value(obj_id, "system_max_damage", idx) or 0)
            if mx <= 0:
                continue
            cur = float(get_data_set_value(obj_id, "system_damage", idx) or 0)
            rows.append(f"{name}: {round(cur, 1)}/{round(mx, 1)}")

    return "^".join(rows) if rows else "none"


def _gm_format_npc_hull(obj_id, ship_data):
    base_hull = ship_data.get("hullpoints", None)
    if base_hull is not None:
        base_hull = float(base_hull)

    total_max = 0.0
    total_dmg = 0.0
    for idx in range(4):
        mx = float(get_data_set_value(obj_id, "system_max_damage", idx) or 0)
        cur = float(get_data_set_value(obj_id, "system_damage", idx) or 0)
        total_max += mx
        total_dmg += cur

    if total_max > 0 and base_hull is not None:
        ratio = max(0.0, min(1.0, 1.0 - (total_dmg / total_max)))
        current_hull = round(base_hull * ratio, 2)
        return f"{current_hull}/{base_hull}"

    if base_hull is not None:
        return str(base_hull)

    if total_max > 0:
        return f"{round(max(0.0, total_max - total_dmg), 1)}/{round(total_max, 1)}"

    return "unknown"


def _gm_format_npc_abilities(obj_id, obj):
    abilities = []

    for r in obj.get_roles():
        if r.startswith("elite_"):
            abilities.append(_ELITE_ABILITY_LABELS.get(r, r))

    for key, label in _ELITE_ABILITY_LABELS.items():
        if get_data_set_value(obj_id, key, 0):
            abilities.append(label)

    # Preserve order while removing duplicates.
    seen = set()
    deduped = []
    for a in abilities:
        if a in seen:
            continue
        seen.add(a)
        deduped.append(a)

    return ", ".join(deduped) if deduped else "none"


def _gm_format_player_upgrades(obj_id):
    names = []
    for up_id in linked_to(obj_id, "__UPGRADE__"):
        up = to_object(up_id)
        if up is None:
            continue

        label = getattr(up, "label", None)
        display = None
        if label is not None and hasattr(label, "get_inventory_value"):
            display = label.get_inventory_value("display_name", None)
        if not display and label is not None and hasattr(label, "name"):
            display = label.name
        if not display and label is not None:
            display = str(label)
        if display:
            names.append(display)

    return ", ".join(sorted(names)) if names else "none"


def _gm_format_fleet_info(obj_id):
    fleet_id = get_inventory_value(obj_id, "my_fleet_id", None)
    if not fleet_id:
        return "none", "none"

    fleet_obj = to_object(fleet_id)
    fleet_name = getattr(fleet_obj, "name", None) if fleet_obj is not None else None
    if not fleet_name:
        fleet_name = f"Fleet {fleet_id}"

    members = sorted([sid for sid in linked_to(fleet_id, "ship_list") if sid is not None])
    if not members:
        return fleet_name, "unknown"

    flagship_id = members[0]
    if flagship_id == obj_id:
        flagship_ref = "This ship is the flagship"
    else:
        flagship_obj = to_object(flagship_id)
        flagship_name = getattr(flagship_obj, "name", None) if flagship_obj is not None else None
        if not flagship_name:
            flagship_name = str(flagship_id)
        flagship_ref = f"{flagship_name} ({flagship_id})"

    return fleet_name, flagship_ref


def gm_selected_object_details(gm_id):
    """Build a multi-line details block for the GM-selected object."""
    sel = get_inventory_value(gm_id, "gamemaster_prev_selection", None)
    if not sel:
        return "Selected Object^none"

    obj = to_object(sel)
    if obj is None:
        return f"Selected Object^Missing object id: {sel}"

    ship_type, origin, side, ship_data = _gm_get_ship_data_fields(obj)
    obj_id = obj.id
    lines = [
        f"Selected Object: {obj.name}",
        f"Object ID: {obj_id}",
    ]

    if obj.is_terrain:
        lines.append("Type: Terrain")
        lines.append(f"Terrain type: {ship_type}")
        return "^".join(lines)

    if hasattr(obj, "has_role") and obj.has_role("station"):
        lines.append("Type: Station")
        lines.append(f"Station type: {ship_type}")
        lines.append(f"Station origin: {origin}")
        lines.append(f"Side: {side}")
        lines.append(f"Current shield strength values: {_gm_format_shields(obj_id)}")
        armor = get_data_set_value(obj_id, "armor", 0)
        armor_max = get_data_set_value(obj_id, "armorMax", 0)
        lines.append(f"Current armor: {round(float(armor or 0), 1)}/{round(float(armor_max or 0), 1)}")
        lines.append(f"Current roles: {_gm_format_roles(obj)}")
        return "^".join(lines)

    if obj.is_player or (hasattr(obj, "has_role") and obj.has_role("__player__")):
        lines.append("Type: Player Ship")
        lines.append(f"Ship type: {ship_type}")
        lines.append(f"Ship origin: {origin}")
        lines.append(f"Side: {side}")
        lines.append(f"Current shield strength values: {_gm_format_shields(obj_id)}")
        lines.append("Current damage to each system:")
        lines.append(_gm_format_system_damage(obj_id))
        lines.append(f"Current roles: {_gm_format_roles(obj)}")
        lines.append(f"Available upgrades: {_gm_format_player_upgrades(obj_id)}")
        return "^".join(lines)

    lines.append("Type: NPC Ship")
    lines.append(f"Ship type: {ship_type}")
    lines.append(f"Ship origin: {origin}")
    lines.append(f"Side: {side}")
    fleet_name, flagship_ref = _gm_format_fleet_info(obj_id)
    lines.append(f"Fleet name: {fleet_name}")
    lines.append(f"Flagship reference: {flagship_ref}")
    lines.append(f"Current shield strength values: {_gm_format_shields(obj_id)}")
    lines.append(f"Current hull points: {_gm_format_npc_hull(obj_id, ship_data)}")
    lines.append(f"Current special abilities: {_gm_format_npc_abilities(obj_id, obj)}")
    lines.append(f"Current roles: {_gm_format_roles(obj)}")
    return "^".join(lines)


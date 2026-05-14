from sbs_utils.fs import get_artemis_data_dir_filename
from sbs_utils.procedural.roles import role
import sbs
from sbs_utils.procedural.query import to_id, to_object, to_blob
from sbs_utils.procedural.execution import get_shared_variable, task_cancel, task_schedule, set_shared_variable
from sbs_utils.procedural.inventory import get_inventory_value, set_inventory_value




__build_times = {
    "command": {"build_times": {"Homing": 2, "Nuke": 5, "EMP": 3, "Mine": 2}},
    "civil": {"build_times": {"Homing": 6, "Nuke": 20, "EMP": 10, "Mine": 8 }},
    "industry": {"build_times": {"Homing": 1, "Nuke": 4, "EMP": 2, "Mine": 2 }},
    "science": {"build_times": {"Homing": 6, "Nuke": 20, "EMP": 10, "Mine": 8}},
    "default": {"build_times": {"Homing": 3, "Nuke": 10, "EMP": 5, "Mine": 4}}
}


def get_build_times(id_or_obj):
    build_times = get_shared_variable("build_times", __build_times)
    if build_times is None:
        build_times = __build_times
    
    #   HOMING : 0, NUKE : 1, EMP : 2, MINE : 3
    so = to_object(id_or_obj)
    if so is not None:
        artid = so.art_id
        for k in build_times:
            if k in artid:
                return  build_times[k]["build_times"]

    return build_times["default"]["build_times"]

def get_torp_build_times(key):
    """
    Get the time it takes to build the torpedo with the given key at stations.
    Args:
        key (str): The key of the torpedo type
    Returns:
        dict: A dictionary with station types as the keys (e.g. command) and the time to build as the value.
    """
    torps = role(key) & role("torpedo_definition")
    torp = torps.pop() # Should only be one
    return get_inventory_value(torp, "build_times")

# TODO: instead of using art_id, might be better to use roles? The applicable roles would need added to shipData.yaml
def get_build_time_for(id_or_obj, torp_type):
    times = get_torp_build_times(torp_type)
    so = to_object(id_or_obj)
    if so is not None:
        time = get_inventory_value(so, f"{torp_type}_BUILD_SPEED", 1000)
        return time
    return times["default"]

def get_default_build_speeds(force_update:bool=False):
    """
    Get the defaults. Can force an update if new torp types are added dynamically later in the game
    """
    defaults = get_shared_variable("default_build_speeds")
    if defaults is None or force_update:
        # Only runs once
        torps = role("torpedo_definition")
        ret = {}
        for t in torps:
            key = get_inventory_value(t, "key")
            default = get_inventory_value(t, "build_times")["default"]
            ret[key] = default * 60
        set_shared_variable("default_build_speeds", ret)
        return ret
    return defaults


def build_munition_queue_task(id_or_obj, torp_type):
    build_task = get_inventory_value(id_or_obj, "build_task")
    build_type = get_inventory_value(id_or_obj, "build_type")

    if build_type == torp_type:
        return False

    set_inventory_value(id_or_obj, "build_type", torp_type)
    # if it is running stop it
    if build_task is not None:
        task_cancel(build_task)
    # Start the new work    
    build_time = get_build_time_for(id_or_obj, torp_type)*60
    set_inventory_value(id_or_obj, "build_task", task_schedule("task_station_building", 
        data={"station_id": to_id(id_or_obj), "build_time": build_time, "torpedo_build_type": torp_type}))
    return True


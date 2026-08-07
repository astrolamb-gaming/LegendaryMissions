from sbs_utils.procedural.gui.button import gui_button
from sbs_utils.procedural.gui.icon import gui_icon
from sbs_utils.procedural.inventory import  get_inventory_value, set_inventory_value
from sbs_utils.procedural.query import get_science_selection, get_weapons_selection, to_object, get_comms_selection
from sbs_utils.helpers import FrameContext
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
    if icon is not None:
        print(f"Building icon: {icon}")
        GAMEMASTER_CONSOLE_ICON_SIZE = gui_get_variable("GAMEMASTER_CONSOLE_ICON_SIZE")
        gui_row(f"row-height: {GAMEMASTER_CONSOLE_ICON_SIZE}px;")
        gui_icon(f"icon_index: {icon}; color: #14749aa8;")
    else:
        gui_text(item.get_inventory_value("type"))
        print("Icon is None")

def gm_build_sub_menu_icons(item):
    """Builds sub-menu icons"""
    icon = item.get_inventory_value("icon_index")
    if icon is not None:
        GAMEMASTER_CONSOLE_ICON_SIZE = gui_get_variable("GAMEMASTER_CONSOLE_ICON_SIZE")
        gui_row(f"row-height: {GAMEMASTER_CONSOLE_ICON_SIZE}px;")
        gui_icon(f"icon_index: {icon}; color: #14749aa8;")
    else:
        gui_text(item.get_inventory_value("type"))

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



from sbs_utils.gui import get_client_aspect_ratio
from sbs_utils.helpers import FrameContext
from sbs_utils.mast.parsers import LayoutAreaParser
from sbs_utils.pages.layout import layout as layout
from sbs_utils.pages.layout.bounds import Bounds
from sbs_utils.pages.widgets.layout_listbox import SubPage
from sbs_utils.procedural.gui import gui_row
from sbs_utils.procedural.execution import labels_get_type
from sbs_utils.procedural.inventory import get_inventory_value
from sbs_utils.procedural.query import to_object
from sbs_utils.procedural.roles import role
from sbs_utils.procedural.style import apply_control_styles


def _visible_rows(section, viewport_top, viewport_bottom, edge_tolerance=0.0):
    visible_rows = []
    if section is None or not hasattr(section, "rows"):
        return visible_rows

    for row in section.rows:
        row_bounds = row.bounds
        if row_bounds.bottom <= viewport_top:
            continue
        if row_bounds.top >= viewport_bottom:
            continue
        if row_bounds.top < viewport_top - edge_tolerance:
            continue
        if row_bounds.bottom > viewport_bottom + edge_tolerance:
            continue
        visible_rows.append(row)
    return visible_rows


def _collect_labels_by_filter(label_type):
    if label_type is None:
        return []

    labels = list(labels_get_type(label_type))
    if len(labels) > 0:
        return labels

    if not label_type.startswith("//"):
        labels = list(labels_get_type("//" + label_type))
        if len(labels) > 0:
            return labels

    ret = []
    for label_id in role("__MAST_LABEL__"):
        o = to_object(label_id)
        if o is None:
            continue
        t = o.name if getattr(o, "name", None) is not None else get_inventory_value(label_id, "type")
        if t is None:
            continue
        if label_type in t:
            ret.append(o)
    return ret


def _route_label_render_plan(task, label):
    """Return (include_label, active_cmd_index) for rendering a label preview."""
    if task is None or label is None:
        return (False, 0)

    cmds = getattr(label, "cmds", None)
    if not cmds:
        return (True, 0)

    first_cmd = cmds[0]
    if_code = getattr(first_cmd, "if_code", None)
    cmd_line = getattr(first_cmd, "line", "")

    # Route labels inject a leading "yield fail if ..." command.
    # For preview rendering:
    # - include only when route condition is True
    # - skip the guard command so the UI body can render
    if if_code is not None and isinstance(cmd_line, str) and " entry test " in cmd_line:
        try:
            guard_should_fail = bool(task.eval_code(if_code))
            if guard_should_fail:
                return (False, 0)
            return (True, 1)
        except Exception:
            # If evaluation fails in this context, keep the default behavior.
            return (True, 0)

    return (True, 0)


class _LabelStackSubPage(SubPage):
    """SubPage wrapper that keeps row heights consistent with procedural GUI defaults."""

    def __init__(self, tag_prefix, region_tag, task, client_id) -> None:
        super().__init__(tag_prefix, region_tag, task, client_id)
        self._minimum_row_height = LayoutAreaParser.parse_e2(LayoutAreaParser.lex("1.5em"))

    def add_row(self):
        row = super().add_row()
        row.default_height = self._minimum_row_height
        return row

    def push_sub_section(self, style, layout_item, is_rebuild):
        sub_layout = super().push_sub_section(style, layout_item, is_rebuild)
        if self.pending_row is not None and getattr(self.pending_row, "default_height", None) is None:
            self.pending_row.default_height = self._minimum_row_height
        return sub_layout

    def pop_sub_section(self, add, is_rebuild):
        (parent_layout, parent_row) = self.sub_sections.pop()
        child_layout = self.active_layout

        # Commit the child subsection's working row before attaching the subsection.
        if self.pending_row is not None and len(self.pending_row.columns) > 0:
            child_layout.add(self.pending_row)

        if add:
            if parent_row is None:
                parent_row = layout.Row()
                parent_row.tag = self.get_tag()
                parent_row.default_height = self._minimum_row_height
                parent_layout.add(parent_row)
            elif getattr(parent_row, "default_height", None) is None:
                parent_row.default_height = self._minimum_row_height
            parent_row.add(child_layout)

        self.active_layout = parent_layout
        self.pending_row = parent_row


def gui_label_stack_listbox(
    style="",
    items=None,
    label_type=None,
):
    page = FrameContext.page
    task = FrameContext.task
    if page is None or task is None:
        return None

    if items is None:
        if label_type is None:
            items = []
        else:
            items = _collect_labels_by_filter(label_type)

    original_main_page = task.main.page
    original_frame_page = FrameContext.page
    tag_prefix = page.get_tag()

    combined_section = layout.Layout(tag_prefix + ":combined", None, 0, 0, 100, 100)
    combined_page = _LabelStackSubPage(tag_prefix, getattr(page, "region_tag", ""), task, getattr(page, "client_id", None))
    combined_page.next_slot(0, combined_section)
    task.main.page = combined_page
    FrameContext.page = combined_page

    visible_items = []
    for label in items:
        include_label, active_cmd = _route_label_render_plan(task, label)
        if include_label:
            visible_items.append((label, active_cmd))

    for i, (label, active_cmd) in enumerate(visible_items):
        if i > 0:
            gui_row()
        task.start_sub_task(label, {"STACK_LABEL": label}, defer=False, active_cmd=active_cmd)

    task.main.page = original_main_page
    FrameContext.page = original_frame_page

    widget = LabelStackListbox(tag_prefix, combined_section)
    apply_control_styles(".listbox", style, widget, task)
    page.add_content(widget, None)
    return widget


class LabelStackListbox(layout.Column):
    def __init__(self, tag_prefix, combined_section) -> None:
        super().__init__(0, 0, 33, 44)

        self.tag_prefix = tag_prefix
        self.tag = tag_prefix
        self.local_region_tag = tag_prefix + "$$"
        self.combined_section = combined_section
        self.scroll_offset_pixels = 0.0
        self.max_scroll_pixels = 0.0
        self.client_id = None
        self.minimum_row_height = LayoutAreaParser.parse_e2(LayoutAreaParser.lex("1.5em"))
        self.slider_style = LayoutAreaParser.parse_e2(LayoutAreaParser.lex("1em"))
        self.overscan_pixels = 0.0
        self.overscan_ratio = 0.15
        self.row_step_pixels = 0.0

    def _present(self, event):
        CID = event.client_id
        self.client_id = CID
        SBS = FrameContext.context.sbs

        top = self.bounds.top
        left = self.bounds.left
        right = self.bounds.right
        bottom = self.bounds.bottom

        aspect_ratio = get_client_aspect_ratio(CID)

        slider_width = 0
        if self.combined_section is not None:
            slider_width = LayoutAreaParser.compute(self.slider_style, None, aspect_ratio.x, 20)

        content_right = right - slider_width
        available_height = bottom - top
        self.overscan_pixels = LayoutAreaParser.compute(self.minimum_row_height, None, aspect_ratio.y, 20) * self.overscan_ratio
        self.row_step_pixels = max(1.0, LayoutAreaParser.compute(self.minimum_row_height, None, aspect_ratio.y, 20))

        self.combined_section.set_bounds(Bounds(left, 0, content_right, available_height))
        self.combined_section.calc(CID)
        total_content_height = max(self.combined_section.get_content_bounds(False).height, 0.2)

        max_scroll = max(0.0, total_content_height - available_height)
        self.max_scroll_pixels = max_scroll
        if self.scroll_offset_pixels > max_scroll:
            self.scroll_offset_pixels = max_scroll

        if total_content_height > available_height:
            button_height = slider_width
            if button_height * 2 >= available_height:
                button_height = max(0.0, available_height / 4.0)

            slider_top = self.bounds.top + button_height
            slider_bottom = self.bounds.bottom - button_height

            # Draw the icon for the Scroll Up button.
            SBS.send_gui_icon(
                CID,
                self.local_region_tag,
                f"{self.tag_prefix}iup",
                "icon_index:148;color:#aaa;draw_layer:1000;",
                right - slider_width,
                self.bounds.top,
                right,
                slider_top,
            )
            # Make the click region for the Scroll Up button
            SBS.send_gui_clickregion(
                CID,
                self.local_region_tag,
                f"{self.tag_prefix}up",
                "background_color:#6663",
                right - slider_width,
                self.bounds.top,
                right,
                slider_top,
            )

            # The actual slider.
            SBS.send_gui_slider(
                CID,
                self.local_region_tag,
                f"{self.tag_prefix}cur",
                max_scroll - self.scroll_offset_pixels,
                f"low:0.0; high:{max_scroll}; show_number:no",
                right - slider_width,
                slider_top,
                right,
                slider_bottom,
            )

            # Draw the icon for the Scroll Down button
            SBS.send_gui_icon(
                CID,
                self.local_region_tag,
                f"{self.tag_prefix}idown",
                "icon_index:150;color:#aaa;draw_layer:1000;",
                right - slider_width,
                slider_bottom,
                right,
                self.bounds.bottom,
            )

            # Make the click region for the Scroll Down button.
            SBS.send_gui_clickregion(
                CID,
                self.local_region_tag,
                f"{self.tag_prefix}down",
                "background_color:#6663",
                right - slider_width,
                slider_bottom,
                right,
                self.bounds.bottom,
            )
            

        viewport_top = self.scroll_offset_pixels
        viewport_bottom = min(total_content_height, self.scroll_offset_pixels + available_height + self.overscan_pixels)
        visible_rows = _visible_rows(
            self.combined_section,
            viewport_top,
            viewport_bottom,
            self.overscan_pixels,
        )
        original_rows = self.combined_section.rows
        self.combined_section.rows = visible_rows

        try:
            render_top = top
            render_bottom = bottom
            if len(visible_rows) > 0:
                first_row_top = visible_rows[0].bounds.top
                render_top = top + first_row_top - self.scroll_offset_pixels
                render_bottom = render_top + (viewport_bottom - first_row_top)

            self.combined_section.region_tag = self.local_region_tag
            self.combined_section.set_bounds(Bounds(left, render_top, content_right, render_bottom))
            self.combined_section.calc(CID)
            self.combined_section.present(event)
        finally:
            self.combined_section.rows = original_rows

    def present(self, event):
        CID = event.client_id
        SBS = FrameContext.context.sbs
        SBS.send_gui_sub_region(CID, self.region_tag, self.local_region_tag, "draggable:True;", 0, 0, 100, 100)
        SBS.send_gui_clear(CID, self.local_region_tag)
        super().present(event)
        SBS.send_gui_complete(CID, self.local_region_tag)

    def on_message(self, event):
        self._on_message(event)
        super().on_message(event)

    def _on_message(self, event):
        if self.client_id != event.client_id:
            return
        if not event.sub_tag.startswith(self.tag_prefix):
            return
        if event.sub_tag.endswith("cur"):
            self.on_scroll(event)
        elif event.sub_tag.endswith("up"):
            self._scroll_by_rows(event, -1)
        elif event.sub_tag.endswith("down"):
            self._scroll_by_rows(event, 1)

    def on_scroll(self, event):
        if event.sub_tag == f"{self.tag_prefix}cur":
            self.scroll_offset_pixels = self.max_scroll_pixels - event.sub_float
            self.gui_state = "redraw"
            self.represent(event)

    def _scroll_by_rows(self, event, direction):
        if not self._snap_to_adjacent_row_top(direction):
            return
        if self.scroll_offset_pixels < 0.0:
            self.scroll_offset_pixels = 0.0
        if self.scroll_offset_pixels > self.max_scroll_pixels:
            self.scroll_offset_pixels = self.max_scroll_pixels
        self.gui_state = "redraw"
        self.represent(event)

    def _snap_to_adjacent_row_top(self, direction):
        all_rows = getattr(self.combined_section, "rows", None)
        if not all_rows:
            return False

        # Snap only across non-empty rows.
        rows = [
            row
            for row in all_rows
            if getattr(row, "bounds", None) is not None and len(getattr(row, "columns", [])) > 0
        ]
        if not rows:
            return False

        tops = sorted({row.bounds.top for row in rows})
        if not tops:
            return False

        cur = self.scroll_offset_pixels
        epsilon = 0.01

        # Anchor to the row that currently starts at or above the viewport top.
        anchor = -1
        for i, top in enumerate(tops):
            if top <= cur + epsilon:
                anchor = i
            else:
                break

        if direction > 0:
            # Down: move to the next non-empty row top.
            if anchor < 0:
                self.scroll_offset_pixels = tops[0]
                return True
            if anchor + 1 < len(tops):
                self.scroll_offset_pixels = tops[anchor + 1]
                return True
            self.scroll_offset_pixels = self.max_scroll_pixels
            return True

        # Up: move to the previous non-empty row top.
        if anchor <= 0:
            self.scroll_offset_pixels = 0.0
            return True
        self.scroll_offset_pixels = tops[anchor - 1]
        return True

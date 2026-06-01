from sbs_utils.gui import get_client_aspect_ratio
from sbs_utils.helpers import FrameContext
from sbs_utils.mast.parsers import LayoutAreaParser
from sbs_utils.pages.layout import layout as layout
from sbs_utils.pages.layout.bounds import Bounds
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
    combined_page = _SectionPage(combined_section, tag_prefix, task)
    task.main.page = combined_page
    FrameContext.page = combined_page

    for i, label in enumerate(items):
        if i > 0:
            gui_row()
        task.start_sub_task(label, {"STACK_LABEL": label}, defer=False)

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

        self.combined_section.set_bounds(Bounds(left, 0, content_right, available_height))
        self.combined_section.calc(CID)
        total_content_height = max(self.combined_section.get_content_bounds(False).height, 0.2)

        max_scroll = max(0.0, total_content_height - available_height)
        self.max_scroll_pixels = max_scroll
        if self.scroll_offset_pixels > max_scroll:
            self.scroll_offset_pixels = max_scroll

        if total_content_height > available_height:
            SBS.send_gui_slider(
                CID,
                self.local_region_tag,
                f"{self.tag_prefix}cur",
                max_scroll - self.scroll_offset_pixels,
                f"low:0.0; high:{max_scroll}; show_number:no",
                right - slider_width,
                self.bounds.top,
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

    def on_scroll(self, event):
        if event.sub_tag == f"{self.tag_prefix}cur":
            self.scroll_offset_pixels = self.max_scroll_pixels - event.sub_float
            self.gui_state = "redraw"
            self.represent(event)


class _SectionPage:
    def __init__(self, section, tag_prefix, task):
        self._section = section
        self._tag_counter = 0
        self._tag_prefix = tag_prefix
        self._pending_row = None
        self._minimum_row_height = LayoutAreaParser.parse_e2(LayoutAreaParser.lex("1.5em"))
        self.gui_task = task
        self.region_tag = ""
        self.client_id = None

    def _new_row(self, default_height=None):
        row = layout.Row()
        row.tag = self.get_tag()
        row.default_height = default_height if default_height is not None else self._minimum_row_height
        return row

    def get_tag(self):
        self._tag_counter += 1
        return f"{self._tag_prefix}:lbl:{self._tag_counter}"

    def add_content(self, layout_item, runtime_node):
        if self._pending_row is None:
            default_height = getattr(layout_item, "default_height", None)
            self._pending_row = self._new_row(default_height)
            self._section.add(self._pending_row)
        elif getattr(self._pending_row, "default_height", None) is None:
            default_height = getattr(layout_item, "default_height", None)
            self._pending_row.default_height = default_height if default_height is not None else self._minimum_row_height
        self._pending_row.add(layout_item)

    def add_row(self):
        self._pending_row = self._new_row(self._minimum_row_height)
        self._section.add(self._pending_row)
        return self._pending_row

    def get_pending_row(self):
        return self._pending_row

    def push_sub_section(self, style, layout_item, is_rebuild):
        if layout_item is None:
            tag = self.get_tag()
            layout_item = layout.Layout(tag, None, 0, 0, 100, 90)
            apply_control_styles(".section", style, layout_item, self.gui_task)
            inner_row = layout.Row()
            inner_row.tag = self.get_tag()
            inner_row.default_height = self._minimum_row_height
            layout_item.add(inner_row)
        self._sub_stack = getattr(self, "_sub_stack", [])
        self._sub_stack.append((self._section, self._pending_row))
        self._section = layout_item
        self._pending_row = None
        if len(layout_item.rows) > 0:
            self._pending_row = layout_item.rows.pop()
        return layout_item

    def pop_sub_section(self, add, is_rebuild):
        (parent_sec, parent_row) = self._sub_stack.pop()
        if add:
            if parent_row is None:
                parent_row = self._new_row(getattr(self._section, "default_height", None))
                self._section.add(parent_row)
            elif getattr(parent_row, "default_height", None) is None:
                parent_row.default_height = getattr(self._section, "default_height", None) or self._minimum_row_height
            parent_row.add(self._section)
        self._section = parent_sec
        self._pending_row = parent_row

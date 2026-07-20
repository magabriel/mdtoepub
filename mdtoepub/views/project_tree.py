import gi
from mdtoepub.models.component import Component, ComponentType
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, Pango

from ..models.project import Project
from ..models.component import Component, ComponentType, COMPONENT_TYPE_LABELS
from ..services.file_service import FileService
from ..utils.dialogs import show_info, confirm
from .project_tree_actions import ProjectTreeActions

from ..i18n import _


def _component_icon(comp: Component) -> str:
    mapping = {
        ComponentType.ACKNOWLEDGEMENT: "emblem-people",
        ComponentType.AFTERWORD: "text-x-preview",
        ComponentType.APPENDIX: "emblem-documents",
        ComponentType.AUTHOR: "avatar-default",
        ComponentType.CHAPTER: "text-x-generic",
        ComponentType.CONCLUSION: "text-x-preview",
        ComponentType.COVER: "image-x-generic",
        ComponentType.DEDICATION: "emblem-favorite",
        ComponentType.EDITION: "text-x-preview",
        ComponentType.EPILOGUE: "text-x-preview",
        ComponentType.FOREWORD: "text-x-preview",
        ComponentType.FOOTNOTES: "accessories-dictionary",
        ComponentType.GLOSSARY: "accessories-dictionary",
        ComponentType.INTRODUCTION: "text-x-preview",
        ComponentType.LICENSE: "application-certificate",
        ComponentType.LOF: "x-office-document",
        ComponentType.LOT: "x-office-document",
        ComponentType.PART: "folder",
        ComponentType.PREFACE: "text-x-preview",
        ComponentType.PROLOGUE: "text-x-preview",
        ComponentType.TITLE: "text-x-generic",
        ComponentType.TOC: "x-office-document",
    }
    return mapping.get(comp.type, "text-x-generic")


def _component_label(comp: Component, labels=None) -> str:
    if labels:
        span = labels.get(comp.type.value, COMPONENT_TYPE_LABELS.get(comp.type, comp.type.value))
        return f"{comp.get_display_name(labels)} ({span})"
    span = COMPONENT_TYPE_LABELS.get(comp.type, comp.type.value)
    return f"{comp.get_display_name()} ({span})"


class ProjectTree:
    def __init__(self, app):
        self.app = app
        self._drag_component_ids = []
        self.project_store = None
        self.project_tree = None
        self._actions = ProjectTreeActions(app, self)

    def build(self, left_box):
        browser_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        browser_header.set_margin_top(6)
        browser_header.set_margin_bottom(6)
        browser_header.set_margin_start(6)
        browser_header.set_margin_end(6)
        left_box.pack_start(browser_header, False, False, 0)

        browser_label = Gtk.Label(label=_("Project Navigator"))
        browser_label.set_hexpand(True)
        browser_label.set_xalign(0)
        browser_label.get_style_context().add_class("heading")
        browser_header.pack_start(browser_label, True, True, 0)

        self.project_store = Gtk.TreeStore(str, object)
        self.project_tree = Gtk.TreeView(model=self.project_store)
        self.project_tree.set_headers_visible(False)
        self.project_tree.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        pixbuf_renderer = Gtk.CellRendererPixbuf()
        pixbuf_renderer.set_property("stock-size", Gtk.IconSize.MENU)
        column = Gtk.TreeViewColumn("Icono")
        column.pack_start(pixbuf_renderer, False)

        def icon_data_func(column, cell, model, iter_, data):
            obj = model.get_value(iter_, 1)
            if isinstance(obj, Project):
                icon_name = "folder"
            elif isinstance(obj, Component) and obj.type == ComponentType.PART:
                icon_name = "folder"
            else:
                icon_name = _component_icon(obj)
            theme = Gtk.IconTheme.get_default()
            info = theme.lookup_icon(icon_name, 16, 0)
            if info:
                cell.set_property("icon-name", icon_name)
            else:
                cell.set_property("icon-name", "text-x-generic")

        column.set_cell_data_func(pixbuf_renderer, icon_data_func)

        text_renderer = Gtk.CellRendererText()
        column.pack_start(text_renderer, True)
        column.add_attribute(text_renderer, "text", 0)
        self.project_tree.append_column(column)
        self.project_tree.connect("cursor-changed", self._on_tree_cursor_changed)
        self.project_tree.connect("button-press-event", self._on_tree_button_press)

        targets = [Gtk.TargetEntry.new("MOVE_ROW", Gtk.TargetFlags.SAME_APP, 1)]
        self.project_tree.enable_model_drag_source(Gdk.ModifierType.BUTTON1_MASK, targets, Gdk.DragAction.MOVE)
        self.project_tree.drag_dest_set(Gtk.DestDefaults.ALL, targets, Gdk.DragAction.MOVE)
        self.project_tree.connect("drag-begin", self._on_drag_begin)
        self.project_tree.connect_after("drag-motion", self._on_drag_motion)
        self.project_tree.connect("drag-data-get", self._on_drag_data_get)
        self.project_tree.connect("drag-data-received", self._on_drag_data_received)

        tree_scrolled = Gtk.ScrolledWindow()
        tree_scrolled.set_vexpand(True)
        tree_scrolled.add(self.project_tree)
        left_box.pack_start(tree_scrolled, True, True, 0)

        self.app.project_store = self.project_store
        self.app.project_tree = self.project_tree

        return self.project_tree

    def refresh_project_tree(self):
        self.project_store.clear()
        if not self.app.project:
            return

        labels = self.app.project_manager.resolve_labels()
        project_iter = self.project_store.append(None, [self.app.project.name, self.app.project])
        part_iters = {}

        for comp in self.app.project.get_ordered_components():
            if comp.type == ComponentType.PART:
                part_iters[comp.id] = self.project_store.append(
                    project_iter, [comp.get_display_name(labels), comp]
                )
                continue
            part = self.app.project.get_part(comp.part_id) if comp.part_id else None
            if part and comp.type == ComponentType.CHAPTER:
                if part.id not in part_iters:
                    part_iters[part.id] = self.project_store.append(
                        project_iter, [part.get_display_name(labels), part]
                    )
                self.project_store.append(part_iters[part.id], [_component_label(comp, labels), comp])
            else:
                self.project_store.append(project_iter, [_component_label(comp, labels), comp])

        self.project_tree.expand_all()

    def _on_tree_cursor_changed(self, tree):
        if self.app.in_cursor_change:
            return
        self.app.in_cursor_change = True
        try:
            path, column = tree.get_cursor()
            if path is None:
                return

            iter_ = self.project_store.get_iter(path)
            obj = self.project_store.get_value(iter_, 1)

            if isinstance(obj, Component):
                title_changed = self.app.project_manager.save_component_content()
                self.app.current_component = obj
                self.app.current_part = None
                self.app.styles_current_component = obj
                if title_changed:
                    self._refresh_project_tree()
                    self.project_tree.expand_all()
                content = self.app.project_manager.load_component_content(obj)
                buffer = self.app.text_view.get_buffer()
                buffer.set_text(content)
                self.app.update_status(_("Editing: {name}").format(name=obj.get_display_name(self.app.project_manager.resolve_labels())))
                self.app.styles_panel.update(obj.type)
                self.app.editor_view.update_preview()
        finally:
            self.app.in_cursor_change = False

    def _on_tree_button_press(self, tree, event):
        if event.button != 3:
            return False
        path_info = tree.get_path_at_pos(int(event.x), int(event.y))
        if path_info is None:
            return False
        path, column, cell_x, cell_y = path_info

        selection = tree.get_selection()
        if not selection.path_is_selected(path):
            selection.unselect_all()
            selection.select_path(path)
            tree.set_cursor(path)

        sel_count = selection.count_selected_rows()
        if sel_count > 1:
            comps = self._get_selected_components(selection)
            if len(comps) == sel_count:
                menu = Gtk.Menu()
                item_delete = Gtk.MenuItem(label=_("Delete {n} components").format(n=len(comps)))
                item_delete.connect("activate", self._actions.on_delete_multiple_components, comps)
                menu.append(item_delete)
                menu.show_all()
                menu.popup_at_pointer(event)
                return True

        iter_ = self.project_store.get_iter(path)
        obj = self.project_store.get_value(iter_, 1)

        menu = Gtk.Menu()
        if isinstance(obj, Component) and obj.type == ComponentType.PART:
            item_add = Gtk.MenuItem(label=_("Add Component to this Part"))
            item_add.connect("activate", self._actions.on_add_component, obj)
            menu.append(item_add)
            menu.append(Gtk.SeparatorMenuItem())
            item_rename = Gtk.MenuItem(label=_("Rename Part"))
            item_rename.connect("activate", self._actions.on_rename_part, obj, iter_)
            menu.append(item_rename)
            item_delete = Gtk.MenuItem(label=_("Delete Part"))
            item_delete.connect("activate", self._actions.on_delete_part, obj)
            menu.append(item_delete)
        elif isinstance(obj, Project):
            item_add_comp = Gtk.MenuItem(label=_("Add Component"))
            item_add_comp.connect("activate", self._actions.on_add_component)
            menu.append(item_add_comp)
        elif isinstance(obj, Component):
            item_duplicate = Gtk.MenuItem(label=_("Duplicate Component"))
            item_duplicate.connect("activate", self._actions.on_duplicate_component, obj)
            menu.append(item_duplicate)
            menu.append(Gtk.SeparatorMenuItem())
            item_rename = Gtk.MenuItem(label=_("Rename Component"))
            item_rename.connect("activate", self._actions.on_rename_component, obj, iter_)
            menu.append(item_rename)
            item_change_type = Gtk.MenuItem(label=_("Change Type"))
            change_type_menu = Gtk.Menu()
            for ct in ComponentType:
                ct_item = Gtk.MenuItem(label=self.app.project_manager.resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct]))
                ct_item.connect("activate", self._actions.on_change_component_type, obj, ct)
                change_type_menu.append(ct_item)
            item_change_type.set_submenu(change_type_menu)
            menu.append(item_change_type)
            parts = self.app.project.get_parts()
            if parts:
                item_move = Gtk.MenuItem(label=_("Move to Part"))
                move_menu = Gtk.Menu()
                for p in parts:
                    p_item = Gtk.MenuItem(label=p.title)
                    p_item.connect("activate", self._actions.on_move_to_part, obj, p)
                    move_menu.append(p_item)
                item_move.set_submenu(move_menu)
                menu.append(item_move)
            if obj.part_id:
                item_detach = Gtk.MenuItem(label=_("Detach from Part"))
                item_detach.connect("activate", self._actions.on_detach_from_part, obj)
                menu.append(item_detach)
            menu.append(Gtk.SeparatorMenuItem())
            item_styles = Gtk.MenuItem(label=_("Styles"))
            styles_menu = Gtk.Menu()
            type_label = self.app.project_manager.resolve_labels().get(obj.type.value, COMPONENT_TYPE_LABELS.get(obj.type, obj.type.value))
            s1 = Gtk.MenuItem(label=_("Of type '{label}'").format(label=type_label))
            s1.connect("activate", self.app.styles_panel.on_edit_type_css, obj)
            styles_menu.append(s1)
            s2 = Gtk.MenuItem(label=_("Of component '{name}'").format(name=obj.get_display_name(self.app.project_manager.resolve_labels())))
            s2.connect("activate", self.app.styles_panel.on_edit_component_css, obj)
            styles_menu.append(s2)
            item_styles.set_submenu(styles_menu)
            menu.append(item_styles)
            menu.append(Gtk.SeparatorMenuItem())
            item_delete = Gtk.MenuItem(label=_("Delete Component"))
            item_delete.connect("activate", self._actions.on_delete_component, obj)
            menu.append(item_delete)
        else:
            return False

        if self.app.read_only:
            menu.foreach(lambda item: item.set_sensitive(False))

        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    def on_close_project(self, widget):
        if self.app.project is None:
            return
        if not confirm(self.app.window, _("Close the current project?")):
            return
        if self.app.current_component and not self.app.read_only:
            self.app.project_manager.save_component_content()
        self.app.project = None
        self.app.main_window.update_project_sensitivity(False)
        self.project_store.clear()
        self.app.current_component = None
        self.app.styles_current_component = None
        self.app.styles_current_comp_type = None
        self.app.text_view.get_buffer().set_text("")
        self.app.webview.load_html(self.app.default_html, self.app.editor_view.get_base_uri())
        self.set_read_only_mode(False)
        self.app.update_status(_("Project closed"))

    def update_window_title(self):
        base = "MDToEPUB"
        if self.app.project and self.app.project.title:
            base = f"MDToEPUB \u2014 {self.app.project.title}"
        if self.app.read_only and "[READ ONLY]" not in base:
            base += " [READ ONLY]"
        self.app.window.set_title(base)

    def set_read_only_mode(self, enabled: bool):
        self.app.read_only = enabled
        if self.app.toolbar_save_btn:
            self.app.toolbar_save_btn.set_sensitive(not enabled)
        self.update_window_title()

    def on_add_component(self, button, part=None):
        """Delegate to actions."""
        self._actions.on_add_component(button, part)

    def on_menu_rename_component(self, widget):
        if not self.app.current_component:
            show_info(self.app.window, _("Select a component first"))
            return
        path, _ = self.project_tree.get_cursor()
        if path is None:
            return
        iter_ = self.project_store.get_iter(path)
        self._actions.on_rename_component(None, self.app.current_component, iter_)

    def on_menu_delete_component(self, widget):
        selection = self.project_tree.get_selection()
        model, paths = selection.get_selected_rows()
        comps = []
        for path in paths:
            iter_ = model.get_iter(path)
            obj = model.get_value(iter_, 1)
            if isinstance(obj, Component):
                comps.append(obj)
        if not comps:
            show_info(self.app.window, _("Select one or more components first"))
            return
        if len(comps) == 1:
            self._actions.on_delete_component(None, comps[0])
        else:
            self._actions.on_delete_multiple_components(None, comps)

    def _get_selected_components(self, selection):
        model, paths = selection.get_selected_rows()
        comps = []
        for path in paths:
            iter_ = model.get_iter(path)
            obj = model.get_value(iter_, 1)
            if isinstance(obj, Component):
                comps.append(obj)
        return comps

    # ─── Drag and drop ────────────────────────────────────────────────

    def _on_drag_begin(self, treeview, context):
        if self.app.read_only:
            self._drag_component_ids = []
            return
        selection = treeview.get_selection()
        __, paths = selection.get_selected_rows()
        self._drag_component_ids = []
        if paths:
            for p in paths:
                si = self.project_store.get_iter(p)
                if si is not None:
                    obj = self.project_store.get_value(si, 1)
                    if isinstance(obj, Component):
                        self._drag_component_ids.append(obj.id)

    def _on_drag_motion(self, treeview, context, x, y, time):
        if self.app.read_only:
            return False
        dest = treeview.get_dest_row_at_pos(int(x), int(y))
        if dest:
            path, pos = dest
            treeview.set_drag_dest_row(path, pos)
        return False

    def _on_drag_data_get(self, treeview, drag_context, data, info, time_):
        if self.app.read_only:
            return
        if not self._drag_component_ids:
            return
        data.set(Gdk.atom_intern("MOVE_ROW", False), 8, b"x")

    def _on_drag_data_received(self, treeview, context, x, y, selection_data, info, time_):
        if not self.app.project or self.app.read_only:
            context.finish(False, False, time_)
            return

        if not self._drag_component_ids:
            context.finish(False, False, time_)
            return

        dest = treeview.get_dest_row_at_pos(int(x), int(y))
        if not dest:
            context.finish(False, False, time_)
            return

        dest_path, dest_pos = dest
        source_ids = self._drag_component_ids

        dest_iter = self.project_store.get_iter(dest_path)
        if dest_iter is not None:
            dest_obj = self.project_store.get_value(dest_iter, 1)
            if isinstance(dest_obj, Component) and dest_obj.id in source_ids:
                context.finish(True, False, time_)
                return

        rows = []
        self._collect_tree_components(treeview, rows)
        source_indices = [i for i, (cid, _) in enumerate(rows) if cid in source_ids]

        if not source_indices:
            context.finish(False, False, time_)
            return

        dest_row = self._find_dest_row(rows, dest_path, dest_pos)

        if dest_row is None:
            context.finish(False, False, time_)
            return

        dragged = [rows[i] for i in source_indices]
        for i in reversed(source_indices):
            rows.pop(i)

        removed_before = sum(1 for i in source_indices if i < dest_row)
        adjusted_dest = dest_row - removed_before

        if dest_pos in (Gtk.TreeViewDropPosition.BEFORE, Gtk.TreeViewDropPosition.INTO_OR_BEFORE):
            insert_at = adjusted_dest
        elif dest_pos in (Gtk.TreeViewDropPosition.AFTER, Gtk.TreeViewDropPosition.INTO_OR_AFTER):
            insert_at = adjusted_dest + 1
        else:
            context.finish(False, False, time_)
            return

        insert_at = max(0, min(insert_at, len(rows)))
        for item in reversed(dragged):
            rows.insert(insert_at, item)

        new_components = []
        for idx, (cid, is_part) in enumerate(rows):
            comp = next((c for c in self.app.project.components if c.id == cid), None)
            if comp is None:
                continue
            comp.order = idx
            if not is_part:
                comp_part = self._find_part_for_row(rows, idx)
                comp.part_id = comp_part.id if comp_part else None
            new_components.append(comp)

        self.app.project.components = new_components
        FileService.save_project(self.app.project)
        self._refresh_project_tree()
        self.app.update_status(_("Component(s) reordered"))
        context.finish(True, False, time_)

    def _collect_tree_components(self, treeview, result):
        store = treeview.get_model()
        root_iter = store.get_iter_first()
        if root_iter is None:
            return
        child = store.iter_children(root_iter)
        while child is not None:
            obj = store.get_value(child, 1)
            if isinstance(obj, Component):
                if obj.type == ComponentType.PART:
                    result.append((obj.id, True))
                    comp_child = store.iter_children(child)
                    while comp_child is not None:
                        sub = store.get_value(comp_child, 1)
                        if isinstance(sub, Component):
                            result.append((sub.id, False))
                        comp_child = store.iter_next(comp_child)
                else:
                    result.append((obj.id, False))
            child = store.iter_next(child)

    def _find_dest_row(self, rows, dest_path, dest_pos):
        store = self.project_store
        dest_iter = store.get_iter(dest_path)
        if dest_iter is None:
            return None
        dest_obj = store.get_value(dest_iter, 1)
        if not isinstance(dest_obj, Component):
            return None
        for i, (cid, _) in enumerate(rows):
            if cid == dest_obj.id:
                return i
        return None

    def _find_part_for_row(self, rows, idx):
        for i in range(idx - 1, -1, -1):
            cid, is_part = rows[i]
            if is_part:
                return next((c for c in self.app.project.components if c.id == cid), None)
        return None

import uuid

import gi
from mdtoepub.models.component import Component, ComponentType
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, Pango

from ..models.project import Project
from ..models.component import Component, ComponentType, COMPONENT_TYPE_LABELS
from ..services.file_service import FileService
from ..services.labels_service import resolve_labels


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

    def build(self, left_box):
        browser_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        browser_header.set_margin_top(6)
        browser_header.set_margin_bottom(6)
        browser_header.set_margin_start(6)
        browser_header.set_margin_end(6)
        left_box.pack_start(browser_header, False, False, 0)

        browser_label = Gtk.Label(label="Navegador del Proyecto")
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

    def _refresh_project_tree(self):
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
        if self.app._in_cursor_change:
            return
        self.app._in_cursor_change = True
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
                self.app._styles_current_component = obj
                if title_changed:
                    self._refresh_project_tree()
                    self.project_tree.expand_all()
                content = self.app.project_manager.load_component_content(obj)
                buffer = self.app.text_view.get_buffer()
                buffer.set_text(content)
                self.app._update_status(f"Editando: {obj.get_display_name(self.app.project_manager.resolve_labels())}")
                self.app._styles_panel.update(obj.type)
                self.app.editor_view._update_preview()
        finally:
            self.app._in_cursor_change = False

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
                item_delete = Gtk.MenuItem(label=f"Eliminar {len(comps)} componentes")
                item_delete.connect("activate", self._on_delete_multiple_components, comps)
                menu.append(item_delete)
                menu.show_all()
                menu.popup_at_pointer(event)
                return True

        iter_ = self.project_store.get_iter(path)
        obj = self.project_store.get_value(iter_, 1)

        menu = Gtk.Menu()
        if isinstance(obj, Component) and obj.type == ComponentType.PART:
            item_add = Gtk.MenuItem(label="Anadir componente a esta parte")
            item_add.connect("activate", self._on_add_component, obj)
            menu.append(item_add)
            menu.append(Gtk.SeparatorMenuItem())
            item_rename = Gtk.MenuItem(label="Renombrar parte")
            item_rename.connect("activate", self._on_rename_part, obj, iter_)
            menu.append(item_rename)
            item_delete = Gtk.MenuItem(label="Eliminar parte")
            item_delete.connect("activate", self._on_delete_part, obj)
            menu.append(item_delete)
        elif isinstance(obj, Project):
            item_add_comp = Gtk.MenuItem(label="Anadir componente")
            item_add_comp.connect("activate", self._on_add_component)
            menu.append(item_add_comp)
        elif isinstance(obj, Component):
            item_duplicate = Gtk.MenuItem(label="Duplicar componente")
            item_duplicate.connect("activate", self._on_duplicate_component, obj)
            menu.append(item_duplicate)
            menu.append(Gtk.SeparatorMenuItem())
            item_rename = Gtk.MenuItem(label="Renombrar componente")
            item_rename.connect("activate", self._on_rename_component, obj, iter_)
            menu.append(item_rename)
            item_change_type = Gtk.MenuItem(label="Cambiar tipo")
            change_type_menu = Gtk.Menu()
            for ct in ComponentType:
                ct_item = Gtk.MenuItem(label=self.app.project_manager.resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct]))
                ct_item.connect("activate", self._on_change_component_type, obj, ct)
                change_type_menu.append(ct_item)
            item_change_type.set_submenu(change_type_menu)
            menu.append(item_change_type)
            parts = self.app.project.get_parts()
            if parts:
                item_move = Gtk.MenuItem(label="Mover a parte")
                move_menu = Gtk.Menu()
                for p in parts:
                    p_item = Gtk.MenuItem(label=p.title)
                    p_item.connect("activate", self._on_move_to_part, obj, p)
                    move_menu.append(p_item)
                item_move.set_submenu(move_menu)
                menu.append(item_move)
            if obj.part_id:
                item_detach = Gtk.MenuItem(label="Sacar de la parte")
                item_detach.connect("activate", self._on_detach_from_part, obj)
                menu.append(item_detach)
            menu.append(Gtk.SeparatorMenuItem())
            item_styles = Gtk.MenuItem(label="Estilos")
            styles_menu = Gtk.Menu()
            type_label = self.app.project_manager.resolve_labels().get(obj.type.value, COMPONENT_TYPE_LABELS.get(obj.type, obj.type.value))
            s1 = Gtk.MenuItem(label=f"Del tipo «{type_label}»")
            s1.connect("activate", self.app._styles_panel._on_edit_type_css, obj)
            styles_menu.append(s1)
            s2 = Gtk.MenuItem(label=f"Del componente «{obj.get_display_name(self.app.project_manager.resolve_labels())}»")
            s2.connect("activate", self.app._styles_panel._on_edit_component_css, obj)
            styles_menu.append(s2)
            item_styles.set_submenu(styles_menu)
            menu.append(item_styles)
            menu.append(Gtk.SeparatorMenuItem())
            item_delete = Gtk.MenuItem(label="Eliminar componente")
            item_delete.connect("activate", self._on_delete_component, obj)
            menu.append(item_delete)
        else:
            return False

        if self.app._read_only:
            menu.foreach(lambda item: item.set_sensitive(False))

        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    def _on_close_project(self, widget):
        if self.app.project is None:
            return
        if not confirm(self.app.window, "?Cerrar el proyecto actual?"):
            return
        if self.app.current_component and not self.app._read_only:
            self.app.project_manager.save_component_content()
        self.app.project = None
        self.project_store.clear()
        self.app.current_component = None
        self.app._styles_current_component = None
        self.app._styles_current_comp_type = None
        self.app.text_view.get_buffer().set_text("")
        self.app.webview.load_html(self.app.default_html, self.app.editor_view._get_base_uri())
        self._set_read_only_mode(False)
        self.app._update_status("Proyecto cerrado")

    def _update_window_title(self):
        base = "MDToEPUB"
        if self.app.project and self.app.project.title:
            base = f"MDToEPUB \u2014 {self.app.project.title}"
        if self.app._read_only and "[SOLO LECTURA]" not in base:
            base += " [SOLO LECTURA]"
        self.app.window.set_title(base)

    def _set_read_only_mode(self, enabled: bool):
        self.app._read_only = enabled
        if self.app._toolbar_save_btn:
            self.app._toolbar_save_btn.set_sensitive(not enabled)
        self._update_window_title()

    def _on_add_component(self, button, part=None):
        if not self.app.project:
            show_info(self.app.window, "Primero crea o abre un proyecto")
            return
        if self.app._read_only:
            show_info(self.app.window, "No se puede modificar un proyecto de solo lectura")
            return

        dialog = Gtk.Dialog(
            title="Anadir Componente",
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Anadir", Gtk.ResponseType.ACCEPT)

        content_area = dialog.get_content_area()
        content_area.set_spacing(12)
        content_area.set_margin_top(12)
        content_area.set_margin_bottom(12)
        content_area.set_margin_start(12)
        content_area.set_margin_end(12)

        type_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        type_label = Gtk.Label(label="Tipo:")
        type_label.set_size_request(80, -1)
        type_box.pack_start(type_label, False, False, 0)

        combo_type = Gtk.ComboBoxText()
        for ct in ComponentType:
            combo_type.append_text(self.app.project_manager.resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct]))
        combo_type.set_active(0)
        type_box.pack_start(combo_type, True, True, 0)
        content_area.add(type_box)

        comp_title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        comp_title_label = Gtk.Label(label="Titulo:")
        comp_title_label.set_size_request(80, -1)
        comp_title_box.pack_start(comp_title_label, False, False, 0)
        entry_title = Gtk.Entry()
        entry_title.set_hexpand(True)
        entry_title.set_placeholder_text("Titulo del componente")
        comp_title_box.pack_start(entry_title, True, True, 0)
        content_area.add(comp_title_box)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                type_index = combo_type.get_active()
                if type_index < 0:
                    type_index = 0
                component_type = list(ComponentType)[type_index]
                title = entry_title.get_text().strip()

                component = Component(type=component_type, title=title)
                component.filename = FileService.generate_filename(
                    component_type.value, title
                )
                if part is not None:
                    component.part_id = part.id

                self.app.project.add_component(component)
                initial_content = f"# {title}\n\n" if title else ""
                FileService.save_component(self.app.project.path, component, initial_content)
                FileService.save_project(self.app.project)
                self._refresh_project_tree()
                self.app._update_status(f"Componente anadido: {component.get_display_name(self.app.project_manager.resolve_labels())}")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_add_part(self, button):
        if not self.app.project:
            show_info(self.app.window, "Primero crea o abre un proyecto")
            return
        if self.app._read_only:
            show_info(self.app.window, "No se puede modificar un proyecto de solo lectura")
            return

        dialog = Gtk.Dialog(
            title="Anadir Parte",
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Anadir", Gtk.ResponseType.ACCEPT)

        content_area = dialog.get_content_area()
        content_area.set_spacing(12)
        content_area.set_margin_top(12)
        content_area.set_margin_bottom(12)
        content_area.set_margin_start(12)
        content_area.set_margin_end(12)

        part_title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        part_title_label = Gtk.Label(label="Titulo:")
        part_title_label.set_size_request(80, -1)
        part_title_box.pack_start(part_title_label, False, False, 0)
        entry_title = Gtk.Entry()
        entry_title.set_hexpand(True)
        entry_title.set_placeholder_text("Parte I: Inicios")
        part_title_box.pack_start(entry_title, True, True, 0)
        content_area.add(part_title_box)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                title = entry_title.get_text().strip()
                if not title:
                    labels = resolve_labels(self.app.project.language)
                    title = labels.get("part", "Parte")
                component_id = str(uuid.uuid4())
                part = Component(
                    id=component_id,
                    type=ComponentType.PART,
                    title=title,
                    filename=FileService.generate_filename("part", title),
                )
                self.app.project.add_component(part)
                initial_content = f"# {title}\n\n"
                FileService.save_component(self.app.project.path, part, initial_content)
                FileService.save_project(self.app.project)
                self._refresh_project_tree()
                self.app._update_status(f"Parte anadida: {title}")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_rename_part(self, menu_item, part, iter_):
        dialog = Gtk.Dialog(
            title="Renombrar parte",
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Renombrar", Gtk.ResponseType.ACCEPT)

        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        entry = Gtk.Entry()
        entry.set_text(part.title)
        entry.set_hexpand(True)
        content.add(entry)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                new_title = entry.get_text().strip()
                if not new_title:
                    labels = resolve_labels(self.app.project.language)
                    new_title = labels.get("part", "Parte")
                part.title = new_title
                self.project_store.set_value(iter_, 0, part.get_display_name(self.app.project_manager.resolve_labels()))
                FileService.save_project(self.app.project)
                self.app._update_status(f"Parte renombrada: {new_title}")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_delete_part(self, menu_item, part):
        dialog = Gtk.MessageDialog(
            transient_for=self.app.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Eliminar parte",
        )
        dialog.format_secondary_text(f"Se eliminara la parte \"{part.get_display_name(self.app.project_manager.resolve_labels())}\" y sus componentes quedaran sin agrupar.")

        def on_response(d, response):
            if response == Gtk.ResponseType.YES:
                for c in self.app.project.components:
                    if c.part_id == part.id:
                        c.part_id = None
                self.app.project.remove_component(part.id)
                FileService.save_project(self.app.project)
                self._refresh_project_tree()
                self.app._update_status(f"Parte eliminada: {part.get_display_name(self.app.project_manager.resolve_labels())}")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_rename_component(self, menu_item, component, iter_):
        dialog = Gtk.Dialog(
            title="Renombrar componente",
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Renombrar", Gtk.ResponseType.ACCEPT)

        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        entry = Gtk.Entry()
        entry.set_text(component.title)
        entry.set_hexpand(True)
        content.add(entry)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                new_title = entry.get_text().strip()
                if new_title:
                    component.title = new_title
                    self.project_store.set_value(iter_, 0, component.get_display_name(self.app.project_manager.resolve_labels()))
                    FileService.save_project(self.app.project)
                    self.app._update_status(f"Componente renombrado: {new_title}")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_duplicate_component(self, menu_item, component):
        new_comp = Component(
            id=str(uuid.uuid4()),
            type=component.type,
            title=component.title,
            filename=FileService.generate_filename(component.type.value, component.title),
            order=component.order + 1,
            part_id=component.part_id,
            frontmatter=component.frontmatter.copy(),
            custom_css=component.custom_css,
        )
        for c in self.app.project.components:
            if c.order >= new_comp.order:
                c.order += 1

        content = FileService.load_component(self.app.project.path, component)
        self.app.project.add_component(new_comp)
        FileService.save_component(self.app.project.path, new_comp, content or "")
        FileService.save_project(self.app.project)
        self._refresh_project_tree()
        self.app._update_status(f"Componente duplicado: {new_comp.get_display_name(self.app.project_manager.resolve_labels())}")

    def _on_move_to_part(self, menu_item, component, part):
        if component.part_id == part.id:
            return
        component.part_id = part.id
        FileService.save_project(self.app.project)
        self._refresh_project_tree()
        self.app._update_status(f"{component.get_display_name(self.app.project_manager.resolve_labels())} movido a {part.get_display_name(self.app.project_manager.resolve_labels())}")

    def _on_detach_from_part(self, menu_item, component):
        if not component.part_id:
            return
        if not confirm(self.app.window, f"Separar \xab{component.get_display_name(self.app.project_manager.resolve_labels())}\xbb de su parte?"):
            return
        component.part_id = None
        FileService.save_project(self.app.project)
        self._refresh_project_tree()
        self.app._update_status(f"{component.get_display_name(self.app.project_manager.resolve_labels())} separado de la parte")

    def _on_delete_component(self, menu_item, component):
        dialog = Gtk.MessageDialog(
            transient_for=self.app.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Eliminar componente",
        )
        dialog.format_secondary_text(f"Se eliminara el componente \"{component.get_display_name(self.app.project_manager.resolve_labels())}\".")

        def on_response(d, response):
            if response == Gtk.ResponseType.YES:
                if self.app.current_component and self.app.current_component.id == component.id:
                    self.app.text_view.get_buffer().set_text("")
                    self.app.webview.load_html(self.app.default_html, self.app.editor_view._get_base_uri())
                    self.app.current_component = None
                self.app.project.remove_component(component.id)
                FileService.save_project(self.app.project)
                self._refresh_project_tree()
                self.app._update_status(f"Componente eliminado: {component.get_display_name(self.app.project_manager.resolve_labels())}")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _get_selected_components(self, selection):
        model, paths = selection.get_selected_rows()
        comps = []
        for path in paths:
            iter_ = model.get_iter(path)
            obj = model.get_value(iter_, 1)
            if isinstance(obj, Component):
                comps.append(obj)
        return comps

    def _on_delete_multiple_components(self, menu_item, components):
        names = "\n".join(f"  - {c.get_display_name(self.app.project_manager.resolve_labels())}" for c in components)
        dialog = Gtk.MessageDialog(
            transient_for=self.app.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Eliminar {len(components)} componentes",
        )
        dialog.format_secondary_text(f"Se eliminaran los siguientes componentes:\n{names}")

        def on_response(d, response):
            if response == Gtk.ResponseType.YES:
                ids = {c.id for c in components}
                if self.app.current_component and self.app.current_component.id in ids:
                    self.app.text_view.get_buffer().set_text("")
                    self.app.webview.load_html(self.app.default_html, self.app.editor_view._get_base_uri())
                    self.app.current_component = None
                for comp in components:
                    self.app.project.remove_component(comp.id)
                FileService.save_project(self.app.project)
                self._refresh_project_tree()
                self.app._update_status(f"Eliminados {len(components)} componentes")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_change_component_type(self, menu_item, component, new_type):
        component.type = new_type
        if not component.title:
            component.title = ""
        FileService.save_project(self.app.project)
        self._refresh_project_tree()
        self.app._update_status(f"Tipo cambiado a: {self.app.project_manager.resolve_labels().get(new_type.value, COMPONENT_TYPE_LABELS[new_type])}")
        self.app.editor_view._update_preview()

    def _on_menu_rename_component(self, widget):
        if not self.app.current_component:
            show_info(self.app.window, "Selecciona un componente primero")
            return
        path, _ = self.project_tree.get_cursor()
        if path is None:
            return
        iter_ = self.project_store.get_iter(path)
        self._on_rename_component(None, self.app.current_component, iter_)

    def _on_menu_delete_component(self, widget):
        selection = self.project_tree.get_selection()
        model, paths = selection.get_selected_rows()
        comps = []
        for path in paths:
            iter_ = model.get_iter(path)
            obj = model.get_value(iter_, 1)
            if isinstance(obj, Component):
                comps.append(obj)
        if not comps:
            show_info(self.app.window, "Selecciona uno o varios componentes primero")
            return
        if len(comps) == 1:
            self._on_delete_component(None, comps[0])
        else:
            self._on_delete_multiple_components(None, comps)

    def _on_drag_begin(self, treeview, context):
        if self.app._read_only:
            self._drag_component_ids = []
            return
        selection = treeview.get_selection()
        _, paths = selection.get_selected_rows()
        self._drag_component_ids = []
        if paths:
            for p in paths:
                si = self.project_store.get_iter(p)
                if si is not None:
                    obj = self.project_store.get_value(si, 1)
                    if isinstance(obj, Component):
                        self._drag_component_ids.append(obj.id)

    def _on_drag_motion(self, treeview, context, x, y, time):
        if self.app._read_only:
            return False
        dest = treeview.get_dest_row_at_pos(int(x), int(y))
        if dest:
            path, pos = dest
            treeview.set_drag_dest_row(path, pos)
        return False

    def _on_drag_data_get(self, treeview, drag_context, data, info, time_):
        if self.app._read_only:
            return
        if not self._drag_component_ids:
            return
        data.set(Gdk.atom_intern("MOVE_ROW", False), 8, b"x")

    def _on_drag_data_received(self, treeview, context, x, y, selection_data, info, time_):
        if not self.app.project or self.app._read_only:
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
        self.app._update_status("Componente(s) reordenado(s)")
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

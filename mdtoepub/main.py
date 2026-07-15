#!/usr/bin/env python3
import sys
import os
import shutil
from pathlib import Path

if sys.platform == "linux":
    system_paths = ["/usr/lib/python3/dist-packages"]
    for path in system_paths:
        if path not in sys.path:
            sys.path.insert(0, path)

import re
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk, Gio, GLib, Gdk, GdkPixbuf, Pango

from .models.project import Project
from .models.component import Component, ComponentType, COMPONENT_TYPE_LABELS
from .services.file_service import FileService
from .services.epub_service import EpubService
from .services.yaml_service import YamlService
from .services.markdown_service import MarkdownService
from .services.image_service import ImageService
from .services.style_doc_service import StyleDocService
from .services.spell_service import SpellCheckService
from .services.theme_service import ThemeService
from .services.labels_service import resolve_labels


FRONTMATTER_DOCS = {
    "toc": [
        ("toc_include", "Lista de tipos de componente a incluir en el índice (ej: ['chapter', 'appendix'])"),
        ("toc_deep", "Profundidad maxima de encabezados en el índice (1-6, por defecto 2)"),
    ],
    "chapter": [
        ("show_title", "false para ocultar el titulo del capitulo"),
    ],
}

FRONTMATTER_COMMON = [
    ("show_title", "false para ocultar el titulo del componente (por defecto true)"),
    ("split_title", "false para desactivar la particion automatica del titulo en subtitulo + titulo al encontrar ' - ', ' -- ' o ' --- ' (por defecto true)"),
]


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


class MDToEPUBApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="com.github.mdtoepub",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.project = None
        self.window = None
        self.project_store = None
        self.current_component = None
        self.current_part = None
        self.md_service = MarkdownService()
        self.webview = None
        self.selected_folder = ""
        self._drag_paths = []
        self._drag_component_ids = []
        self._last_epub_path = None
        self._recent_projects = []
        self._in_cursor_change = False
        self._read_only = False
        self._dev_mode = os.environ.get("MDTOEPUB_DEV") == "1"
        self._toolbar_save_btn = None
        self._styles_current_component = None
        self._styles_current_comp_type = None

    def _resolve_labels(self):
        if self.project:
            return resolve_labels(self.project.language)
        return resolve_labels("es")

    def do_activate(self):
        settings = Gtk.Settings.get_default()
        if settings:
            settings.set_property("gtk-decoration-layout", "menu:minimize,maximize,close")
        self.window = Gtk.ApplicationWindow(application=self)
        self.window.set_title("MDToEPUB")
        self.window.set_default_size(1200, 800)
        self.window.set_decorated(True)
        self.window.set_resizable(True)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        from .views.main_window import MainWindow
        self.main_window = MainWindow(self)
        left_box, right_box = self.main_window.build(main_box)

        from .views.styles_panel import StylesPanel
        self._styles_panel = StylesPanel(self)
        self._styles_scrolled = self._styles_panel.build()

        from .views.editor_view import EditorView
        self.editor_view = EditorView(self)
        self.editor_view.build(right_box)

        from .views.project_tree import ProjectTree
        self.project_tree_view = ProjectTree(self)
        self.project_tree_view.build(left_box)
        self.project_tree = self.project_tree_view.project_tree

        from .controllers.export_import import ExportImportController
        self.export_import_ctrl = ExportImportController(self)

        self.window.add(main_box)
        self.window.show_all()
        self._load_recent_projects()

    # ─── Delegation: tree & component actions ─────────────────────────

    def _refresh_project_tree(self):
        self.project_tree_view._refresh_project_tree()

    def _on_tree_cursor_changed(self, tree):
        self.project_tree_view._on_tree_cursor_changed(tree)

    def _on_tree_button_press(self, tree, event):
        return self.project_tree_view._on_tree_button_press(tree, event)

    def _on_add_component(self, button, part=None):
        self.project_tree_view._on_add_component(button, part)

    def _on_add_part(self, button):
        self.project_tree_view._on_add_part(button)

    def _on_menu_rename_component(self, widget):
        self.project_tree_view._on_menu_rename_component(widget)

    def _on_menu_delete_component(self, widget):
        self.project_tree_view._on_menu_delete_component(widget)

    def _on_rename_component(self, menu_item, component, iter_):
        self.project_tree_view._on_rename_component(menu_item, component, iter_)

    def _on_delete_component(self, menu_item, component):
        self.project_tree_view._on_delete_component(menu_item, component)

    def _on_delete_multiple_components(self, menu_item, components):
        self.project_tree_view._on_delete_multiple_components(menu_item, components)

    def _on_rename_part(self, menu_item, part, iter_):
        self.project_tree_view._on_rename_part(menu_item, part, iter_)

    def _on_delete_part(self, menu_item, part):
        self.project_tree_view._on_delete_part(menu_item, part)

    def _on_duplicate_component(self, menu_item, component):
        self.project_tree_view._on_duplicate_component(menu_item, component)

    def _on_move_to_part(self, menu_item, component, part):
        self.project_tree_view._on_move_to_part(menu_item, component, part)

    def _on_detach_from_part(self, menu_item, component):
        self.project_tree_view._on_detach_from_part(menu_item, component)

    def _on_change_component_type(self, menu_item, component, new_type):
        self.project_tree_view._on_change_component_type(menu_item, component, new_type)

    def _get_selected_components(self, selection):
        return self.project_tree_view._get_selected_components(selection)

    def _on_drag_begin(self, treeview, context):
        self.project_tree_view._on_drag_begin(treeview, context)

    def _on_drag_motion(self, treeview, context, x, y, time):
        self.project_tree_view._on_drag_motion(treeview, context, x, y, time)

    def _on_drag_data_get(self, treeview, drag_context, data, info, time_):
        self.project_tree_view._on_drag_data_get(treeview, drag_context, data, info, time_)

    def _on_drag_data_received(self, treeview, context, x, y, selection_data, info, time_):
        self.project_tree_view._on_drag_data_received(treeview, context, x, y, selection_data, info, time_)

    def _on_close_project(self, widget):
        self.project_tree_view._on_close_project(widget)

    def _update_window_title(self):
        self.project_tree_view._update_window_title()

    def _set_read_only_mode(self, enabled: bool):
        self.project_tree_view._set_read_only_mode(enabled)

    # ─── Delegation: editor & preview ─────────────────────────────────

    def _update_preview(self):
        self.editor_view._update_preview()

    def _focus_editor(self):
        self.editor_view._focus_editor()

    def _focus_preview(self):
        self.editor_view._focus_preview()

    def _get_base_uri(self) -> str:
        return self.editor_view._get_base_uri()

    def _get_editor_text(self) -> str:
        return self.editor_view._get_editor_text()

    def _update_spell_lang(self):
        self.editor_view._update_spell_lang()

    # ─── Delegation: styles panel ─────────────────────────────────────

    def _update_styles_panel(self, component_type=None):
        self._styles_panel.update(component_type)

    def _load_theme_css(self, component_type=None):
        return self._styles_panel._load_theme_css(component_type)

    def _on_edit_book_css(self, widget):
        self._styles_panel._on_edit_book_css(widget)

    def _on_edit_type_css(self, widget, component):
        self._styles_panel._on_edit_type_css(widget, component)

    def _on_edit_component_css(self, widget, component):
        self._styles_panel._on_edit_component_css(widget, component)

    def _on_manage_type_css(self, widget):
        self._styles_panel._on_manage_type_css(widget)

    # ─── Delegation: dialogs ──────────────────────────────────────────

    def _on_project_config(self, button):
        from .views.dialogs.project_config import show_project_config
        show_project_config(self)

    def _on_theme_manager(self, widget):
        from .views.dialogs.theme_manager import show_theme_manager
        show_theme_manager(self)

    # ─── Delegation: export / import ──────────────────────────────────

    def _on_export_epub(self, button):
        self.export_import_ctrl.export_epub(button)

    def _on_import_book(self, button):
        self.export_import_ctrl.import_book(button)

    def _on_import_epub(self, button):
        self.export_import_ctrl.import_epub(button)

    def _on_open_epub(self, button):
        self.export_import_ctrl.open_epub(button)

    # ─── Core: project lifecycle ──────────────────────────────────────

    def _save_current_component(self):
        if self._read_only:
            return False
        text = self._get_editor_text()
        frontmatter, markdown_content = YamlService.parse_frontmatter(text)

        component = self.current_part or self.current_component
        if component is None or component not in self.project.components:
            return False

        component.frontmatter = frontmatter
        FileService.save_component(self.project.path, component, text)

        h1_match = re.search(r'^#\s+(.+)$', markdown_content, re.MULTILINE)
        new_title = h1_match.group(1).strip() if h1_match else ""
        if new_title and new_title != component.title:
            component.title = new_title
            FileService.save_project(self.project)
            return True

        return False

    def _load_component_content(self, component: Component) -> str:
        content = FileService.load_component(self.project.path, component)
        if component.frontmatter and not content.startswith("---"):
            content = YamlService.join_content(component.frontmatter, content)
        return content

    def _confirm_discard_project(self):
        if self.project is None:
            return True
        return self._confirm("Se cerrará el proyecto actual. ¿Continuar?")

    def _on_new_project(self, button):
        if not self._confirm_discard_project():
            return
        dialog = Gtk.Dialog(
            title="Nuevo Proyecto",
            transient_for=self.window,
            modal=True,
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Crear", Gtk.ResponseType.ACCEPT)
        dialog.set_default_size(500, -1)

        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        folder_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        folder_label = Gtk.Label(label="Carpeta padre:")
        folder_label.set_size_request(80, -1)
        folder_box.pack_start(folder_label, False, False, 0)

        self.folder_chooser_btn = Gtk.Button(label=GLib.get_home_dir())
        self.folder_chooser_btn.set_hexpand(True)
        self.selected_folder = GLib.get_home_dir()

        def on_folder_clicked(btn):
            fc_dialog = Gtk.FileChooserNative(
                title="Seleccionar carpeta",
                transient_for=dialog,
                action=Gtk.FileChooserAction.SELECT_FOLDER,
                accept_label="_Seleccionar",
                cancel_label="_Cancelar",
            )
            if fc_dialog.run() == Gtk.ResponseType.ACCEPT:
                path = fc_dialog.get_filename()
                if path:
                    self.selected_folder = path
                    btn.set_label(path)
            fc_dialog.destroy()

        self.folder_chooser_btn.connect("clicked", on_folder_clicked)
        folder_box.pack_start(self.folder_chooser_btn, True, True, 0)
        content.add(folder_box)

        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        name_label = Gtk.Label(label="Nombre:")
        name_label.set_size_request(80, -1)
        name_box.pack_start(name_label, False, False, 0)
        entry_name = Gtk.Entry()
        entry_name.set_hexpand(True)
        entry_name.set_placeholder_text("mi_libro")
        name_box.pack_start(entry_name, True, True, 0)
        content.add(name_box)

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_label = Gtk.Label(label="Titulo:")
        title_label.set_size_request(80, -1)
        title_box.pack_start(title_label, False, False, 0)
        entry_title = Gtk.Entry()
        entry_title.set_hexpand(True)
        entry_title.set_placeholder_text("Mi Gran Libro")
        title_box.pack_start(entry_title, True, True, 0)
        content.add(title_box)

        author_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        author_label = Gtk.Label(label="Autor:")
        author_label.set_size_request(80, -1)
        author_box.pack_start(author_label, False, False, 0)
        entry_author = Gtk.Entry()
        entry_author.set_hexpand(True)
        entry_author.set_placeholder_text("Autor Ejemplo")
        author_box.pack_start(entry_author, True, True, 0)
        content.add(author_box)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                name = entry_name.get_text().strip()
                title = entry_title.get_text().strip()
                author = entry_author.get_text().strip()

                if not name:
                    self._show_error("El nombre del proyecto es obligatorio")
                    d.destroy()
                    return

                project_path = FileService.create_project_structure(self.selected_folder, name)
                project_path.title = title
                project_path.author = author
                FileService.save_project(project_path)

                self.project = project_path
                self._update_spell_lang()
                self.current_component = None
                self._set_read_only_mode(False)
                self._add_recent_project(project_path.path)
                self._refresh_project_tree()
                self._update_status(f"Proyecto creado: {name}")

            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_open_project(self, button):
        if not self._confirm_discard_project():
            return
        dialog = Gtk.FileChooserNative(
            title="Abrir Proyecto",
            transient_for=self.window,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            accept_label="_Abrir",
            cancel_label="_Cancelar",
        )
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            path = dialog.get_filename()
            if path:
                yaml_file = os.path.join(path, "project.yaml")
                if os.path.exists(yaml_file):
                    project = FileService.load_project(path)
                    if project:
                        self.project = project
                        self._update_spell_lang()
                        self.current_component = None
                        self._set_read_only_mode(False)
                        self._add_recent_project(project.path)
                        self._refresh_project_tree()
                        self.text_view.get_buffer().set_text("")
                        self._update_status(f"Proyecto abierto: {project.name}")
                    else:
                        self._show_error("Error al cargar el proyecto")
                else:
                    self._show_error("No se encontro project.yaml en esta carpeta")
        dialog.destroy()

    def _on_save_project(self, button):
        if not self.project:
            self._show_info("No hay proyecto abierto")
            return
        if self._read_only:
            return
        if self.current_component:
            self._save_current_component()
        FileService.save_project(self.project)
        self._update_status("Proyecto guardado")

    def _on_save_project_as(self, button):
        if not self.project:
            self._show_info("No hay proyecto abierto")
            return
        if self._read_only:
            return
        dialog = Gtk.FileChooserNative(
            title="Guardar Proyecto Como",
            transient_for=self.window,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            accept_label="_Guardar",
            cancel_label="_Cancelar",
        )
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            path = dialog.get_filename()
            if path:
                new_project = FileService.create_project_structure(path, self.project.name)
                new_project.title = self.project.title
                new_project.author = self.project.author
                new_project.language = self.project.language
                new_project.theme_id = self.project.theme_id
                new_project.epub_version = self.project.epub_version
                new_project.figure_numbering = self.project.figure_numbering
                new_project.figure_numbering_style = self.project.figure_numbering_style
                new_project.table_numbering = self.project.table_numbering
                new_project.table_numbering_style = self.project.table_numbering_style
                new_project.edition = self.project.edition
                new_project.isbn = self.project.isbn
                new_project.publisher = self.project.publisher
                new_project.subtitle = self.project.subtitle

                old_components_dir = os.path.join(self.project.path, "components")
                new_components_dir = os.path.join(new_project.path, "components")
                if os.path.exists(old_components_dir):
                    for item in os.listdir(old_components_dir):
                        src = os.path.join(old_components_dir, item)
                        dst = os.path.join(new_components_dir, item)
                        if os.path.isfile(src):
                            shutil.copy2(src, dst)

                for comp in self.project.components:
                    new_comp = Component(
                        id=comp.id,
                        type=comp.type,
                        title=comp.title,
                        filename=comp.filename,
                        order=comp.order,
                        part_id=comp.part_id,
                        frontmatter=comp.frontmatter.copy(),
                    )
                    new_project.components.append(new_comp)

                FileService.save_project(new_project)
                self.project = new_project
                self._add_recent_project(new_project.path)
                self._refresh_project_tree()
                self._update_status(f"Proyecto guardado en: {new_project.path}")
        dialog.destroy()

    def _on_load_sample_book(self, widget, book_dir="sample_book"):
        if not self._confirm_discard_project():
            return
        sample_dir = os.path.join(os.path.dirname(__file__), "data", book_dir)
        yaml_path = os.path.join(sample_dir, "project.yaml")
        if not os.path.exists(yaml_path):
            self._show_error("No se encontro el libro de ejemplo")
            return
        project = FileService.load_project(sample_dir)
        if project:
            self.project = project
            self.project.path = sample_dir
            self._update_spell_lang()
            self.current_component = None
            self._set_read_only_mode(True)
            self._refresh_project_tree()
            self.text_view.get_buffer().set_text("")
            self._update_status(f"Libro de ejemplo cargado: {project.name} [SOLO LECTURA]")
        else:
            self._show_error("Error al cargar el libro de ejemplo")

    # ─── About dialog ─────────────────────────────────────────────────

    def _on_about(self, widget):
        dialog = Gtk.AboutDialog(
            transient_for=self.window,
            modal=True,
        )
        dialog.set_program_name("MDToEPUB")
        dialog.set_version("1.2.0")
        dialog.set_comments("Editor de EPUB a partir de Markdown")
        dialog.set_license_type(Gtk.License.GPL_3_0)
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.show_all()

    # ─── Global config ────────────────────────────────────────────────

    def _on_global_config(self, action, param):
        config_dir = os.path.join(GLib.get_user_config_dir(), "mdtoepub")
        config_file = os.path.join(config_dir, "config.yaml")
        os.makedirs(config_dir, exist_ok=True)
        config = YamlService.load(config_file)

        if not config:
            config = {
                "editor": {"font_size": 12, "tab_size": 4, "auto_save_interval": 30},
                "preview": {"zoom": 100},
                "general": {"window_width": 1200, "window_height": 800},
                "epub_reader_path": "",
            }

        dialog = Gtk.Dialog(
            title="Configuracion Global",
            transient_for=self.window,
            modal=True,
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Guardar", Gtk.ResponseType.ACCEPT)
        dialog.set_default_size(500, -1)

        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        notebook = Gtk.Notebook()
        notebook.set_vexpand(True)
        content.add(notebook)

        editor_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        editor_page.set_margin_top(8)
        editor_page.set_margin_bottom(8)
        editor_page.set_margin_start(8)
        editor_page.set_margin_end(8)
        notebook.append_page(editor_page, Gtk.Label(label="Editor"))

        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(12)
        grid.set_hexpand(True)
        editor_page.pack_start(grid, False, False, 0)

        row = 0
        label = Gtk.Label(label="Tamano fuente:")
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        spin_font_size = Gtk.SpinButton()
        spin_font_size.set_range(8, 48)
        spin_font_size.set_value(config.get("editor", {}).get("font_size", 12))
        grid.attach(spin_font_size, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="Tamano tab:")
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        spin_tab = Gtk.SpinButton()
        spin_tab.set_range(2, 8)
        spin_tab.set_value(config.get("editor", {}).get("tab_size", 4))
        grid.attach(spin_tab, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="Auto-guardado (s):")
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        spin_auto = Gtk.SpinButton()
        spin_auto.set_range(10, 300)
        spin_auto.set_value(config.get("editor", {}).get("auto_save_interval", 30))
        grid.attach(spin_auto, 1, row, 1, 1)

        general_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        general_page.set_margin_top(8)
        general_page.set_margin_bottom(8)
        general_page.set_margin_start(8)
        general_page.set_margin_end(8)
        notebook.append_page(general_page, Gtk.Label(label="General"))

        grid_general = Gtk.Grid()
        grid_general.set_row_spacing(8)
        grid_general.set_column_spacing(12)
        grid_general.set_hexpand(True)
        general_page.pack_start(grid_general, False, False, 0)

        reader_row = 0
        reader_label = Gtk.Label(label="Lector EPUB:")
        reader_label.set_xalign(1)
        grid_general.attach(reader_label, 0, reader_row, 1, 1)

        reader_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entry_reader = Gtk.Entry()
        entry_reader.set_hexpand(True)
        entry_reader.set_placeholder_text("Dejar vacio para usar el visor del sistema")
        entry_reader.set_text(config.get("epub_reader_path", ""))
        reader_box.pack_start(entry_reader, True, True, 0)

        def on_reader_browse(btn):
            fc = Gtk.FileChooserDialog(
                title="Seleccionar lector EPUB",
                transient_for=dialog,
                action=Gtk.FileChooserAction.OPEN,
            )
            fc.add_button("Cancelar", Gtk.ResponseType.CANCEL)
            fc.add_button("Seleccionar", Gtk.ResponseType.ACCEPT)
            def on_fc_response(d, response):
                if response == Gtk.ResponseType.ACCEPT:
                    entry_reader.set_text(d.get_filename())
                d.destroy()
            fc.connect("response", on_fc_response)
            fc.show_all()

        browse_btn = Gtk.Button(label="Examinar...")
        browse_btn.connect("clicked", on_reader_browse)
        reader_box.pack_start(browse_btn, False, False, 0)
        grid_general.attach(reader_box, 1, reader_row, 1, 1)

        def on_global_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                config["editor"]["font_size"] = int(spin_font_size.get_value())
                config["editor"]["tab_size"] = int(spin_tab.get_value())
                config["editor"]["auto_save_interval"] = int(spin_auto.get_value())
                config["epub_reader_path"] = entry_reader.get_text().strip()
                YamlService.save(config, config_file)
                self._show_info("Configuracion global guardada")
            d.destroy()

        dialog.connect("response", on_global_response)
        dialog.show_all()

    # ─── Recent projects ──────────────────────────────────────────────

    def _get_config_path(self) -> tuple:
        config_dir = os.path.join(GLib.get_user_config_dir(), "mdtoepub")
        os.makedirs(config_dir, exist_ok=True)
        config_file = os.path.join(config_dir, "config.yaml")
        return config_dir, config_file

    def _load_recent_projects(self):
        config = None
        try:
            _, config_file = self._get_config_path()
            if os.path.exists(config_file):
                config = YamlService.load(config_file)
        except Exception:
            config = None
        if config:
            self._recent_projects = config.get("recent_projects", [])
        else:
            self._recent_projects = []
        self._rebuild_recent_menu()

    def _save_recent_projects(self):
        _, config_file = self._get_config_path()
        config = YamlService.load(config_file)
        config["recent_projects"] = self._recent_projects
        YamlService.save(config, config_file)

    def _add_recent_project(self, project_path):
        if project_path in self._recent_projects:
            self._recent_projects.remove(project_path)
        self._recent_projects.insert(0, project_path)
        self._recent_projects = self._recent_projects[:10]
        self._save_recent_projects()
        self._rebuild_recent_menu()

    def _rebuild_recent_menu(self):
        for child in self._recent_menu.get_children():
            self._recent_menu.remove(child)
        if not self._recent_projects:
            item = Gtk.MenuItem(label="(sin proyectos recientes)")
            item.set_sensitive(False)
            self._recent_menu.append(item)
        else:
            for path in self._recent_projects:
                name = os.path.basename(path)
                item = Gtk.MenuItem(label=f"{name}  ({path})")
                item.connect("activate", lambda w, p=path: self._open_recent_project(p))
                self._recent_menu.append(item)
        self._recent_menu.show_all()

    def _open_recent_project(self, path):
        if not self._confirm_discard_project():
            return
        yaml_file = os.path.join(path, "project.yaml")
        if not os.path.exists(yaml_file):
            self._show_error(f"El proyecto ya no existe:\n{path}")
            self._recent_projects = [p for p in self._recent_projects if p != path]
            self._save_recent_projects()
            self._rebuild_recent_menu()
            return
        project = FileService.load_project(path)
        if project:
            self.project = project
            self._update_spell_lang()
            self.current_component = None
            self._set_read_only_mode(False)
            self._refresh_project_tree()
            self.text_view.get_buffer().set_text("")
            self._update_status(f"Proyecto abierto: {project.name}")
            self._add_recent_project(path)
        else:
            self._show_error("Error al cargar el proyecto")

    # ─── Status bar ───────────────────────────────────────────────────

    def _update_status(self, message):
        self.status_label.set_text(message)

    # ─── Utility dialogs ──────────────────────────────────────────────

    def _show_error(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Error",
        )
        dialog.format_secondary_text(message)
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.show_all()

    def _show_info(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Informacion",
        )
        dialog.format_secondary_text(message)
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.show_all()

    def _confirm(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Confirmar",
        )
        dialog.format_secondary_text(message)
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.YES


def main():
    app = MDToEPUBApp()
    return app.run(sys.argv)


def main_with_system_gtk():
    if sys.platform == "linux":
        system_paths = ["/usr/lib/python3/dist-packages"]
        for path in system_paths:
            if path not in sys.path:
                sys.path.insert(0, path)
    return main()


if __name__ == "__main__":
    main()

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
from gi.repository import Gtk, Gio, GLib, Gdk, GdkPixbuf, Pango, WebKit2, GtkSource

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
        from .services.labels_service import resolve_labels
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

        self._setup_ui(main_box)
        self._setup_statusbar(main_box)

        self.window.add(main_box)
        self.window.show_all()
        self._load_recent_projects()

    def _setup_menubar(self, container):
        menubar = Gtk.MenuBar()

        # Archivo
        archivo = Gtk.MenuItem(label="Archivo")
        archivo_menu = Gtk.Menu()
        archivo.set_submenu(archivo_menu)
        item = Gtk.MenuItem(label="Nuevo proyecto")
        item.connect("activate", self._on_new_project)
        archivo_menu.append(item)
        item = Gtk.MenuItem(label="Abrir proyecto")
        item.connect("activate", self._on_open_project)
        archivo_menu.append(item)
        item = Gtk.MenuItem(label="Guardar")
        item.connect("activate", self._on_save_project)
        archivo_menu.append(item)
        item = Gtk.MenuItem(label="Guardar como")
        item.connect("activate", self._on_save_project_as)
        archivo_menu.append(item)
        archivo_menu.append(Gtk.SeparatorMenuItem())
        item = Gtk.MenuItem(label="Cerrar proyecto")
        item.connect("activate", self._on_close_project)
        archivo_menu.append(item)
        archivo_menu.append(Gtk.SeparatorMenuItem())
        self._recent_menu = Gtk.Menu()
        recent_item = Gtk.MenuItem(label="Proyectos recientes")
        recent_item.set_submenu(self._recent_menu)
        archivo_menu.append(recent_item)
        archivo_menu.append(Gtk.SeparatorMenuItem())
        item = Gtk.MenuItem(label="Importar libro...")
        item.connect("activate", self._on_import_book)
        archivo_menu.append(item)
        item = Gtk.MenuItem(label="Importar libro EPUB...")
        item.connect("activate", self._on_import_epub)
        archivo_menu.append(item)
        archivo_menu.append(Gtk.SeparatorMenuItem())
        item = Gtk.MenuItem(label="Salir")
        item.connect("activate", lambda w: self.window.destroy())
        archivo_menu.append(item)
        menubar.append(archivo)

        # Componente
        componente = Gtk.MenuItem(label="Componente")
        componente_menu = Gtk.Menu()
        componente.set_submenu(componente_menu)
        item = Gtk.MenuItem(label="Anadir componente")
        item.connect("activate", self._on_add_component)
        componente_menu.append(item)
        componente_menu.append(Gtk.SeparatorMenuItem())
        item = Gtk.MenuItem(label="Renombrar componente")
        item.connect("activate", self._on_menu_rename_component)
        componente_menu.append(item)
        item = Gtk.MenuItem(label="Eliminar componente")
        item.connect("activate", self._on_menu_delete_component)
        componente_menu.append(item)
        menubar.append(componente)

        # Ver
        ver = Gtk.MenuItem(label="Ver")
        ver_menu = Gtk.Menu()
        ver.set_submenu(ver_menu)
        item = Gtk.MenuItem(label="Editor")
        item.connect("activate", lambda w: self._focus_editor())
        ver_menu.append(item)
        item = Gtk.MenuItem(label="Preview")
        item.connect("activate", lambda w: self._focus_preview())
        ver_menu.append(item)
        menubar.append(ver)

        # Exportar
        exportar = Gtk.MenuItem(label="Exportar")
        exportar_menu = Gtk.Menu()
        exportar.set_submenu(exportar_menu)
        item = Gtk.MenuItem(label="Exportar EPUB")
        item.connect("activate", self._on_export_epub)
        exportar_menu.append(item)
        item = Gtk.MenuItem(label="Abrir EPUB")
        item.connect("activate", self._on_open_epub)
        exportar_menu.append(item)
        menubar.append(exportar)

        # Configuracion
        config = Gtk.MenuItem(label="Configuracion")
        config_menu = Gtk.Menu()
        config.set_submenu(config_menu)
        item = Gtk.MenuItem(label="Proyecto")
        item.connect("activate", self._on_project_config)
        config_menu.append(item)
        item = Gtk.MenuItem(label="Global")
        item.connect("activate", lambda w: self._on_global_config(None, None))
        config_menu.append(item)
        item = Gtk.MenuItem(label="Temas")
        item.connect("activate", self._on_theme_manager)
        config_menu.append(item)
        menubar.append(config)

        # Ayuda
        ayuda = Gtk.MenuItem(label="Ayuda")
        ayuda_menu = Gtk.Menu()
        ayuda.set_submenu(ayuda_menu)
        libros_ejemplo = Gtk.MenuItem(label="Libros de ejemplo")
        libros_menu = Gtk.Menu()
        libros_ejemplo.set_submenu(libros_menu)
        item = Gtk.MenuItem(label="Novela clásica")
        item.connect("activate", self._on_load_sample_book, "sample_book")
        libros_menu.append(item)
        item = Gtk.MenuItem(label="Libro de texto")
        item.connect("activate", self._on_load_sample_book, "sample_book_textbook")
        libros_menu.append(item)
        ayuda_menu.append(libros_ejemplo)
        ayuda_menu.append(Gtk.SeparatorMenuItem())
        item = Gtk.MenuItem(label="Acerca de")
        item.connect("activate", self._on_about)
        ayuda_menu.append(item)
        menubar.append(ayuda)

        container.pack_start(menubar, False, False, 0)

    def _setup_toolbar(self, container):
        toolbar = Gtk.Toolbar()
        toolbar.get_style_context().add_class("primary-toolbar")

        new_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("document-new-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        new_btn.set_label("Nuevo")
        new_btn.set_tooltip_text("Nuevo proyecto")
        new_btn.connect("clicked", self._on_new_project)
        toolbar.insert(new_btn, -1)

        open_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("folder-open-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        open_btn.set_label("Abrir")
        open_btn.set_tooltip_text("Abrir proyecto")
        open_btn.connect("clicked", self._on_open_project)
        toolbar.insert(open_btn, -1)

        self._toolbar_save_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("document-save-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        self._toolbar_save_btn.set_label("Guardar")
        self._toolbar_save_btn.set_tooltip_text("Guardar proyecto")
        self._toolbar_save_btn.connect("clicked", self._on_save_project)
        toolbar.insert(self._toolbar_save_btn, -1)

        sep1 = Gtk.SeparatorToolItem()
        toolbar.insert(sep1, -1)

        project_config_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("preferences-system-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        project_config_btn.set_label("Configurar")
        project_config_btn.set_tooltip_text("Configuracion del proyecto")
        project_config_btn.connect("clicked", self._on_project_config)
        toolbar.insert(project_config_btn, -1)

        sep2 = Gtk.SeparatorToolItem()
        toolbar.insert(sep2, -1)

        export_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("document-send-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        export_btn.set_label("Exportar EPUB")
        export_btn.set_tooltip_text("Exportar a EPUB")
        export_btn.get_style_context().add_class("suggested-action")
        export_btn.connect("clicked", self._on_export_epub)
        toolbar.insert(export_btn, -1)

        open_epub_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("document-open-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        open_epub_btn.set_label("Abrir EPUB")
        open_epub_btn.set_tooltip_text("Abrir EPUB generado")
        open_epub_btn.connect("clicked", self._on_open_epub)
        toolbar.insert(open_epub_btn, -1)

        container.pack_start(toolbar, False, False, 0)

    def _setup_ui(self, container):
        self._setup_menubar(container)
        self._setup_toolbar(container)
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        container.pack_start(paned, True, True, 0)

        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left_box.set_size_request(250, -1)
        left_box.set_vexpand(True)
        paned.pack1(left_box, True, True)

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

        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right_box.set_vexpand(True)
        paned.pack2(right_box, True, True)

        # Register custom language before any GtkSource language is looked up
        lang_dir = os.path.join(os.path.dirname(__file__), "lang-specs")
        if os.path.isdir(lang_dir):
            lm = GtkSource.LanguageManager.get_default()
            sp = list(lm.get_search_path())
            sp.insert(0, lang_dir)
            lm.set_search_path(sp)
        help_lang = GtkSource.LanguageManager.get_default().get_language("mdtoepub-help")

        editor_scrolled = Gtk.ScrolledWindow()
        editor_scrolled.set_vexpand(True)
        self.text_view = GtkSource.View.new_with_buffer(
            GtkSource.Buffer.new_with_language(
                GtkSource.LanguageManager.get_default().get_language("markdown")
            )
        )
        self.text_view.set_editable(True)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_view.set_monospace(True)
        editor_scrolled.add(self.text_view)

        # Spell-check setup
        self.spell_service = SpellCheckService()
        self._spell_timer_id = 0
        self._misspelled_words = []
        self._session_ignored_words = set()

        buf = self.text_view.get_buffer()
        self._spell_tag = buf.create_tag("misspelled",
                                         underline=Pango.Underline.ERROR)

        def _on_buffer_changed(*_a):
            if self._spell_timer_id:
                GLib.source_remove(self._spell_timer_id)
            self._spell_timer_id = GLib.timeout_add(600, self._run_spell_check)

        buf.connect("changed", _on_buffer_changed)

        self.text_view.connect("populate-popup", self._on_spell_popup)

        self.webview = WebKit2.WebView()
        self.webview.set_vexpand(True)

        front_scrolled = Gtk.ScrolledWindow()
        front_scrolled.set_vexpand(True)
        front_buf = GtkSource.Buffer.new_with_language(help_lang)
        self.front_textview = GtkSource.View.new_with_buffer(front_buf)
        self.front_textview.set_editable(False)
        self.front_textview.set_cursor_visible(False)
        self.front_textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        front_scrolled.add(self.front_textview)

        syntax_scrolled = Gtk.ScrolledWindow()
        syntax_scrolled.set_vexpand(True)
        syntax_buf = GtkSource.Buffer.new_with_language(help_lang)
        self.syntax_textview = GtkSource.View.new_with_buffer(syntax_buf)
        self.syntax_textview.set_editable(False)
        self.syntax_textview.set_cursor_visible(False)
        self.syntax_textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.syntax_textview.set_monospace(True)
        syntax_scrolled.add(self.syntax_textview)
        self._init_syntax_help(syntax_buf)

        # Inner notebook: Contenido (Editor + Vista previa)
        self.content_notebook = Gtk.Notebook()
        self.content_notebook.append_page(editor_scrolled, Gtk.Label(label="Editor"))
        self.content_notebook.append_page(self.webview, Gtk.Label(label="Vista previa"))

        # Styles panel (replaces old Tema tab)
        self._build_styles_panel()

        # Help notebook: Metadatos + Sintaxis (merged from old Ayuda and Sintaxis tabs)
        help_notebook = Gtk.Notebook()
        help_notebook.append_page(front_scrolled, Gtk.Label(label="Metadatos"))
        help_notebook.append_page(syntax_scrolled, Gtk.Label(label="Sintaxis"))

        # StackSidebar + Stack for section navigation
        self.main_stack = Gtk.Stack()
        self.main_stack.set_vexpand(True)
        self.main_stack.add_titled(self.content_notebook, "content", "Contenido")
        self.main_stack.add_titled(self._styles_scrolled, "styles", "Estilos")
        self.main_stack.add_titled(help_notebook, "help", "Ayuda")

        sidebar = Gtk.StackSidebar()
        sidebar.set_stack(self.main_stack)

        side_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        side_box.pack_start(sidebar, False, False, 0)
        side_box.pack_start(self.main_stack, True, True, 0)
        right_box.pack_start(side_box, True, True, 0)

        self.default_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body { font-family: Georgia, serif; margin: 2em; color: #333; line-height: 1.6; }
h1 { font-size: 1.8em; border-bottom: 2px solid #ccc; }
h2 { font-size: 1.4em; }
p { margin: 0.5em 0; }
pre { background: #f4f4f4; padding: 1em; border-radius: 4px; }
code { background: #f4f4f4; padding: 0.1em 0.3em; border-radius: 3px; }
img { max-width: 90%; display: block; margin: 1em auto; }
figure { margin: 1.5em 0; text-align: center; }
figcaption { font-style: italic; font-size: 0.9em; margin-top: 0.5em; color: #555; }
blockquote { border-left: 3px solid #ccc; margin: 1em 0; padding-left: 1em; color: #555; }
hr { border: none; border-top: 1px solid #ccc; }
</style></head><body>
<p style="color:#999;text-align:center;margin-top:4em;">Vista previa del contenido Markdown</p>
</body></html>"""
        self.webview.load_html(self.default_html, self._get_base_uri())

        self.text_view.get_buffer().connect("changed", self._on_text_changed)

    def _setup_statusbar(self, container):
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        status_box.set_margin_top(4)
        status_box.set_margin_bottom(4)
        status_box.set_margin_start(8)
        status_box.set_margin_end(8)
        container.pack_start(status_box, False, False, 0)

        self.status_label = Gtk.Label(label="Listo")
        self.status_label.set_xalign(0)
        self.status_label.set_hexpand(True)
        status_box.pack_start(self.status_label, True, True, 0)

        self.project_label = Gtk.Label(label="")
        self.project_label.set_xalign(1)
        status_box.pack_end(self.project_label, False, False, 0)

    def _build_styles_panel(self):
        self._styles_scrolled = Gtk.ScrolledWindow()
        self._styles_scrolled.set_vexpand(True)

        styles_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        styles_vbox.set_margin_top(8)
        styles_vbox.set_margin_bottom(8)
        styles_vbox.set_margin_start(8)
        styles_vbox.set_margin_end(8)

        header = Gtk.Label()
        header.set_xalign(0)
        header.get_style_context().add_class("heading")
        styles_vbox.pack_start(header, False, False, 0)

        hierarchy_label = Gtk.Label(label="Jerarquia de estilos — los de abajo sobreescriben")
        hierarchy_label.set_xalign(0)
        styles_vbox.pack_start(hierarchy_label, False, False, 0)

        self._theme_frame = Gtk.Frame()
        self._theme_frame_label = Gtk.Label()
        self._theme_frame_label.set_use_markup(True)
        self._theme_frame.set_label_widget(self._theme_frame_label)
        theme_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        theme_inner.set_margin_top(6)
        theme_inner.set_margin_bottom(6)
        theme_inner.set_margin_start(8)
        theme_inner.set_margin_end(8)
        self._theme_box = theme_inner
        self._theme_frame.add(theme_inner)
        styles_vbox.pack_start(self._theme_frame, False, False, 0)

        self._project_frame = Gtk.Frame()
        self._project_frame_label = Gtk.Label()
        self._project_frame_label.set_use_markup(True)
        self._project_frame.set_label_widget(self._project_frame_label)
        project_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        project_inner.set_margin_top(6)
        project_inner.set_margin_bottom(6)
        project_inner.set_margin_start(8)
        project_inner.set_margin_end(8)
        self._project_box = project_inner
        self._project_frame.add(project_inner)
        styles_vbox.pack_start(self._project_frame, False, False, 0)

        self._comp_frame = Gtk.Frame()
        self._comp_frame_label = Gtk.Label()
        self._comp_frame_label.set_use_markup(True)
        self._comp_frame.set_label_widget(self._comp_frame_label)
        comp_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        comp_inner.set_margin_top(6)
        comp_inner.set_margin_bottom(6)
        comp_inner.set_margin_start(8)
        comp_inner.set_margin_end(8)
        self._comp_box = comp_inner
        self._comp_frame.add(comp_inner)
        styles_vbox.pack_start(self._comp_frame, False, False, 0)

        css_header = Gtk.Label(label="Clases CSS disponibles")
        css_header.set_xalign(0)
        css_header.get_style_context().add_class("heading")
        styles_vbox.pack_start(css_header, False, False, 0)

        self._css_store = Gtk.ListStore(str, str, str)
        self._css_tree = Gtk.TreeView(model=self._css_store)
        self._css_tree.set_headers_visible(True)

        r_sel = Gtk.CellRendererText()
        r_sel.set_property("family", "Monospace")
        col_sel = Gtk.TreeViewColumn("Selector", r_sel, text=0)
        col_sel.set_resizable(True)
        col_sel.set_expand(True)
        self._css_tree.append_column(col_sel)

        r_desc = Gtk.CellRendererText()
        r_desc.set_property("wrap-mode", Pango.WrapMode.WORD_CHAR)
        r_desc.set_property("wrap-width", 250)
        col_desc = Gtk.TreeViewColumn("Descripcion", r_desc, text=1)
        col_desc.set_resizable(True)
        col_desc.set_expand(True)
        self._css_tree.append_column(col_desc)

        r_origin = Gtk.CellRendererText()
        col_origin = Gtk.TreeViewColumn("Origen", r_origin, text=2)
        col_origin.set_resizable(True)
        self._css_tree.append_column(col_origin)

        css_scrolled = Gtk.ScrolledWindow()
        css_scrolled.set_vexpand(True)
        css_scrolled.set_min_content_height(130)
        css_scrolled.add(self._css_tree)
        styles_vbox.pack_start(css_scrolled, True, True, 0)

        btn_box = Gtk.Box(spacing=6)
        btn_box.set_margin_top(6)

        theme_mgr_btn = Gtk.Button(label="Gestor de temas...")
        theme_mgr_btn.connect("clicked", self._on_theme_manager)
        btn_box.pack_start(theme_mgr_btn, False, False, 0)

        manage_btn = Gtk.Button(label="Gestionar todos los tipos...")
        manage_btn.connect("clicked", self._on_manage_type_css)
        btn_box.pack_start(manage_btn, False, False, 0)

        styles_vbox.pack_start(btn_box, False, False, 0)

        self._styles_scrolled.add(styles_vbox)

    def _get_theme_dir(self) -> str:
        return ThemeService.get_theme_path(self.project.theme_id) or ""

    def _load_theme_config(self) -> dict:
        theme_dir = self._get_theme_dir()
        if not theme_dir:
            return {}
        theme_yaml = os.path.join(theme_dir, "theme.yaml")
        if os.path.exists(theme_yaml):
            return YamlService.load(theme_yaml)
        return {}

    def _load_theme_css(self, component_type=None) -> str:
        css = ""
        if not self.project or not self.project.theme_id:
            return css

        theme_dir = self._get_theme_dir()
        if not theme_dir:
            return css

        # Level 1: Theme base
        style_path = os.path.join(theme_dir, "style.css")
        if os.path.exists(style_path):
            with open(style_path, "r") as f:
                css = f.read()

        # Level 1: Theme component CSS
        if component_type is not None:
            theme_config = self._load_theme_config()
            component_styles = theme_config.get("styles", {})
            comp_style_file = component_styles.get(component_type.value)
            if comp_style_file:
                comp_style_path = os.path.join(theme_dir, comp_style_file)
                if os.path.exists(comp_style_path):
                    with open(comp_style_path, "r") as f:
                        css += "\n" + f.read()

        # Level 2: Book-level custom CSS
        if self.project.custom_css:
            css += "\n" + self.project.custom_css

        # Level 3: Type-level CSS override
        if component_type is not None:
            type_css = self.project.type_css_overrides.get(component_type.value)
            if type_css:
                css += "\n" + type_css

        return css

    def _ensure_style_doc_svc(self):
        if not hasattr(self, "_style_doc_svc") or self._style_doc_svc is None:
            theme_dir = self._get_theme_dir()
            if not theme_dir:
                theme_dir = str(ThemeService.BUILTIN_DIR / "classic")
            self._style_doc_svc = StyleDocService(theme_dir)
        return self._style_doc_svc

    def _init_syntax_help(self, buf):
        lines = [
            "Sintaxis Markdown",
            "",
            "— Texto —",
            "",
            "  *cursiva*                _cursiva_",
            "  **negrita**              __negrita__",
            "  ~~tachado~~              `codigo`",
            "  > cita                   > cita anidada",
            "",
            "— Encabezados —",
            "",
            "  # Titulo                 ## Seccion",
            "  ### Subseccion           #### Sub-sub",
            "",
            "— Enlaces e imagenes —",
            "",
            "  [Texto](url)             [Texto](url \"Titulo\")",
            "  ![Alt](ruta/imagen.jpg)",
            "",
            "— Listas —",
            "",
            "  - item                   * item",
            "    - subitem",
            "  1. numerada              1) numerada",
            "",
            "— Separador —",
            "",
            "  ---                      ***",
            "",
            "Extensiones activas",
            "",
            "— Tablas —  (tables)",
            "",
            "  | Col A | Col B | Col C |",
            "  |-------|-------|-------|",
            "  | a     | b     | c     |",
            "",
            "  * Alineacion con :   |:---|:---:|---:|",
            "",
            "— Bloque de codigo —  (fenced_code + codehilite)",
            "",
            "  ```python",
            "  def hola():",
            "      print(\"Hola\")",
            "  ```",
            "",
            "  * Lenguajes: python, js, html, css, bash, json, yaml...",
            "  * Resaltado con Pygments en el EPUB exportado.",
            "",
            "— Listas de definicion —  (def_list)",
            "",
            "  Termino",
            "  : Definicion del termino.",
            "  : Parrafo adicional de la definicion.",
            "",
            "— Atributos CSS —  (attr_list)",
            "",
            "  {.clase}                 → <elemento class=\"clase\">",
            "  {.c1 .c2}                → varias clases",
            "  {#id-unico}              → ancla con id",
            "",
            "  * Se coloca en la linea siguiente al elemento.",
            "  * Clases disponibles segun el tema activo.",
            "",
            "— Notas al pie —  (footnotes)",
            "",
            "  Texto con nota[^1] y otra nota[^2].",
            "",
            "  [^1]: Contenido de la primera nota.",
            "  [^2]: Contenido de la segunda nota.",
            "",
            "  * Se numeran automaticamente por componente.",
            "  * Se recogen al final en el componente Notas al pie.",
            "",
            "— Tabla de contenidos —  (toc)",
            "",
            "  [TOC]",
            "",
            "  * Genera un indice local dentro del propio componente.",
            "",
            "— Saltos de linea —  (estandar CommonMark)",
            "",
            "  * Una linea en blanco entre bloques de texto",
            "    crea un nuevo parrafo.",
            "  * Un salto de linea simple une el texto en",
            "    el mismo parrafo (soft break).",
            "  * Dos espacios al final de una linea + salto",
            "    de linea crea un <br> explicito (hard break).",
            "  * Barra invertida al final de una linea +",
            "    salto de linea tambien crea un hard break.",
            "",
            "Sintaxis personalizada",
            "",
            "— Tablas con titulo —",
            "",
            "  <!-- Table: Mi tabla de datos -->",
            "  | A | B |",
            "  |---|---|",
            "  | 1 | 2 |",
            "",
            "  * Aparecen en la Lista de Tablas si se activa",
            "    la numeracion en Configuracion del proyecto.",
            "  * Tablas sin comentario no se numeran ni listan.",
            "",
            "— Figuras numerables —",
            "",
            "  ![Pie de figura](images/illustrations/foto.jpg)",
            "",
            "  * Las imagenes en images/illustrations/ se numeran",
            "    automaticamente y aparecen en la Lista de Figuras.",
            "",
            "— Imagenes decorativas —",
            "",
            "  ![Alt](images/decorative/ornamento.jpg)",
            "",
            "  * Quedan fuera de la numeracion y de la LOF.",
            "  * Aun asi obtienen <figure> con alt como caption.",
            "",
            "— Idioma del corrector —",
            "",
            "  {lang=en}This text is in English.{lang=es}",
            "",
            "  * Cambia el idioma del corrector ortografico.",
            "  * Los marcadores se eliminan del EPUB.",
            "",
            "— Metadatos del componente —  (frontmatter)",
            "",
            "  ---",
            "  show_title: false",
            "  toc_deep: 2",
            "  ---",
            "",
            "  * En YAML, entre --- al inicio del archivo.",
            "  * Variables comunes: show_title, toc_deep,",
            "    toc_include, split_title.",
            "",
            "— Variables del proyecto —  (interpolacion)",
            "",
            "  {{title}}       {{subtitle}}",
            "  {{author}}      {{publisher}}",
            "  {{isbn}}        {{edition}}",
            "  {{publication_date}}",
            "  {{publication_date:year}}",
            "",
            "  * Se sustituyen por los valores de la configuracion",
            "    del proyecto (Archivo → Configuracion).",
            "  * {{publication_date:year}} extrae solo el año",
            "    (ej: 2025-01-15 → 2025).",
            "  * Los campos no definidos quedan como {{clave}}.",
        ]
        buf.set_text("\n".join(lines))

    def _update_styles_panel(self, component_type=None):
        """Refreshes the Styles panel: hierarchy and CSS classes table."""

        # Frontmatter tab (still needed for Ayuda → Metadatos)
        front_buf = self.front_textview.get_buffer()
        if not self.project or component_type is None:
            front_buf.set_text(
                "Selecciona un componente para ver los metadatos.\n\n"
                "Consejos de sintaxis Markdown:\n"
                "  — Usa {.clase} para aplicar una clase CSS.\n"
                "  — Usa <!-- Table: titulo --> antes de una tabla para\n"
                "    asignarle un titulo y que aparezca en la Lista de Tablas.\n"
                "  — Usa ![alt](ruta) para imagenes. Las imagenes en\n"
                "    images/illustrations/ se numeran automaticamente.\n"
                "  — Usa {lang=en} para cambiar idioma del corrector."
            )
        else:
            comp_label = self._resolve_labels().get(component_type.value, COMPONENT_TYPE_LABELS.get(component_type, component_type.value))
            type_key = component_type.value
            fm_lines = [
                f"Metadatos para {comp_label}:",
                "",
            ]
            type_vars = FRONTMATTER_DOCS.get(type_key, [])
            type_names = {v[0] for v in type_vars}
            common_vars = [v for v in FRONTMATTER_COMMON if v[0] not in type_names]
            vars_list = type_vars + common_vars
            for var_name, description in vars_list:
                fm_lines.append(f"  {var_name}")
                fm_lines.append(f"    {description}")
                fm_lines.append("")
            fm_lines.append("Los metadatos se añaden al principio del componente")
            fm_lines.append("(entre las lineas --- al inicio del archivo).")
            front_buf.set_text("\n".join(fm_lines))

        # Styles panel
        self._styles_current_comp_type = component_type
        theme_config = self._load_theme_config()
        svc = self._ensure_style_doc_svc()

        # Clear dynamic widgets in hierarchy frames
        for child in self._theme_box.get_children():
            self._theme_box.remove(child)
        for child in self._project_box.get_children():
            self._project_box.remove(child)
        for child in self._comp_box.get_children():
            self._comp_box.remove(child)

        project_opened = self.project is not None
        theme_name = ""
        theme_dir = ""
        theme_is_builtin = True
        if project_opened:
            theme_dir = self._get_theme_dir()
            theme = ThemeService.get_theme(self.project.theme_id)
            if theme:
                theme_name = theme.name
                theme_is_builtin = theme.is_builtin

        # --- THEME FRAME ---
        if project_opened and theme_dir:
            theme_scope = "compartido entre todos los libros con este tema"
            self._theme_frame_label.set_markup(
                f"<b>Tema: {theme_name}</b>  <small>({theme_scope})</small>"
            )
            self._theme_frame.set_visible(True)

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            row.pack_start(Gtk.Label(label="Base: style.css", xalign=0), True, True, 0)
            if theme_is_builtin:
                btn = Gtk.Button(label="Ver")
                btn.set_tooltip_text("Solo lectura — los temas integrados no se editan")
            else:
                btn = Gtk.Button(label="Editar")
                btn.set_tooltip_text("Atencion: los cambios afectaran a TODOS los libros que usen este tema")
            btn.connect("clicked", lambda b: self._on_view_theme_css_by_file("style.css", theme_name))
            row.pack_start(btn, False, False, 0)
            self._theme_box.pack_start(row, False, False, 0)

            if component_type is not None:
                type_value = component_type.value
                type_file = theme_config.get("styles", {}).get(type_value, "")
                type_label = self._resolve_labels().get(component_type.value, COMPONENT_TYPE_LABELS.get(component_type, type_value))
                if type_file:
                    row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                    row2.pack_start(Gtk.Label(label=f"Tipo {type_label}: {type_file}", xalign=0), True, True, 0)
                    btn2 = Gtk.Button(label="Ver" if theme_is_builtin else "Editar")
                    if theme_is_builtin:
                        btn2.set_tooltip_text("Solo lectura — los temas integrados no se editan")
                    else:
                        btn2.set_tooltip_text("Atencion: los cambios afectaran a TODOS los libros que usen este tema")
                    btn2.connect("clicked", lambda b, f=type_file: self._on_view_theme_css_by_file(f, theme_name))
                    row2.pack_start(btn2, False, False, 0)
                    self._theme_box.pack_start(row2, False, False, 0)
        else:
            self._theme_frame.set_visible(False)

        # --- PROJECT FRAME ---
        if project_opened:
            self._project_frame_label.set_markup(
                f"<b>Proyecto: {self.project.title}</b>  <small>(solo este libro)</small>"
            )
            self._project_frame.set_visible(True)

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            status = "Editado" if self.project.custom_css.strip() else "Sin cambios"
            row.pack_start(Gtk.Label(label="Estilos globales", xalign=0), True, True, 0)
            status_lbl = Gtk.Label(label=status, xalign=0)
            row.pack_start(status_lbl, False, False, 0)
            btn = Gtk.Button(label="Editar")
            btn.connect("clicked", self._on_edit_book_css)
            row.pack_start(btn, False, False, 0)
            self._project_box.pack_start(row, False, False, 0)

            if component_type is not None:
                type_value = component_type.value
                type_label = self._resolve_labels().get(component_type.value, COMPONENT_TYPE_LABELS.get(component_type, type_value))
                has_override = type_value in self.project.type_css_overrides
                row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                row2.pack_start(Gtk.Label(label=f"Tipo: {type_label}", xalign=0), True, True, 0)
                status2 = Gtk.Label(label="Editado" if has_override else "Sin cambios", xalign=0)
                row2.pack_start(status2, False, False, 0)
                btn2 = Gtk.Button(label="Editar")
                btn2.connect("clicked", lambda b, ct=component_type: self._on_styles_edit_type_css(ct))
                row2.pack_start(btn2, False, False, 0)
                if has_override:
                    reset_btn = Gtk.Button(label="Restablecer")
                    reset_btn.connect("clicked", lambda b, ct=component_type: self._on_styles_reset_type_css(ct))
                    row2.pack_start(reset_btn, False, False, 0)
                self._project_box.pack_start(row2, False, False, 0)
        else:
            self._project_frame.set_visible(False)

        # --- COMPONENT FRAME ---
        if self._styles_current_component and component_type is not None:
            comp = self._styles_current_component
            self._comp_frame_label.set_markup(
                f"<b>Componente: {comp.get_display_name(self._resolve_labels())}</b>  <small>(solo este componente)</small>"
            )
            self._comp_frame.set_visible(True)

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            has_comp_css = bool(comp.custom_css.strip())
            row.pack_start(Gtk.Label(label="Estilos del componente", xalign=0), True, True, 0)
            status = Gtk.Label(label="Editado" if has_comp_css else "Sin cambios", xalign=0)
            row.pack_start(status, False, False, 0)
            btn = Gtk.Button(label="Editar")
            btn.connect("clicked", self._on_styles_edit_comp_css)
            row.pack_start(btn, False, False, 0)
            self._comp_box.pack_start(row, False, False, 0)
        else:
            self._comp_frame.set_visible(False)

        # --- CSS CLASSES TABLE ---
        self._css_store.clear()
        if project_opened and svc:
            all_docs = []

            theme_global = svc.get_docs("style.css")
            for d in theme_global:
                all_docs.append((d["markdown_hint"], d["description"], f"Tema ({theme_name or 'desconocido'})"))

            if component_type is not None:
                theme_type_docs = svc.get_docs_for_type(component_type, theme_config)
                for d in theme_type_docs:
                    all_docs.append((d["markdown_hint"], d["description"], f"Tema ({theme_name or 'desconocido'}) — tipo"))

            if self.project.custom_css:
                book_docs = svc.get_docs_from_css(self.project.custom_css)
                for d in book_docs:
                    all_docs.append((d["markdown_hint"], d["description"], "Proyecto (libro)"))

            if component_type is not None:
                type_css = self.project.type_css_overrides.get(component_type.value, "")
                if type_css:
                    type_docs = svc.get_docs_from_css(type_css)
                    for d in type_docs:
                        all_docs.append((d["markdown_hint"], d["description"], f"Proyecto (tipo)"))

            if self._styles_current_component and self._styles_current_component.custom_css:
                comp_docs = svc.get_docs_from_css(self._styles_current_component.custom_css)
                for d in comp_docs:
                    all_docs.append((d["markdown_hint"], d["description"], "Componente"))

            for selector, desc, origin in all_docs:
                self._css_store.append([selector, desc, origin])

        self._styles_scrolled.show_all()

    def _on_styles_edit_type_css(self, component_type):
        ct = component_type
        type_key = ct.value
        current = self.project.type_css_overrides.get(type_key, "")
        label = self._resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct])
        css = self._edit_css_dialog(f"Estilos del tipo: {label}", current, scope_type="type", scope_type_value=ct.value)
        if css is None:
            return
        if css.strip():
            self.project.type_css_overrides[type_key] = css
        else:
            self.project.type_css_overrides.pop(type_key, None)
        FileService.save_project(self.project)
        self._update_preview()
        self._update_styles_panel(ct)
        self._update_status(f"Estilos del tipo '{label}' actualizados")

    def _on_styles_reset_type_css(self, component_type):
        ct = component_type
        type_key = ct.value
        label = self._resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct])
        if type_key not in self.project.type_css_overrides:
            return
        if not self._confirm(f"Restablecer estilos del tipo «{label}»?\nSe perderan los cambios personalizados."):
            return
        del self.project.type_css_overrides[type_key]
        FileService.save_project(self.project)
        self._update_preview()
        self._update_styles_panel(ct)
        self._update_status(f"Estilos del tipo '{label}' restablecidos al tema")

    def _on_styles_edit_comp_css(self, btn):
        if not self._styles_current_component:
            return
        self._on_edit_component_css(btn, self._styles_current_component)

    def _on_view_theme_css_by_file(self, filename, theme_name=None):
        """Opens the theme CSS viewer/editor for a specific file within the current theme."""
        if not self.project:
            return
        theme_id = self.project.theme_id
        theme = ThemeService.get_theme(theme_id)
        if not theme:
            return
        theme_dir = theme.path
        fpath = os.path.join(theme_dir, filename)
        if not os.path.exists(fpath):
            self._show_info(f"El archivo {filename} no existe en el tema.")
            return

        with open(fpath, "r") as f:
            text = f.read()

        display_name = theme_name or theme.name
        is_read_only = theme.is_builtin
        mode_title = "Visualizar" if is_read_only else "Editar"

        editor_dialog = Gtk.Dialog(
            title=f"{mode_title} CSS: {display_name} — {filename}",
            transient_for=self.window,
            modal=True,
        )
        editor_dialog.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        if not is_read_only:
            editor_dialog.add_button("Guardar", Gtk.ResponseType.ACCEPT)
        editor_dialog.set_default_size(700, 500)

        editor_content = editor_dialog.get_content_area()
        editor_content.set_spacing(8)
        editor_content.set_margin_top(12)
        editor_content.set_margin_bottom(12)
        editor_content.set_margin_start(12)
        editor_content.set_margin_end(12)

        if not is_read_only:
            warning = Gtk.Label()
            warning.set_markup(
                "<b>Los cambios en este tema afectaran a TODOS los libros que lo usen.</b>"
            )
            warning.set_xalign(0)
            editor_content.pack_start(warning, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        buf = GtkSource.Buffer.new_with_language(
            GtkSource.LanguageManager.get_default().get_language("css")
        )
        text_view = GtkSource.View.new_with_buffer(buf)
        text_view.set_monospace(True)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_hexpand(True)
        text_view.set_vexpand(True)
        text_view.set_editable(not is_read_only)
        if is_read_only:
            text_view.set_cursor_visible(False)
        buf.set_text(text)
        scrolled.add(text_view)
        editor_content.pack_start(scrolled, True, True, 0)

        def on_editor_response(d, response):
            if response == Gtk.ResponseType.ACCEPT and not is_read_only:
                new_text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
                with open(fpath, "w") as f:
                    f.write(new_text)
                self._update_styles_panel(self._styles_current_comp_type)
                self._update_preview()
            d.destroy()

        editor_dialog.connect("response", on_editor_response)
        editor_dialog.show_all()

    def _update_spell_lang(self):
        """Update the default spell-check language from the current project."""
        if self.project:
            self.spell_service.default_lang = self.project.spell_lang
        self._run_spell_check()

    def _run_spell_check(self):
        self._spell_timer_id = 0
        buf = self.text_view.get_buffer()
        if not self.project or not self.project.path:
            return False

        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
        if not text:
            return False

        # Remove old misspelled tags
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        buf.remove_tag(self._spell_tag, start, end)

        # Run check
        project_words = set(self.project.spell_words) if self.project else set()
        all_ignored = project_words | self._session_ignored_words
        self._misspelled_words = self.spell_service.check_text(text, all_ignored)

        # Apply tags
        for w_start, w_end, word, lang in self._misspelled_words:
            try:
                it1 = buf.get_iter_at_offset(w_start)
                it2 = buf.get_iter_at_offset(w_end)
                buf.apply_tag(self._spell_tag, it1, it2)
            except Exception:
                pass

        return False

    def _on_spell_popup(self, textview, popup):
        buf = textview.get_buffer()
        cursor = buf.get_iter_at_mark(buf.get_insert())
        offset = cursor.get_offset()

        # Find if cursor is on a misspelled word
        for w_start, w_end, word, lang in self._misspelled_words:
            if w_start <= offset <= w_end:
                suggestions = self.spell_service.get_suggestions(word, lang)
                if suggestions:
                    sep = Gtk.SeparatorMenuItem()
                    sep.show()
                    popup.append(sep)

                    item = Gtk.MenuItem(label="Sugerencias ortográficas")
                    item.set_sensitive(False)
                    item.show()
                    popup.append(item)

                    for sug in suggestions[:10]:
                        def _replace(menu_item, s=sug, ws=w_start, we=w_end):
                            it1 = buf.get_iter_at_offset(ws)
                            it2 = buf.get_iter_at_offset(we)
                            buf.delete(it1, it2)
                            it = buf.get_iter_at_offset(ws)
                            buf.insert(it, s)
                        sug_item = Gtk.MenuItem(label=sug)
                        sug_item.connect("activate", _replace)
                        sug_item.show()
                        popup.append(sug_item)

                # Dictionary options
                sep2 = Gtk.SeparatorMenuItem()
                sep2.show()
                popup.append(sep2)

                def _ignore_word(*_a, w=word, ws=w_start, we=w_end):
                    self._session_ignored_words.add(w.lower())
                    it1 = buf.get_iter_at_offset(ws)
                    it2 = buf.get_iter_at_offset(we)
                    buf.remove_tag(self._spell_tag, it1, it2)
                    self._run_spell_check()

                item_ignore = Gtk.MenuItem(label="Ignorar palabra")
                item_ignore.connect("activate", _ignore_word)
                item_ignore.show()
                popup.append(item_ignore)

                def _add_book_word(*_a, w=word, ws=w_start, we=w_end):
                    if self.project:
                        self.project.spell_words.append(w.lower())
                        FileService.save_project(self.project)
                    it1 = buf.get_iter_at_offset(ws)
                    it2 = buf.get_iter_at_offset(we)
                    buf.remove_tag(self._spell_tag, it1, it2)
                    self._update_preview()

                item_book = Gtk.MenuItem(label="Añadir al diccionario del libro")
                item_book.connect("activate", _add_book_word)
                item_book.show()
                popup.append(item_book)

                def _add_global_word(*_a, w=word, ws=w_start, we=w_end):
                    self.spell_service.add_global_word(w)
                    if self.project:
                        self.project.spell_words.append(w.lower())
                    it1 = buf.get_iter_at_offset(ws)
                    it2 = buf.get_iter_at_offset(we)
                    buf.remove_tag(self._spell_tag, it1, it2)
                    self._update_preview()

                item_global = Gtk.MenuItem(label="Añadir al diccionario global")
                item_global.connect("activate", _add_global_word)
                item_global.show()
                popup.append(item_global)
                break

    def _get_base_uri(self) -> str:
        if self.project and self.project.path:
            return f"file://{self.project.path}/"
        return "file:///"

    def _build_preview_html(self, html_content: str, component_type=None, component=None) -> str:
        css = self._load_theme_css(component_type)
        # Level 2: Book-level CSS
        if self.project and self.project.custom_css:
            css += "\n" + self.project.custom_css
        # Level 3: Type-level CSS
        if (self.project and component_type is not None
                and component_type.value in self.project.type_css_overrides):
            css += "\n" + self.project.type_css_overrides[component_type.value]
        # Level 4: Per-component CSS
        if component and component.custom_css:
            css += "\n" + component.custom_css
        # Level 5: Pygments code syntax CSS
        css += "\n" + MarkdownService.get_code_css()
        css += """
.auto-notice {
    margin-top: 2em;
    padding: 0.8em 1em;
    border: 1px solid #ccc;
    border-radius: 6px;
    background: #f5f5f5;
    font-style: italic;
    color: #666;
    font-size: 0.9em;
}
"""
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{css}</style>
</head><body>
{html_content}
</body></html>"""

    def _focus_editor(self):
        self.main_stack.set_visible_child(self.content_notebook)
        self.content_notebook.set_current_page(0)

    def _focus_preview(self):
        self.main_stack.set_visible_child(self.content_notebook)
        self.content_notebook.set_current_page(1)

    def _update_preview(self):
        if not self.webview:
            return

        text = self._get_editor_text()
        component = self.current_component
        if not text.strip():
            if (self.project and component
                    and component.type
                    in (ComponentType.FOOTNOTES, ComponentType.TOC, ComponentType.LOF)):
                text = '\u200b'
            else:
                self.webview.load_html(self.default_html, self._get_base_uri())
                return

        if text.strip():
            component_id = ""
            if component:
                component_type = component.type
                component_id = component.id
            elif self.current_part:
                component_type = ComponentType.CHAPTER
            else:
                component_type = ComponentType.CHAPTER

            editor_fm, md_text = YamlService.parse_frontmatter(text)
            if component:
                component.frontmatter = editor_fm

            variables = {}
            if self.project:
                for k in ("title", "subtitle", "author", "isbn", "publisher",
                          "edition", "publication_date", "language"):
                    v = getattr(self.project, k, None)
                    if v:
                        variables[k] = v

            # Apply header and drop cap when project is loaded
            if self.project and component:
                from .services.epub_service import EpubService as _EpubService
                epub_svc = _EpubService(self.project)
                _, config_file = self._get_config_path()
                global_config = YamlService.load(config_file)
                epub_svc._resolve_labels(global_config)

                # Special handling for COVER with only one image
                if (component.type == ComponentType.COVER
                        and _EpubService._is_cover_only_image(md_text)):
                    img_info = _EpubService._extract_cover_image(md_text)
                    if img_info:
                        alt, src = img_info
                        preview_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body {{ margin:0; padding:0; height:100vh; display:flex; align-items:center; justify-content:center; }}
img {{ max-width:100%; max-height:100%; object-fit:contain; }}
</style>
</head><body>
<img src="{src}" alt="{alt}"/>
</body></html>"""
                        self.webview.load_html(preview_html, self._get_base_uri())
                        return
                chapter_number = None
                part_number = None
                if component.should_use_numbering():
                    ch_count = 0
                    ap_count = 0
                    for c in self.project.get_ordered_components():
                        if c.type == ComponentType.CHAPTER:
                            ch_count += 1
                        elif c.type == ComponentType.APPENDIX:
                            ap_count += 1
                        if c.id == component.id:
                            chapter_number = ch_count if component.type == ComponentType.CHAPTER else ap_count
                            break
                elif component.type == ComponentType.PART:
                    count = 0
                    for c in self.project.get_ordered_components():
                        if c.type == ComponentType.PART:
                            count += 1
                        if c.id == component.id:
                            part_number = count
                            break

                h1_match = re.search(r'^# (.+)$', md_text, re.MULTILINE)
                default_title = h1_match.group(1).strip() if h1_match else ""
                show_title = editor_fm.get("show_title", True)

                if component.type == ComponentType.PART:
                    num_part, title_part, _ = epub_svc._get_part_header(
                        component, part_number
                    )
                    replaces = self.project.auto_part_title in ("part_number", "number")
                else:
                    num_part, title_part, _ = epub_svc._get_component_header(
                        component, chapter_number
                    )
                    replaces = self.project.auto_chapter_title in ("chapter_number", "number")
                if show_title:
                    if default_title and not title_part and not replaces:
                        title_part = default_title
                    if default_title and title_part and default_title != component.title:
                        title_part = default_title

                subtitle_part = ""
                if title_part:
                    subtitle_part, title_part = _EpubService._split_title(
                        title_part, editor_fm
                    )

                header_html = epub_svc._build_header_html(num_part, subtitle_part, title_part)
                if header_html:
                    if h1_match:
                        md_text = md_text[:h1_match.start()] + md_text[h1_match.end():]
                        md_text = md_text.strip()
                    md_text = header_html + md_text
                elif not default_title and editor_fm.get("show_title", True):
                    display = component.title or epub_svc._labels.get(component.type.value, component.get_display_name())
                    md_text = f"# {display}\n\n{md_text}"

                html = self.md_service.render(md_text, component_type, component_id,
                                              variables=variables,
                                              labels=epub_svc._labels)

                if (self.project.drop_cap_enabled
                        and component_type.value in self.project.drop_cap_types):
                    html = epub_svc._apply_drop_cap(html)
            else:
                html = self.md_service.render(md_text, component_type, component_id,
                                              variables=variables)

            # Preview notices for auto-generated components
            if self.project and component:
                if component.type == ComponentType.FOOTNOTES:
                    html = html.replace(
                        '</section>',
                        '<div class="auto-notice">'
                        '<p>Aquí aparecerán automáticamente todas '
                        'las notas al pie del libro.</p>'
                        '</div>\n</section>',
                        1
                    )
                elif component.type == ComponentType.TOC:
                    html = html.replace(
                        '</section>',
                        '<div class="auto-notice">'
                        '<p>Aquí aparecerá automáticamente la '
                        'tabla de contenidos.</p>'
                        '</div>\n</section>',
                        1
                    )
                elif component.type == ComponentType.LOF:
                    html = html.replace(
                        '</section>',
                        '<div class="auto-notice">'
                        '<p>Aquí aparecerá automáticamente la '
                        'lista de figuras.</p>'
                        '</div>\n</section>',
                        1
                    )
                elif component.type == ComponentType.LOT:
                    html = html.replace(
                        '</section>',
                        '<div class="auto-notice">'
                        '<p>Aquí aparecerá automáticamente la '
                        'lista de tablas.</p>'
                        '</div>\n</section>',
                        1
                    )

            full_html = self._build_preview_html(html, component_type, component)
            self.webview.load_html(full_html, self._get_base_uri())
        else:
            self.webview.load_html(self.default_html, self._get_base_uri())

    def _get_editor_text(self) -> str:
        buffer = self.text_view.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        return buffer.get_text(start, end, True)

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

    # --- Dialogos de configuracion ---

    def _on_project_config(self, button):
        if not self.project:
            self._show_info("No hay proyecto abierto")
            return

        read_only = self._read_only

        dialog = Gtk.Dialog(
            title="Configuracion del Proyecto" + (" [SOLO LECTURA]" if read_only else ""),
            transient_for=self.window,
            modal=True,
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        if not read_only:
            dialog.add_button("Guardar", Gtk.ResponseType.ACCEPT)
        dialog.set_default_size(520, 420)

        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        if read_only:
            note_rw = Gtk.Label()
            note_rw.set_markup('<span foreground="#c00"><b>Este proyecto es de solo lectura. No se pueden guardar cambios.</b></span>')
            note_rw.set_xalign(0)
            content.pack_start(note_rw, False, False, 0)

        interactive_widgets = []

        notebook = Gtk.Notebook()
        content.add(notebook)

        # ── Tab 1: Book info ──
        grid_book = Gtk.Grid()
        grid_book.set_row_spacing(8)
        grid_book.set_column_spacing(12)
        grid_book.set_column_homogeneous(False)
        grid_book.set_margin_top(12)
        grid_book.set_margin_bottom(12)
        grid_book.set_margin_start(12)
        grid_book.set_margin_end(12)
        grid_book.set_vexpand(False)
        notebook.append_page(grid_book, Gtk.Label(label="Libro"))

        row = 0

        label = Gtk.Label(label="Titulo *:")
        label.set_xalign(1)
        grid_book.attach(label, 0, row, 1, 1)
        entry_title = Gtk.Entry()
        interactive_widgets.append(entry_title)
        entry_title.set_text(self.project.title)
        entry_title.set_hexpand(True)
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_box.pack_start(entry_title, True, True, 0)
        hint = Gtk.Label(label="{{title}}")
        hint.set_opacity(0.55)
        hint.set_tooltip_text("Usa {{title}} en el texto para insertar este valor")
        title_box.pack_start(hint, False, False, 0)
        grid_book.attach(title_box, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="Subtitulo *:")
        label.set_xalign(1)
        grid_book.attach(label, 0, row, 1, 1)
        entry_subtitle = Gtk.Entry()
        interactive_widgets.append(entry_subtitle)
        entry_subtitle.set_text(self.project.subtitle)
        entry_subtitle.set_hexpand(True)
        entry_subtitle.set_placeholder_text("Subtitulo del libro")
        sub_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        sub_box.pack_start(entry_subtitle, True, True, 0)
        hint = Gtk.Label(label="{{subtitle}}")
        hint.set_opacity(0.55)
        hint.set_tooltip_text("Usa {{subtitle}} en el texto para insertar este valor")
        sub_box.pack_start(hint, False, False, 0)
        grid_book.attach(sub_box, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="Archivo EPUB:")
        label.set_xalign(1)
        grid_book.attach(label, 0, row, 1, 1)
        entry_export = Gtk.Entry()
        interactive_widgets.append(entry_export)
        from .services.file_service import slugify
        def _update_export_filename(*_a):
            current = entry_export.get_text().strip()
            old_slug = slugify(entry_title.get_text().strip())
            if current and current != old_slug:
                return
            entry_export.set_text(slugify(entry_title.get_text().strip()))
        entry_title.connect("changed", _update_export_filename)
        if self.project.export_filename:
            entry_export.set_text(self.project.export_filename)
        else:
            entry_export.set_text(slugify(self.project.title or self.project.name))
        entry_export.set_hexpand(True)
        entry_export.set_placeholder_text(".epub")
        grid_book.attach(entry_export, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="Autor *:")
        label.set_xalign(1)
        grid_book.attach(label, 0, row, 1, 1)
        entry_author = Gtk.Entry()
        interactive_widgets.append(entry_author)
        entry_author.set_text(self.project.author)
        entry_author.set_hexpand(True)
        aut_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        aut_box.pack_start(entry_author, True, True, 0)
        hint = Gtk.Label(label="{{author}}")
        hint.set_opacity(0.55)
        hint.set_tooltip_text("Usa {{author}} en el texto para insertar este valor")
        aut_box.pack_start(hint, False, False, 0)
        grid_book.attach(aut_box, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="Idioma:")
        label.set_xalign(1)
        grid_book.attach(label, 0, row, 1, 1)
        entry_lang = Gtk.Entry()
        interactive_widgets.append(entry_lang)
        entry_lang.set_text(self.project.language)
        entry_lang.set_hexpand(True)
        entry_lang.set_placeholder_text("es")
        grid_book.attach(entry_lang, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="Version EPUB:")
        label.set_xalign(1)
        grid_book.attach(label, 0, row, 1, 1)
        combo_epub = Gtk.ComboBoxText()
        interactive_widgets.append(combo_epub)
        combo_epub.append_text("epub2")
        combo_epub.append_text("epub3")
        if self.project.epub_version == "epub2":
            combo_epub.set_active(0)
        else:
            combo_epub.set_active(1)
        grid_book.attach(combo_epub, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="Edicion *:")
        label.set_xalign(1)
        grid_book.attach(label, 0, row, 1, 1)
        entry_edicion = Gtk.Entry()
        interactive_widgets.append(entry_edicion)
        entry_edicion.set_text(self.project.edition)
        entry_edicion.set_hexpand(True)
        entry_edicion.set_placeholder_text("1ª edicion")
        edi_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        edi_box.pack_start(entry_edicion, True, True, 0)
        hint = Gtk.Label(label="{{edition}}")
        hint.set_opacity(0.55)
        hint.set_tooltip_text("Usa {{edition}} en el texto para insertar este valor")
        edi_box.pack_start(hint, False, False, 0)
        grid_book.attach(edi_box, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="Fecha de publicacion *:")
        label.set_xalign(1)
        grid_book.attach(label, 0, row, 1, 1)
        entry_fecha = Gtk.Entry()
        interactive_widgets.append(entry_fecha)
        entry_fecha.set_text(self.project.publication_date)
        entry_fecha.set_hexpand(True)
        entry_fecha.set_placeholder_text("2025-01-15")
        fec_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        fec_box.pack_start(entry_fecha, True, True, 0)
        hint = Gtk.Label(label="{{publication_date}}  {{publication_date:year}}")
        hint.set_opacity(0.55)
        hint.set_tooltip_text("Usa {{publication_date}} o {{publication_date:year}} (solo año) en el texto")
        fec_box.pack_start(hint, False, False, 0)
        grid_book.attach(fec_box, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="ISBN *:")
        label.set_xalign(1)
        grid_book.attach(label, 0, row, 1, 1)
        entry_isbn = Gtk.Entry()
        interactive_widgets.append(entry_isbn)
        entry_isbn.set_text(self.project.isbn)
        entry_isbn.set_hexpand(True)
        entry_isbn.set_placeholder_text("978-84-999-9999-9")
        isbn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        isbn_box.pack_start(entry_isbn, True, True, 0)
        hint = Gtk.Label(label="{{isbn}}")
        hint.set_opacity(0.55)
        hint.set_tooltip_text("Usa {{isbn}} en el texto para insertar este valor")
        isbn_box.pack_start(hint, False, False, 0)
        grid_book.attach(isbn_box, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="Editorial *:")
        label.set_xalign(1)
        grid_book.attach(label, 0, row, 1, 1)
        entry_editorial = Gtk.Entry()
        interactive_widgets.append(entry_editorial)
        entry_editorial.set_text(self.project.publisher)
        entry_editorial.set_hexpand(True)
        entry_editorial.set_placeholder_text("Ediciones Aprender")
        pub_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        pub_box.pack_start(entry_editorial, True, True, 0)
        hint = Gtk.Label(label="{{publisher}}")
        hint.set_opacity(0.55)
        hint.set_tooltip_text("Usa {{publisher}} en el texto para insertar este valor")
        pub_box.pack_start(hint, False, False, 0)
        grid_book.attach(pub_box, 1, row, 1, 1)
        row += 1

        note = Gtk.Label()
        note.set_markup(
            '<span size="small" foreground="#555">'
            '* Los campos marcados pueden insertarse en el texto '
            'usando <tt>{{nombre}}</tt>. Ejemplo: <tt>{{title}}</tt>, '
            '<tt>{{isbn}}</tt>, <tt>{{publisher}}</tt>.'
            '</span>'
        )
        note.set_xalign(0)
        note.set_line_wrap(True)
        grid_book.attach(note, 0, row, 2, 1)
        row += 1

        # ── Tab 2: Appearance ──
        grid_app = Gtk.Grid()
        grid_app.set_row_spacing(8)
        grid_app.set_column_spacing(12)
        grid_app.set_column_homogeneous(False)
        grid_app.set_margin_top(12)
        grid_app.set_margin_bottom(12)
        grid_app.set_margin_start(12)
        grid_app.set_margin_end(12)
        notebook.append_page(grid_app, Gtk.Label(label="Apariencia"))

        row = 0

        label = Gtk.Label(label="Titulo auto de componentes:")
        label.set_xalign(1)
        grid_app.attach(label, 0, row, 1, 1)
        combo_auto_title = Gtk.ComboBoxText()
        interactive_widgets.append(combo_auto_title)
        combo_auto_title.append_text("No")
        combo_auto_title.append_text("Capitulo <n>")
        combo_auto_title.append_text("<n>")
        combo_auto_title.append_text("Capitulo <n> + titulo")
        combo_auto_title.append_text("<n> + titulo")
        auto_title_values = ["none", "chapter_number", "number", "chapter_number_with_title", "number_with_title"]
        auto_title_index = 0
        for i, v in enumerate(auto_title_values):
            if v == self.project.auto_chapter_title:
                auto_title_index = i
                break
        combo_auto_title.set_active(auto_title_index)
        grid_app.attach(combo_auto_title, 1, row, 1, 1)
        row += 1

        label_part = Gtk.Label(label="Titulo auto de partes:")
        label_part.set_xalign(1)
        grid_app.attach(label_part, 0, row, 1, 1)
        combo_auto_part = Gtk.ComboBoxText()
        interactive_widgets.append(combo_auto_part)
        combo_auto_part.append_text("No")
        combo_auto_part.append_text("Parte <n>")
        combo_auto_part.append_text("<n>")
        combo_auto_part.append_text("Parte <n> + titulo")
        combo_auto_part.append_text("<n> + titulo")
        auto_part_values = ["none", "part_number", "number", "part_number_with_title", "number_with_title"]
        auto_part_index = 0
        for i, v in enumerate(auto_part_values):
            if v == self.project.auto_part_title:
                auto_part_index = i
                break
        combo_auto_part.set_active(auto_part_index)
        grid_app.attach(combo_auto_part, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="Tema:")
        label.set_xalign(1)
        grid_app.attach(label, 0, row, 1, 1)

        themes_list = ThemeService.list_themes()
        available_themes = [(t.id, t.name) for t in themes_list]

        combo_theme = Gtk.ComboBoxText()
        interactive_widgets.append(combo_theme)
        theme_index = 0
        for i, (tid, tname) in enumerate(available_themes):
            combo_theme.append_text(tname)
            if tid == self.project.theme_id:
                theme_index = i
        combo_theme.set_active(theme_index)
        grid_app.attach(combo_theme, 1, row, 1, 1)
        row += 1

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        grid_app.attach(sep, 0, row, 2, 1)
        row += 1

        label = Gtk.Label(label="Letra capitular:")
        label.set_xalign(1)
        label.set_valign(Gtk.Align.START)
        grid_app.attach(label, 0, row, 1, 1)

        right_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        grid_app.attach(right_vbox, 1, row, 1, 1)
        row += 1

        check_drop_cap = Gtk.CheckButton(label="Activar")
        interactive_widgets.append(check_drop_cap)
        check_drop_cap.set_active(self.project.drop_cap_enabled)
        right_vbox.pack_start(check_drop_cap, False, False, 0)

        label_cap_types = Gtk.Label(label="Tipos con capitular:", xalign=0)
        right_vbox.pack_start(label_cap_types, False, False, 0)

        type_list = Gtk.ListBox()
        type_list.set_selection_mode(Gtk.SelectionMode.NONE)
        type_list.set_vexpand(True)
        type_list.set_hexpand(True)

        from .models.component import ComponentType, COMPONENT_TYPE_LABELS
        skip_types = {ComponentType.PART, ComponentType.TOC, ComponentType.COVER,
                      ComponentType.TITLE, ComponentType.LICENSE, ComponentType.FOOTNOTES}
        self._drop_cap_checkbuttons = {}
        for ct in ComponentType:
            if ct in skip_types:
                continue
            label_text = self._resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS.get(ct, ct.value))
            cb = Gtk.CheckButton(label=label_text)
            cb.set_active(ct.value in self.project.drop_cap_types)
            self._drop_cap_checkbuttons[ct.value] = cb
            type_list.add(cb)

        sw = Gtk.ScrolledWindow()
        sw.set_min_content_height(200)
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.add(type_list)
        right_vbox.pack_start(sw, True, True, 0)

        # Separator
        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        grid_app.attach(sep2, 0, row, 2, 1)
        row += 1

        # ── Figure numbering ──
        label_fig = Gtk.Label(label="Numeracion de figuras:")
        label_fig.set_xalign(1)
        label_fig.set_valign(Gtk.Align.START)
        grid_app.attach(label_fig, 0, row, 1, 1)

        fig_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        grid_app.attach(fig_vbox, 1, row, 1, 1)
        row += 1

        check_figure_numbering = Gtk.CheckButton(label="Numerar figuras automaticamente")
        interactive_widgets.append(check_figure_numbering)
        check_figure_numbering.set_active(self.project.figure_numbering)
        fig_vbox.pack_start(check_figure_numbering, False, False, 0)

        fig_style_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        fig_style_label = Gtk.Label(label="Estilo:")
        fig_style_box.pack_start(fig_style_label, False, False, 0)
        combo_fig_style = Gtk.ComboBoxText()
        interactive_widgets.append(combo_fig_style)
        combo_fig_style.append_text("Numeros arabigos")
        combo_fig_style.append_text("Numeros romanos")
        fig_style_values = ["arabic", "roman"]
        fig_style_index = 0
        for i, v in enumerate(fig_style_values):
            if v == self.project.figure_numbering_style:
                fig_style_index = i
                break
        combo_fig_style.set_active(fig_style_index)
        fig_style_box.pack_start(combo_fig_style, False, False, 0)
        fig_vbox.pack_start(fig_style_box, False, False, 0)

        # Toggle style combo sensitivity based on checkbox
        def _on_fig_numbering_toggle(cb):
            combo_fig_style.set_sensitive(cb.get_active())
        check_figure_numbering.connect("toggled", _on_fig_numbering_toggle)
        _on_fig_numbering_toggle(check_figure_numbering)

        sep3 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        grid_app.attach(sep3, 0, row, 2, 1)
        row += 1

        # ── Table numbering ──
        label_tab = Gtk.Label(label="Numeracion de tablas:")
        label_tab.set_xalign(1)
        label_tab.set_valign(Gtk.Align.START)
        grid_app.attach(label_tab, 0, row, 1, 1)

        tab_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        grid_app.attach(tab_vbox, 1, row, 1, 1)
        row += 1

        check_table_numbering = Gtk.CheckButton(label="Numerar tablas automaticamente")
        interactive_widgets.append(check_table_numbering)
        check_table_numbering.set_active(self.project.table_numbering)
        tab_vbox.pack_start(check_table_numbering, False, False, 0)

        tab_style_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        tab_style_label = Gtk.Label(label="Estilo:")
        tab_style_box.pack_start(tab_style_label, False, False, 0)
        combo_tab_style = Gtk.ComboBoxText()
        interactive_widgets.append(combo_tab_style)
        combo_tab_style.append_text("Numeros arabigos")
        combo_tab_style.append_text("Numeros romanos")
        tab_style_values = ["arabic", "roman"]
        tab_style_index = 0
        for i, v in enumerate(tab_style_values):
            if v == self.project.table_numbering_style:
                tab_style_index = i
                break
        combo_tab_style.set_active(tab_style_index)
        tab_style_box.pack_start(combo_tab_style, False, False, 0)
        tab_vbox.pack_start(tab_style_box, False, False, 0)

        def _on_tab_numbering_toggle(cb):
            combo_tab_style.set_sensitive(cb.get_active())
        check_table_numbering.connect("toggled", _on_tab_numbering_toggle)
        _on_tab_numbering_toggle(check_table_numbering)

        sep4 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        grid_app.attach(sep4, 0, row, 2, 1)
        row += 1

        # ── Spell check language ──
        label_lang = Gtk.Label(label="Corrector ortografico:")
        label_lang.set_xalign(1)
        grid_app.attach(label_lang, 0, row, 1, 1)

        combo_lang = Gtk.ComboBoxText()
        interactive_widgets.append(combo_lang)
        langs = self.spell_service.get_language_list()
        lang_index = 0
        for i, l in enumerate(langs):
            combo_lang.append_text(l)
            if l == self.project.spell_lang:
                lang_index = i
        combo_lang.set_active(lang_index)
        combo_lang.set_hexpand(True)
        grid_app.attach(combo_lang, 1, row, 1, 1)
        row += 1

        # ── Tab 3: Labels ──
        from .services.labels_service import DEFAULT_LABELS

        labels_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        labels_page.set_margin_top(12)
        labels_page.set_margin_bottom(12)
        labels_page.set_margin_start(12)
        labels_page.set_margin_end(12)
        notebook.append_page(labels_page, Gtk.Label(label="Etiquetas"))

        _, config_file = self._get_config_path()
        global_cfg = YamlService.load(config_file) or {}
        global_labels = global_cfg.get("labels", {})
        label_keys = [k for k in DEFAULT_LABELS.get("es", {})]

        def _build_labels_page(lang_code):
            for child in labels_page.get_children():
                labels_page.remove(child)

            top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            top_row.pack_start(Gtk.Label(label="Idioma:", xalign=0), False, False, 0)

            combo_label_lang = Gtk.ComboBoxText()
            for lang in sorted(set(list(DEFAULT_LABELS.keys()) + list(global_labels.keys()))):
                combo_label_lang.append_text(lang)
            top_row.pack_start(combo_label_lang, False, False, 0)

            btn_new_lang = Gtk.Button(label="Nuevo idioma...")
            interactive_widgets.append(btn_new_lang)
            top_row.pack_start(btn_new_lang, False, False, 0)

            btn_reset = Gtk.Button(label="Restablecer predeterminados")
            interactive_widgets.append(btn_reset)
            top_row.pack_start(btn_reset, False, False, 0)
            top_row.pack_start(Gtk.Label(label=""), True, True, 0)

            labels_page.pack_start(top_row, False, False, 0)

            grid = Gtk.Grid()
            grid.set_row_spacing(4)
            grid.set_column_spacing(8)
            grid.set_hexpand(True)

            scrolled = Gtk.ScrolledWindow()
            scrolled.set_vexpand(True)
            scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scrolled.add(grid)
            labels_page.pack_start(scrolled, True, True, 0)

            def _populate_grid(current_lang):
                for child in grid.get_children():
                    grid.remove(child)

                defaults = DEFAULT_LABELS.get(current_lang, {})
                current = dict(defaults)
                current.update(global_labels.get(current_lang, {}))

                note = Gtk.Label(
                    label="Estas etiquetas sustituyen los nombres de tipos de "
                          "componente (p.ej. \"Capitulo\", \"Tabla de contenidos\") "
                          "en el arbol y en el EPUB cuando el componente no tiene titulo."
                )
                note.set_line_wrap(True)
                note.set_xalign(0)
                note.set_margin_bottom(8)
                grid.attach(note, 0, 0, 2, 1)

                row_idx = 1
                for key in label_keys:
                    lbl = Gtk.Label(label=f"{key}:")
                    lbl.set_xalign(1)
                    grid.attach(lbl, 0, row_idx, 1, 1)
                    entry = Gtk.Entry()
                    entry.set_text(current.get(key, ""))
                    entry.set_hexpand(True)
                    entry.connect("changed", lambda e, k=key, l=current_lang:
                                  global_labels.setdefault(l, {}).__setitem__(
                                      k, e.get_text()))
                    grid.attach(entry, 1, row_idx, 1, 1)
                    row_idx += 1
                grid.show_all()

            def _on_lang_changed(combo):
                new_lang = combo.get_active_text()
                if new_lang:
                    _populate_grid(new_lang)

            def _on_new_lang(btn):
                dlg = Gtk.Dialog(
                    title="Nuevo idioma",
                    transient_for=dialog,
                    modal=True,
                )
                dlg.add_button("Cancelar", Gtk.ResponseType.CANCEL)
                dlg.add_button("Crear", Gtk.ResponseType.ACCEPT)
                c = dlg.get_content_area()
                c.set_spacing(8)
                c.set_margin_top(8)
                c.set_margin_bottom(8)
                c.set_margin_start(8)
                c.set_margin_end(8)

                c.pack_start(Gtk.Label(label="Codigo de idioma (ej. fr, de, it):"), False, False, 0)
                code_entry = Gtk.Entry()
                c.pack_start(code_entry, False, False, 0)

                c.pack_start(Gtk.Label(label="Copiar etiquetas de:"), False, False, 0)
                src_combo = Gtk.ComboBoxText()
                for lang in sorted(set(list(DEFAULT_LABELS.keys()) + list(global_labels.keys()))):
                    src_combo.append_text(lang)
                current_lang = combo_label_lang.get_active_text()
                src_combo.set_active(0)
                c.pack_start(src_combo, False, False, 0)

                dlg.show_all()
                if dlg.run() == Gtk.ResponseType.ACCEPT:
                    new_code = code_entry.get_text().strip()
                    src_lang = src_combo.get_active_text()
                    if new_code and src_lang:
                        defaults = DEFAULT_LABELS.get(src_lang, {})
                        custom = global_labels.get(src_lang, {})
                        global_labels[new_code] = dict(defaults)
                        global_labels[new_code].update(custom)
                        combo_label_lang.append_text(new_code)
                        combo_label_lang.set_active(len(combo_label_lang.get_model()) - 1)
                dlg.destroy()

            def _on_reset(btn):
                current_lang = combo_label_lang.get_active_text()
                if current_lang and current_lang in DEFAULT_LABELS:
                    global_labels[current_lang] = {}
                    _populate_grid(current_lang)
                elif current_lang:
                    global_labels.pop(current_lang, None)
                    if combo_label_lang.get_active() >= 0:
                        combo_label_lang.set_active(0)

            combo_label_lang.connect("changed", _on_lang_changed)
            btn_new_lang.connect("clicked", _on_new_lang)
            btn_reset.connect("clicked", _on_reset)

            if lang_code in [r[0] for r in combo_label_lang.get_model()]:
                combo_label_lang.set_active_id(lang_code)
            else:
                combo_label_lang.set_active(0)

        _build_labels_page(self.project.language)

        def on_config_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                self.project.title = entry_title.get_text().strip()
                self.project.author = entry_author.get_text().strip()
                self.project.language = entry_lang.get_text().strip() or "es"
                epub_idx = combo_epub.get_active()
                self.project.epub_version = ["epub2", "epub3"][epub_idx]
                auto_idx = combo_auto_title.get_active()
                if 0 <= auto_idx < len(auto_title_values):
                    self.project.auto_chapter_title = auto_title_values[auto_idx]
                auto_part_idx = combo_auto_part.get_active()
                if 0 <= auto_part_idx < len(auto_part_values):
                    self.project.auto_part_title = auto_part_values[auto_part_idx]
                theme_idx = combo_theme.get_active()
                if theme_idx >= 0 and theme_idx < len(available_themes):
                    self.project.theme_id = available_themes[theme_idx][0]
                self.project.drop_cap_enabled = check_drop_cap.get_active()
                self.project.drop_cap_types = [
                    t for t, cb in self._drop_cap_checkbuttons.items() if cb.get_active()
                ] or ["chapter"]
                self.project.figure_numbering = check_figure_numbering.get_active()
                fig_style_idx = combo_fig_style.get_active()
                if 0 <= fig_style_idx < len(fig_style_values):
                    self.project.figure_numbering_style = fig_style_values[fig_style_idx]
                self.project.table_numbering = check_table_numbering.get_active()
                tab_style_idx = combo_tab_style.get_active()
                if 0 <= tab_style_idx < len(tab_style_values):
                    self.project.table_numbering_style = tab_style_values[tab_style_idx]
                self.project.export_filename = entry_export.get_text().strip()
                self.project.edition = entry_edicion.get_text().strip()
                self.project.publication_date = entry_fecha.get_text().strip()
                self.project.isbn = entry_isbn.get_text().strip()
                self.project.publisher = entry_editorial.get_text().strip()
                self.project.subtitle = entry_subtitle.get_text().strip()
                lang_idx = combo_lang.get_active()
                if lang_idx >= 0 and lang_idx < len(langs):
                    self.project.spell_lang = langs[lang_idx]
                FileService.save_project(self.project)
                global_cfg["labels"] = global_labels
                YamlService.save(global_cfg, config_file)
                self._update_spell_lang()
                self._update_window_title()
                self._refresh_project_tree()
                if self.current_component:
                    self._update_styles_panel(self.current_component.type)
                elif self.current_part:
                    self._update_styles_panel(self.current_part.type)
                self._update_status("Configuracion del proyecto guardada")
                self._update_preview()
            d.destroy()

        dialog.connect("response", on_config_response)
        
        if read_only:
            for w in interactive_widgets:
                w.set_sensitive(False)
        dialog.show_all()

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

    # --- Acciones de proyecto ---

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

    def _on_add_component(self, button, part=None):
        if not self.project:
            self._show_info("Primero crea o abre un proyecto")
            return
        if self._read_only:
            self._show_info("No se puede modificar un proyecto de solo lectura")
            return

        dialog = Gtk.Dialog(
            title="Anadir Componente",
            transient_for=self.window,
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
            combo_type.append_text(self._resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct]))
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

                self.project.add_component(component)
                initial_content = f"# {title}\n\n" if title else ""
                FileService.save_component(self.project.path, component, initial_content)
                FileService.save_project(self.project)
                self._refresh_project_tree()
                self._update_status(f"Componente anadido: {component.get_display_name(self._resolve_labels())}")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_add_part(self, button):
        if not self.project:
            self._show_info("Primero crea o abre un proyecto")
            return
        if self._read_only:
            self._show_info("No se puede modificar un proyecto de solo lectura")
            return

        dialog = Gtk.Dialog(
            title="Anadir Parte",
            transient_for=self.window,
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
                    from .services.labels_service import resolve_labels
                    labels = resolve_labels(self.project.language)
                    title = labels.get("part", "Parte")
                import uuid
                component_id = str(uuid.uuid4())
                part = Component(
                    id=component_id,
                    type=ComponentType.PART,
                    title=title,
                    filename=FileService.generate_filename("part", title),
                )
                self.project.add_component(part)
                initial_content = f"# {title}\n\n"
                FileService.save_component(self.project.path, part, initial_content)
                FileService.save_project(self.project)
                self._refresh_project_tree()
                self._update_status(f"Parte anadida: {title}")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_export_epub(self, button):
        if not self.project:
            self._show_info("No hay proyecto abierto")
            return

        # Save current component before export so files on disk are up to date
        self._save_current_component()

        # Determine output filename
        from .services.file_service import slugify
        epub_name = self.project.export_filename or slugify(
            self.project.title or self.project.name
        )
        if not epub_name.endswith(".epub"):
            epub_name += ".epub"

        if self._read_only:
            output_dir = "/tmp/mdtoepub_export"
            epub_path = os.path.join(output_dir, epub_name)
        else:
            output_dir = os.path.join(self.project.path, "output")
            epub_path = os.path.join(output_dir, epub_name)

        os.makedirs(output_dir, exist_ok=True)
        if os.path.exists(epub_path):
            if not self._confirm(f"El archivo ya existe:\n{epub_path}\n\n¿Sobrescribirlo?"):
                return
        epub_service = EpubService(self.project)
        _, config_file = self._get_config_path()
        global_config = YamlService.load(config_file)
        result = epub_service.generate(epub_path, self.project.epub_version, global_config=global_config)
        if result:
            self._last_epub_path = result
            self._update_status(f"EPUB exportado: {result}")
            self._show_info(f"EPUB generado correctamente:\n{result}")
        else:
            self._show_error("Error al generar el EPUB")

    def _on_import_book(self, button):
        if not self.project:
            self._show_info("No hay proyecto abierto")
            return
        if self._read_only:
            self._show_info("No se puede importar en el libro de ejemplo")
            return

        dialog = Gtk.FileChooserNative(
            title="Importar libro Markdown",
            transient_for=self.window,
            action=Gtk.FileChooserAction.OPEN,
            accept_label="_Importar",
            cancel_label="_Cancelar",
        )

        f_filter = Gtk.FileFilter()
        f_filter.set_name("Archivos Markdown (*.md)")
        f_filter.add_pattern("*.md")
        dialog.add_filter(f_filter)
        f_filter = Gtk.FileFilter()
        f_filter.set_name("Todos los archivos")
        f_filter.add_pattern("*")
        dialog.add_filter(f_filter)

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_filename()
            dialog.destroy()

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                self._show_error(f"Error al leer el archivo: {e}")
                return

            if not content.strip():
                self._show_info("El archivo esta vacio")
                return

            # Preview the import structure
            from .services.file_service import FileService as FS
            parsed = FS.parse_imported_markdown(content)
            total_chars = sum(len(md) for _, _, md in parsed)
            desc_lines = [f"Se van a importar {len(parsed)} componentes:"]
            for ctype, title, md in parsed:
                title_str = f' — "{title}"' if title else ""
                desc_lines.append(f"  - {ctype}{title_str} ({len(md)} chars)")
            desc_lines.append("")
            desc_lines.append(f"Total: {total_chars} caracteres en {len(parsed)} componentes.")
            desc_lines.append("")
            desc_lines.append("Los nuevos componentes se anyadiran a los existentes.")

            confirm = Gtk.MessageDialog(
                parent=self.window,
                modal=True,
                type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text="Confirmar importacion",
            )
            confirm.format_secondary_text("\n".join(desc_lines))

            if confirm.run() == Gtk.ResponseType.YES:
                confirm.destroy()
                count = FS.import_book(self.project.path, self.project, content, file_path)
                self._update_status(f"Importados {count} componentes")
                self._refresh_project_tree()
                self._update_preview()
                self._show_info(f"Se importaron {count} componentes correctamente.")
            else:
                confirm.destroy()
        else:
            dialog.destroy()

    def _on_import_epub(self, button):
        if not self.project:
            self._show_info("No hay proyecto abierto")
            return
        if self._read_only:
            self._show_info("No se puede importar en el libro de ejemplo")
            return

        dialog = Gtk.FileChooserNative(
            title="Importar libro EPUB",
            transient_for=self.window,
            action=Gtk.FileChooserAction.OPEN,
            accept_label="_Importar",
            cancel_label="_Cancelar",
        )

        f_filter = Gtk.FileFilter()
        f_filter.set_name("Archivos EPUB (*.epub)")
        f_filter.add_pattern("*.epub")
        dialog.add_filter(f_filter)
        f_filter = Gtk.FileFilter()
        f_filter.set_name("Todos los archivos")
        f_filter.add_pattern("*")
        dialog.add_filter(f_filter)

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_filename()
            dialog.destroy()

            from .services.file_service import FileService as FS

            try:
                components, images = FS.parse_imported_epub(file_path)
            except Exception as e:
                self._show_error(f"Error al leer el EPUB: {e}")
                return

            if not components:
                self._show_info("El EPUB no contiene documentos importables.")
                return

            total_chars = sum(len(md) for _, _, md in components)
            desc_lines = [f"Se van a importar {len(components)} componentes:"]
            for ctype, title, md in components:
                title_str = f' — "{title}"' if title else ""
                desc_lines.append(f"  - {ctype}{title_str} ({len(md)} chars)")
            desc_lines.append("")
            desc_lines.append(f"Imagenes encontradas: {len(images)}")
            desc_lines.append(f"Total: {total_chars} caracteres en {len(components)} componentes.")
            desc_lines.append("")
            desc_lines.append("Los nuevos componentes se anyadiran a los existentes.")

            confirm = Gtk.MessageDialog(
                parent=self.window,
                modal=True,
                type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text="Confirmar importacion",
            )
            confirm.format_secondary_text("\n".join(desc_lines))

            if confirm.run() == Gtk.ResponseType.YES:
                confirm.destroy()
                count = FS.import_epub(self.project.path, self.project, file_path)
                self._update_status(f"Importados {count} componentes")
                self._refresh_project_tree()
                self._update_preview()
                self._show_info(f"Se importaron {count} componentes correctamente.")
            else:
                confirm.destroy()
        else:
            dialog.destroy()

    def _on_open_epub(self, button):
        if not self._last_epub_path or not os.path.exists(self._last_epub_path):
            self._show_info("No hay EPUB generado. Exportalo primero.")
            return
        try:
            import subprocess
            config_dir = os.path.join(GLib.get_user_config_dir(), "mdtoepub")
            config_file = os.path.join(config_dir, "config.yaml")
            config = YamlService.load(config_file) or {}
            reader_path = config.get("epub_reader_path", "").strip()
            if reader_path and os.path.exists(reader_path):
                subprocess.Popen([reader_path, self._last_epub_path])
            else:
                subprocess.Popen(["xdg-open", self._last_epub_path])
        except Exception as e:
            self._show_error(f"No se pudo abrir el EPUB: {e}")

    def _refresh_project_tree(self):
        self.project_store.clear()
        if not self.project:
            return

        labels = self._resolve_labels()
        project_iter = self.project_store.append(None, [self.project.name, self.project])
        part_iters = {}

        for comp in self.project.get_ordered_components():
            if comp.type == ComponentType.PART:
                part_iters[comp.id] = self.project_store.append(
                    project_iter, [comp.get_display_name(labels), comp]
                )
                continue
            part = self.project.get_part(comp.part_id) if comp.part_id else None
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
        if self._in_cursor_change:
            return
        self._in_cursor_change = True
        try:
            path, column = tree.get_cursor()
            if path is None:
                return

            iter = self.project_store.get_iter(path)
            obj = self.project_store.get_value(iter, 1)

            if isinstance(obj, Component):
                title_changed = self._save_current_component()
                self.current_component = obj
                self.current_part = None
                self._styles_current_component = obj
                if title_changed:
                    self._refresh_project_tree()
                    self.project_tree.expand_all()
                content = self._load_component_content(obj)
                buffer = self.text_view.get_buffer()
                buffer.set_text(content)
                self._update_status(f"Editando: {obj.get_display_name(self._resolve_labels())}")
                self._update_styles_panel(obj.type)
                self._update_preview()
        finally:
            self._in_cursor_change = False

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
            menu.append(Gtk.SeparatorMenuItem())
            item_import_img = Gtk.MenuItem(label="Importar imagen")
            item_import_img.connect("activate", self._on_import_image)
            menu.append(item_import_img)
            item_manage_img = Gtk.MenuItem(label="Gestionar imagenes")
            item_manage_img.connect("activate", self._on_manage_images)
            menu.append(item_manage_img)
            menu.append(Gtk.SeparatorMenuItem())
            item_css = Gtk.MenuItem(label="Editar estilos del libro")
            item_css.connect("activate", self._on_edit_book_css)
            menu.append(item_css)
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
                ct_item = Gtk.MenuItem(label=self._resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct]))
                ct_item.connect("activate", self._on_change_component_type, obj, ct)
                change_type_menu.append(ct_item)
            item_change_type.set_submenu(change_type_menu)
            menu.append(item_change_type)
            # Move to part submenu (if there are parts)
            parts = self.project.get_parts()
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
            type_label = self._resolve_labels().get(obj.type.value, COMPONENT_TYPE_LABELS.get(obj.type, obj.type.value))
            s1 = Gtk.MenuItem(label=f"Del tipo «{type_label}»")
            s1.connect("activate", self._on_edit_type_css, obj)
            styles_menu.append(s1)
            s2 = Gtk.MenuItem(label=f"Del componente «{obj.get_display_name(self._resolve_labels())}»")
            s2.connect("activate", self._on_edit_component_css, obj)
            styles_menu.append(s2)
            item_styles.set_submenu(styles_menu)
            menu.append(item_styles)
            menu.append(Gtk.SeparatorMenuItem())
            item_delete = Gtk.MenuItem(label="Eliminar componente")
            item_delete.connect("activate", self._on_delete_component, obj)
            menu.append(item_delete)
        else:
            return False

        if self._read_only:
            menu.foreach(lambda item: item.set_sensitive(False))

        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    def _on_close_project(self, widget):
        if self.project is None:
            return
        if not self._confirm("¿Cerrar el proyecto actual?"):
            return
        if self.current_component and not self._read_only:
            self._save_current_component()
        self.project = None
        self.project_store.clear()
        self.current_component = None
        self._styles_current_component = None
        self._styles_current_comp_type = None
        self.text_view.get_buffer().set_text("")
        self.webview.load_html(self.default_html, self._get_base_uri())
        self._set_read_only_mode(False)
        self._update_status("Proyecto cerrado")

    def _update_window_title(self):
        base = "MDToEPUB"
        if self.project and self.project.title:
            base = f"MDToEPUB — {self.project.title}"
        if self._read_only and "[SOLO LECTURA]" not in base:
            base += " [SOLO LECTURA]"
        self.window.set_title(base)

    def _set_read_only_mode(self, enabled: bool):
        self._read_only = enabled
        if self._toolbar_save_btn:
            self._toolbar_save_btn.set_sensitive(not enabled)
        self._update_window_title()

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

    def _on_menu_rename_component(self, widget):
        if not self.current_component:
            self._show_info("Selecciona un componente primero")
            return
        path, _ = self.project_tree.get_cursor()
        if path is None:
            return
        iter_ = self.project_store.get_iter(path)
        self._on_rename_component(None, self.current_component, iter_)

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
            self._show_info("Selecciona uno o varios componentes primero")
            return
        if len(comps) == 1:
            self._on_delete_component(None, comps[0])
        else:
            self._on_delete_multiple_components(None, comps)

    def _on_theme_manager(self, widget):
        if not self.project:
            self._show_info("Abre un proyecto primero")
            return

        themes = ThemeService.list_themes()

        dialog = Gtk.Dialog(
            title="Gestor de temas",
            transient_for=self.window,
            modal=True,
        )
        dialog.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(650, 500)

        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        store = Gtk.ListStore(str, str, str, str)
        for theme in themes:
            is_active = "Si" if theme.id == self.project.theme_id else ""
            type_label = "Integrado" if theme.is_builtin else "Personalizado"
            store.append([theme.name, theme.id, is_active, type_label])

        tree = Gtk.TreeView(model=store)
        tree.set_headers_visible(True)

        r_name = Gtk.CellRendererText()
        c_name = Gtk.TreeViewColumn("Tema", r_name, text=0)
        c_name.set_resizable(True)
        c_name.set_expand(True)
        tree.append_column(c_name)

        r_id = Gtk.CellRendererText()
        c_id = Gtk.TreeViewColumn("ID", r_id, text=1)
        c_id.set_resizable(True)
        tree.append_column(c_id)

        r_active = Gtk.CellRendererText()
        c_active = Gtk.TreeViewColumn("Activo", r_active, text=2)
        tree.append_column(c_active)

        r_type = Gtk.CellRendererText()
        c_type = Gtk.TreeViewColumn("Tipo", r_type, text=3)
        tree.append_column(c_type)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.add(tree)
        content.pack_start(scrolled, True, True, 0)

        btn_box = Gtk.Box(spacing=6)

        btn_activate = Gtk.Button(label="Activar tema")
        btn_activate.connect("clicked", lambda b: self._on_activate_theme(tree, store, dialog))
        btn_box.pack_start(btn_activate, False, False, 0)

        btn_create = Gtk.Button(label="Crear tema en blanco")
        btn_create.connect("clicked", lambda b: self._on_create_blank_theme(tree, store))
        btn_box.pack_start(btn_create, False, False, 0)

        btn_clone = Gtk.Button(label="Clonar tema")
        btn_clone.connect("clicked", lambda b: self._on_clone_theme(tree, store))
        btn_box.pack_start(btn_clone, False, False, 0)

        btn_view_css = Gtk.Button(label="Visualizar CSS")
        btn_view_css.connect("clicked", lambda b: self._on_view_theme_css(tree, store))
        btn_box.pack_start(btn_view_css, False, False, 0)

        btn_rename = Gtk.Button(label="Renombrar")
        btn_rename.connect("clicked", lambda b: self._on_rename_theme(tree, store))
        btn_box.pack_start(btn_rename, False, False, 0)

        btn_delete = Gtk.Button(label="Eliminar")
        btn_delete.connect("clicked", lambda b: self._on_delete_theme(tree, store, dialog))
        btn_box.pack_start(btn_delete, False, False, 0)

        content.pack_start(btn_box, False, False, 0)

        def on_selection_changed(sel):
            model, iter_ = sel.get_selected()
            if iter_ is not None:
                type_label = model.get_value(iter_, 3)
                is_custom = type_label == "Personalizado"
                btn_view_css.set_label("Editar CSS" if is_custom else "Visualizar CSS")
                btn_rename.set_sensitive(is_custom)
                btn_delete.set_sensitive(is_custom)
            else:
                btn_view_css.set_label("Visualizar CSS")
                btn_rename.set_sensitive(False)
                btn_delete.set_sensitive(False)

        tree.get_selection().connect("changed", on_selection_changed)
        on_selection_changed(tree.get_selection())

        dialog.show_all()
        dialog.connect("response", lambda d, r: d.destroy())

    def _on_activate_theme(self, tree, store, dialog):
        sel = tree.get_selection()
        model, iter_ = sel.get_selected()
        if iter_ is None:
            return
        theme_id = model.get_value(iter_, 1)
        if theme_id:
            self.project.theme_id = theme_id
            FileService.save_project(self.project)
            self._style_doc_svc = None
            self._update_preview()
            self._update_styles_panel(
                self.current_component.type if self.current_component else None
            )
            self._update_status(f"Tema activado: {model.get_value(iter_, 0)}")
            dialog.destroy()

    def _on_create_blank_theme(self, tree, store):
        dialog = Gtk.Dialog(
            title="Crear tema en blanco",
            transient_for=self.window,
            modal=True,
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Crear", Gtk.ResponseType.ACCEPT)
        dialog.set_default_size(400, 200)

        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        grid = Gtk.Grid(row_spacing=6, column_spacing=6)
        row = 0

        label = Gtk.Label(label="Nombre:")
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        entry_name = Gtk.Entry()
        grid.attach(entry_name, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="Descripcion:")
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        entry_desc = Gtk.Entry()
        grid.attach(entry_desc, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="Autor:")
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        entry_author = Gtk.Entry()
        grid.attach(entry_author, 1, row, 1, 1)

        content.pack_start(grid, False, False, 0)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                name = entry_name.get_text().strip()
                if not name:
                    self._show_info("El nombre es obligatorio")
                    return
                theme = ThemeService.create_blank(
                    name=name,
                    description=entry_desc.get_text().strip(),
                    author=entry_author.get_text().strip(),
                )
                if theme:
                    self._refresh_theme_store(store)
                    self._update_status(f"Tema creado: {name}")
                else:
                    self._show_info("No se pudo crear el tema (el ID ya existe)")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_clone_theme(self, tree, store):
        sel = tree.get_selection()
        model, iter_ = sel.get_selected()
        if iter_ is None:
            self._show_info("Selecciona un tema para clonar")
            return

        source_id = model.get_value(iter_, 1)
        source_name = model.get_value(iter_, 0)

        dialog = Gtk.Dialog(
            title=f"Clonar tema: {source_name}",
            transient_for=self.window,
            modal=True,
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Clonar", Gtk.ResponseType.ACCEPT)
        dialog.set_default_size(400, 250)

        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        grid = Gtk.Grid(row_spacing=6, column_spacing=6)
        row = 0

        label = Gtk.Label(label="Nombre:")
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        entry_name = Gtk.Entry()
        entry_name.set_text(f"{source_name} (copia)")
        entry_name.select_region(0, -1)
        grid.attach(entry_name, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="Descripcion:")
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        entry_desc = Gtk.Entry()
        grid.attach(entry_desc, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label="Autor:")
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        entry_author = Gtk.Entry()
        grid.attach(entry_author, 1, row, 1, 1)

        content.pack_start(grid, False, False, 0)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                name = entry_name.get_text().strip()
                if not name:
                    self._show_info("El nombre es obligatorio")
                    return
                theme = ThemeService.clone_theme(
                    source_id=source_id,
                    new_name=name,
                    description=entry_desc.get_text().strip(),
                    author=entry_author.get_text().strip(),
                )
                if theme:
                    self._refresh_theme_store(store)
                    self._update_status(f"Tema clonado: {name}")
                else:
                    self._show_info("No se pudo clonar el tema (el ID ya existe)")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_view_theme_css(self, tree, store):
        sel = tree.get_selection()
        model, iter_ = sel.get_selected()
        if iter_ is None:
            return
        type_label = model.get_value(iter_, 3)
        is_read_only = type_label == "Integrado"

        theme_id = model.get_value(iter_, 1)
        theme_name = model.get_value(iter_, 0)
        theme = ThemeService.get_theme(theme_id)
        if not theme:
            return

        theme_dir = theme.path

        theme_config = {}
        tyaml = os.path.join(theme_dir, "theme.yaml")
        if os.path.exists(tyaml):
            theme_config = YamlService.load(tyaml)

        css_files = {"style.css": "Base"}
        for comp_type, css_file in theme_config.get("styles", {}).items():
            if css_file not in css_files:
                css_files[css_file] = f"Componente: {comp_type}"

        mode_title = "Visualizar" if is_read_only else "Editar"
        editor_dialog = Gtk.Dialog(
            title=f"{mode_title} CSS: {theme_name}",
            transient_for=self.window,
            modal=True,
        )
        editor_dialog.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        if not is_read_only:
            editor_dialog.add_button("Guardar", Gtk.ResponseType.ACCEPT)
        editor_dialog.set_default_size(700, 500)

        editor_content = editor_dialog.get_content_area()
        editor_content.set_spacing(8)
        editor_content.set_margin_top(12)
        editor_content.set_margin_bottom(12)
        editor_content.set_margin_start(12)
        editor_content.set_margin_end(12)

        combo_css = Gtk.ComboBoxText()
        css_list = sorted(css_files.items())
        for fname, label in css_list:
            combo_css.append_text(f"{label} ({fname})")
        combo_css.set_active(0)
        editor_content.pack_start(combo_css, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        buf = GtkSource.Buffer.new_with_language(
            GtkSource.LanguageManager.get_default().get_language("css")
        )
        text_view = GtkSource.View.new_with_buffer(buf)
        text_view.set_monospace(True)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.set_hexpand(True)
        text_view.set_vexpand(True)
        text_view.set_editable(not is_read_only)
        if is_read_only:
            text_view.set_cursor_visible(False)

        current_file_idx = [0]

        def load_css_file(idx):
            fname = css_list[idx][0]
            fpath = os.path.join(theme_dir, fname)
            text = ""
            if os.path.exists(fpath):
                with open(fpath) as f:
                    text = f.read()
            buf.set_text(text)
            current_file_idx[0] = idx

        load_css_file(0)

        def on_combo_changed(cb):
            load_css_file(cb.get_active())

        combo_css.connect("changed", on_combo_changed)

        scrolled.add(text_view)
        editor_content.pack_start(scrolled, True, True, 0)

        def on_editor_response(d, response):
            if response == Gtk.ResponseType.ACCEPT and not is_read_only:
                fname = css_list[current_file_idx[0]][0]
                fpath = os.path.join(theme_dir, fname)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True))
                self._update_status(f"CSS guardado: {fname}")
                if self.project and self.project.theme_id == theme_id:
                    self._update_preview()
                    self._update_styles_panel()
            d.destroy()

        editor_dialog.connect("response", on_editor_response)
        editor_dialog.show_all()

    def _on_rename_theme(self, tree, store):
        sel = tree.get_selection()
        model, iter_ = sel.get_selected()
        if iter_ is None:
            return
        type_label = model.get_value(iter_, 3)
        if type_label == "Integrado":
            self._show_info("Los temas integrados no se pueden renombrar")
            return

        theme_id = model.get_value(iter_, 1)
        current_name = model.get_value(iter_, 0)

        dialog = Gtk.Dialog(
            title="Renombrar tema",
            transient_for=self.window,
            modal=True,
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Renombrar", Gtk.ResponseType.ACCEPT)
        dialog.set_default_size(350, 120)

        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        entry = Gtk.Entry()
        entry.set_text(current_name)
        entry.select_region(0, -1)
        content.pack_start(entry, False, False, 0)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                new_name = entry.get_text().strip()
                if new_name:
                    ThemeService.rename_theme(theme_id, new_name)
                    self._refresh_theme_store(store)
                    self._update_status(f"Tema renombrado: {new_name}")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_delete_theme(self, tree, store, parent_dialog):
        sel = tree.get_selection()
        model, iter_ = sel.get_selected()
        if iter_ is None:
            return
        type_label = model.get_value(iter_, 3)
        if type_label == "Integrado":
            self._show_info("Los temas integrados no se pueden eliminar")
            return

        theme_id = model.get_value(iter_, 1)
        theme_name = model.get_value(iter_, 0)

        if theme_id == self.project.theme_id:
            self._show_info(
                f"El tema '{theme_name}' esta en uso.\n"
                "Cambia a otro tema antes de eliminarlo."
            )
            return

        confirm = Gtk.MessageDialog(
            transient_for=parent_dialog,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Eliminar tema: {theme_name}",
        )
        confirm.format_secondary_text(
            "Esta accion no se puede deshacer.\n"
            "Todos los archivos del tema se eliminaran permanentemente."
        )
        resp = confirm.run()
        confirm.destroy()

        if resp == Gtk.ResponseType.YES:
            if ThemeService.delete_theme(theme_id):
                self._refresh_theme_store(store)
                self._update_status(f"Tema eliminado: {theme_name}")
            else:
                self._show_info("No se pudo eliminar el tema")

    def _refresh_theme_store(self, store):
        store.clear()
        themes = ThemeService.list_themes()
        for theme in themes:
            is_active = "Si" if theme.id == self.project.theme_id else ""
            type_label = "Integrado" if theme.is_builtin else "Personalizado"
            store.append([theme.name, theme.id, is_active, type_label])

    def _on_about(self, widget):
        dialog = Gtk.AboutDialog(
            transient_for=self.window,
            modal=True,
        )
        dialog.set_program_name("MDToEPUB")
        dialog.set_version("1.0")
        dialog.set_comments("Editor de EPUB a partir de Markdown")
        dialog.set_license_type(Gtk.License.GPL_3_0)
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.show_all()

    def _on_edit_custom_css(self, menu_item):
        if not self.project:
            return

        custom_css_path = os.path.join(self.project.path, "styles", "custom.css")
        content = ""
        if os.path.exists(custom_css_path):
            with open(custom_css_path, "r") as f:
                content = f.read()

        dialog = Gtk.Dialog(
            title="CSS personalizado",
            transient_for=self.window,
            modal=True,
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Guardar", Gtk.ResponseType.ACCEPT)
        dialog.set_default_size(600, 500)

        content_area = dialog.get_content_area()
        content_area.set_spacing(8)
        content_area.set_margin_top(12)
        content_area.set_margin_bottom(12)
        content_area.set_margin_start(12)
        content_area.set_margin_end(12)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        text_view = Gtk.TextView()
        text_view.set_monospace(True)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        buffer_ = text_view.get_buffer()
        buffer_.set_text(content)
        scrolled.add(text_view)
        content_area.pack_start(scrolled, True, True, 0)

        dialog.show_all()

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                start = buffer_.get_start_iter()
                end = buffer_.get_end_iter()
                new_content = buffer_.get_text(start, end, True)
                os.makedirs(os.path.dirname(custom_css_path), exist_ok=True)
                with open(custom_css_path, "w") as f:
                    f.write(new_content)
                self._update_status("CSS personalizado guardado")
                self._update_preview()
            d.destroy()

        dialog.connect("response", on_response)

    def _on_import_image(self, menu_item):
        if not self.project:
            return

        dialog = Gtk.FileChooserDialog(
            title="Seleccionar imagen",
            transient_for=self.window,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Importar", Gtk.ResponseType.ACCEPT)

        img_filter = Gtk.FileFilter()
        img_filter.set_name("Imagenes (JPEG, PNG, GIF)")
        for ext in ImageService.get_supported_formats():
            img_filter.add_pattern(f"*{ext}")
            img_filter.add_pattern(f"*{ext.upper()}")
        dialog.add_filter(img_filter)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                src_path = d.get_filename()
                if src_path:
                    category_dialog = Gtk.Dialog(
                        title="Tipo de imagen",
                        transient_for=self.window,
                        modal=True,
                    )
                    category_dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
                    category_dialog.add_button("Importar", Gtk.ResponseType.ACCEPT)

                    cat_content = category_dialog.get_content_area()
                    cat_content.set_spacing(12)
                    cat_content.set_margin_top(12)
                    cat_content.set_margin_bottom(12)
                    cat_content.set_margin_start(12)
                    cat_content.set_margin_end(12)

                    cat_label = Gtk.Label(label="Selecciona el tipo de imagen:")
                    cat_content.add(cat_label)

                    combo_cat = Gtk.ComboBoxText()
                    combo_cat.append_text("Ilustrativa (figuras, diagramas)")
                    combo_cat.append_text("Decorativa (separadores, adornos)")
                    combo_cat.set_active(0)
                    cat_content.add(combo_cat)

                    category_dialog.show_all()

                    def on_cat_response(cd, cat_response):
                        if cat_response == Gtk.ResponseType.ACCEPT:
                            category = "illustrations" if combo_cat.get_active() == 0 else "decorative"
                            images_dir = os.path.join(self.project.path, "images")
                            result = ImageService.copy_to_project(src_path, images_dir, category)
                            if result:
                                self._update_status(f"Imagen importada: {os.path.basename(src_path)}")
                            else:
                                self._show_error("Error al importar la imagen")
                        cd.destroy()

                    category_dialog.connect("response", on_cat_response)
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_manage_images(self, menu_item):
        if not self.project:
            return

        images_dir = Path(self.project.path) / "images"
        if not images_dir.exists():
            self._show_info("No hay imagenes en el proyecto")
            return

        dialog = Gtk.Dialog(
            title="Gestionar imagenes",
            transient_for=self.window,
            modal=True,
        )
        dialog.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(820, 520)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hbox.set_margin_top(12)
        hbox.set_margin_bottom(12)
        hbox.set_margin_start(12)
        hbox.set_margin_end(12)
        dialog.get_content_area().pack_start(hbox, True, True, 0)

        # --- Left: tree + buttons ---
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        hbox.pack_start(left_box, True, True, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        left_box.pack_start(scrolled, True, True, 0)

        IMG_COL_NAME = 0
        IMG_COL_CAT = 1
        IMG_COL_SIZE = 2
        IMG_COL_PATH = 3

        store = Gtk.ListStore(str, str, str, str)
        tree_view = Gtk.TreeView(model=store)
        tree_view.set_headers_visible(True)
        tree_view.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        r_name = Gtk.CellRendererText()
        col_name = Gtk.TreeViewColumn("Nombre", r_name, text=IMG_COL_NAME)
        col_name.set_resizable(True)
        col_name.set_expand(True)
        tree_view.append_column(col_name)

        r_cat = Gtk.CellRendererText()
        col_cat = Gtk.TreeViewColumn("Categoria", r_cat, text=IMG_COL_CAT)
        col_cat.set_resizable(True)
        tree_view.append_column(col_cat)

        r_size = Gtk.CellRendererText()
        col_size = Gtk.TreeViewColumn("Tamano", r_size, text=IMG_COL_SIZE)
        col_size.set_resizable(True)
        tree_view.append_column(col_size)

        def populate_store():
            store.clear()
            for cat_name, cat_label in [("illustrations", "Ilustrativa"), ("decorative", "Decorativa")]:
                cat_dir = images_dir / cat_name
                if cat_dir.exists():
                    for f in sorted(cat_dir.iterdir()):
                        if not f.is_file() or f.suffix.lower() not in ImageService.get_supported_formats():
                            continue
                        size = f.stat().st_size
                        size_str = f"{size / 1024:.1f} KB"
                        store.append([f.name, cat_label, size_str, str(f)])

        populate_store()

        scrolled.add(tree_view)

        # Button row below tree
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        left_box.pack_start(btn_box, False, False, 0)

        btn_delete = Gtk.Button(label="Eliminar")
        btn_box.pack_start(btn_delete, False, False, 0)

        btn_rename = Gtk.Button(label="Renombrar")
        btn_box.pack_start(btn_rename, False, False, 0)

        # --- Right: preview ---
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        right_box.set_size_request(280, -1)
        hbox.pack_start(right_box, False, False, 0)

        preview_img = Gtk.Image()
        preview_frame = Gtk.Frame(label="Vista previa")
        preview_frame.set_size_request(260, 300)
        preview_frame.add(preview_img)
        right_box.pack_start(preview_frame, True, True, 0)

        def update_preview():
            sel = tree_view.get_selection()
            model, paths = sel.get_selected_rows()
            if len(paths) != 1:
                preview_img.clear()
                return
            iter_ = model.get_iter(paths[0])
            fpath = model.get_value(iter_, IMG_COL_PATH)
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(fpath, 240, 260)
                preview_img.set_from_pixbuf(pixbuf)
            except Exception:
                preview_img.clear()

        tree_view.get_selection().connect("changed", lambda *a: update_preview())

        # --- Delete ---
        def on_delete(_btn):
            sel = tree_view.get_selection()
            model, paths = sel.get_selected_rows()
            if not paths:
                self._show_info("Selecciona una o varias imagenes")
                return
            names = []
            for p in paths:
                iter_ = model.get_iter(p)
                names.append(model.get_value(iter_, IMG_COL_NAME))
            confirm = Gtk.MessageDialog(
                transient_for=dialog, modal=True,
                message_type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text=f"Eliminar {len(names)} imagenes",
            )
            confirm.format_secondary_text("\n".join(f"  - {n}" for n in names))
            if confirm.run() == Gtk.ResponseType.YES:
                confirm.destroy()
                for p in reversed(sorted(paths)):
                    iter_ = model.get_iter(p)
                    fpath = model.get_value(iter_, IMG_COL_PATH)
                    ImageService.delete_image(fpath)
                populate_store()
                update_preview()
            else:
                confirm.destroy()

        btn_delete.connect("clicked", on_delete)

        # --- Rename ---
        def on_rename(_btn):
            sel = tree_view.get_selection()
            model, paths = sel.get_selected_rows()
            if len(paths) != 1:
                self._show_info("Selecciona una sola imagen para renombrar")
                return
            iter_ = model.get_iter(paths[0])
            old_name = model.get_value(iter_, IMG_COL_NAME)
            fpath = model.get_value(iter_, IMG_COL_PATH)
            cat_label = model.get_value(iter_, IMG_COL_CAT)
            cat_name = "illustrations" if cat_label == "Ilustrativa" else "decorative"

            rename_dialog = Gtk.Dialog(
                title="Renombrar imagen",
                transient_for=dialog, modal=True,
            )
            rename_dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
            rename_dialog.add_button("Renombrar", Gtk.ResponseType.ACCEPT)

            r_content = rename_dialog.get_content_area()
            r_content.set_spacing(12)
            r_content.set_margin_top(12)
            r_content.set_margin_bottom(12)
            r_content.set_margin_start(12)
            r_content.set_margin_end(12)

            r_content.add(Gtk.Label(label="Nuevo nombre:"))
            entry = Gtk.Entry()
            entry.set_text(old_name)
            entry.set_hexpand(True)
            entry.connect("activate", lambda *a: rename_dialog.response(Gtk.ResponseType.ACCEPT))
            r_content.add(entry)

            rename_dialog.show_all()

            if rename_dialog.run() == Gtk.ResponseType.ACCEPT:
                new_name = entry.get_text().strip()
                rename_dialog.destroy()
                if not new_name or new_name == old_name:
                    return
                old_path = f"images/{cat_name}/{old_name}"
                new_path = f"images/{cat_name}/{new_name}"

                # Check extension matches
                src_suffix = Path(old_name).suffix.lower()
                new_suffix = Path(new_name).suffix.lower()
                if new_suffix != src_suffix:
                    self._show_error("La extension debe ser la misma")
                    return

                result = ImageService.rename_image(fpath, new_name)
                if result is None:
                    self._show_error(f"No se pudo renombrar (¿ya existe '{new_name}'?)")
                    return

                # Update references in all component files
                updated = FileService.rename_image_references(
                    self.project.path, old_path, new_path, self.project
                )

                # Refresh editor if current component was affected
                if self.current_component:
                    content = FileService.load_component(self.project.path, self.current_component)
                    if content:
                        buf = self.text_view.get_buffer()
                        buf.set_text(content)
                        self._update_preview()

                populate_store()
                self._update_status(f"Imagen renombrada a '{new_name}' ({updated} componente(s) actualizados)")
            else:
                rename_dialog.destroy()

        btn_rename.connect("clicked", on_rename)

        dialog.show_all()
        dialog.connect("response", lambda d, r: d.destroy())

    def _on_rename_part(self, menu_item, part, iter_):
        dialog = Gtk.Dialog(
            title="Renombrar parte",
            transient_for=self.window,
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
                    from .services.labels_service import resolve_labels
                    labels = resolve_labels(self.project.language)
                    new_title = labels.get("part", "Parte")
                part.title = new_title
                self.project_store.set_value(iter_, 0, part.get_display_name(self._resolve_labels()))
                FileService.save_project(self.project)
                self._update_status(f"Parte renombrada: {new_title}")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_delete_part(self, menu_item, part):
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Eliminar parte",
        )
        dialog.format_secondary_text(f"Se eliminara la parte \"{part.get_display_name(self._resolve_labels())}\" y sus componentes quedaran sin agrupar.")

        def on_response(d, response):
            if response == Gtk.ResponseType.YES:
                for c in self.project.components:
                    if c.part_id == part.id:
                        c.part_id = None
                self.project.remove_component(part.id)
                FileService.save_project(self.project)
                self._refresh_project_tree()
                self._update_status(f"Parte eliminada: {part.get_display_name(self._resolve_labels())}")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_rename_component(self, menu_item, component, iter_):
        dialog = Gtk.Dialog(
            title="Renombrar componente",
            transient_for=self.window,
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
                    self.project_store.set_value(iter_, 0, component.get_display_name(self._resolve_labels()))
                    FileService.save_project(self.project)
                    self._update_status(f"Componente renombrado: {new_title}")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_duplicate_component(self, menu_item, component):
        import uuid
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
        # Shift subsequent components' orders up
        for c in self.project.components:
            if c.order >= new_comp.order:
                c.order += 1

        content = FileService.load_component(self.project.path, component)
        self.project.add_component(new_comp)
        FileService.save_component(self.project.path, new_comp, content or "")
        FileService.save_project(self.project)
        self._refresh_project_tree()
        self._update_status(f"Componente duplicado: {new_comp.get_display_name(self._resolve_labels())}")

    def _on_move_to_part(self, menu_item, component, part):
        if component.part_id == part.id:
            return
        component.part_id = part.id
        FileService.save_project(self.project)
        self._refresh_project_tree()
        self._update_status(f"{component.get_display_name(self._resolve_labels())} movido a {part.get_display_name(self._resolve_labels())}")

    def _on_detach_from_part(self, menu_item, component):
        if not component.part_id:
            return
        if not self._confirm(f"Separar «{component.get_display_name(self._resolve_labels())}» de su parte?"):
            return
        component.part_id = None
        FileService.save_project(self.project)
        self._refresh_project_tree()
        self._update_status(f"{component.get_display_name(self._resolve_labels())} separado de la parte")

    def _on_delete_component(self, menu_item, component):
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Eliminar componente",
        )
        dialog.format_secondary_text(f"Se eliminara el componente \"{component.get_display_name(self._resolve_labels())}\".")

        def on_response(d, response):
            if response == Gtk.ResponseType.YES:
                if self.current_component and self.current_component.id == component.id:
                    self.text_view.get_buffer().set_text("")
                    self.webview.load_html(self.default_html, self._get_base_uri())
                    self.current_component = None
                self.project.remove_component(component.id)
                FileService.save_project(self.project)
                self._refresh_project_tree()
                self._update_status(f"Componente eliminado: {component.get_display_name(self._resolve_labels())}")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _get_selected_components(self, selection):
        """Return all Component objects from the current tree selection."""
        model, paths = selection.get_selected_rows()
        comps = []
        for path in paths:
            iter_ = model.get_iter(path)
            obj = model.get_value(iter_, 1)
            if isinstance(obj, Component):
                comps.append(obj)
        return comps

    def _on_delete_multiple_components(self, menu_item, components):
        names = "\n".join(f"  - {c.get_display_name(self._resolve_labels())}" for c in components)
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Eliminar {len(components)} componentes",
        )
        dialog.format_secondary_text(f"Se eliminaran los siguientes componentes:\n{names}")

        def on_response(d, response):
            if response == Gtk.ResponseType.YES:
                ids = {c.id for c in components}
                if self.current_component and self.current_component.id in ids:
                    self.text_view.get_buffer().set_text("")
                    self.webview.load_html(self.default_html, self._get_base_uri())
                    self.current_component = None
                for comp in components:
                    self.project.remove_component(comp.id)
                FileService.save_project(self.project)
                self._refresh_project_tree()
                self._update_status(f"Eliminados {len(components)} componentes")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_change_component_type(self, menu_item, component, new_type):
        component.type = new_type
        if not component.title:
            component.title = ""
        FileService.save_project(self.project)
        self._refresh_project_tree()
        self._update_status(f"Tipo cambiado a: {self._resolve_labels().get(new_type.value, COMPONENT_TYPE_LABELS[new_type])}")
        self._update_preview()

    def _edit_css_dialog(self, title: str, initial_css: str, scope_type: str = "", scope_type_value: str = "") -> str:
        dialog = Gtk.Dialog(
            title=title,
            transient_for=self.window,
            flags=0,
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Guardar", Gtk.ResponseType.OK)
        dialog.set_default_size(600, 500)

        box = dialog.get_content_area()

        if scope_type:
            hints = []
            if scope_type == "book":
                hints.append("Editando estilos globales del libro (afectan a TODOS los componentes).")
            elif scope_type == "type" and scope_type_value:
                hints.append(
                    f"Selector principal: <b>.component-{scope_type_value}</b>"
                )
                hints.append(
                    f"Sub-elementos: <b>.component-{scope_type_value}</b> h1, h2, p, ul, li, img, blockquote, etc."
                )
                hints.append("Usa prefijos de clase (p.ej. <b>.toc-entry</b>) para elementos auto-generados.")
            elif scope_type == "component" and scope_type_value:
                hints.append(
                    f"Selector principal: <b>.component-{scope_type_value}</b>"
                )
                hints.append("Estos estilos solo afectan a este componente.")
            elif scope_type == "theme":
                hints.append("Editando estilos del tema (afectan a TODOS los libros que usen este tema).")

            if hints:
                hint_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                hint_bar.set_margin_bottom(8)
                for h in hints:
                    lbl = Gtk.Label()
                    lbl.set_markup(f'<span size="small" foreground="#444">{h}</span>')
                    lbl.set_xalign(0)
                    lbl.set_line_wrap(True)
                    hint_bar.pack_start(lbl, False, False, 0)
                box.pack_start(hint_bar, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        buffer = GtkSource.Buffer.new_with_language(
            GtkSource.LanguageManager.get_default().get_language("css")
        )
        if not initial_css.strip() and scope_type_value:
            if scope_type == "type":
                initial_css = (
                    f"/* Estilos para el tipo «{scope_type_value}»\n"
                    f" * Selector principal: .component-{scope_type_value}\n"
                    f" * Ejemplos:\n"
                    f" *   .component-{scope_type_value} p {{ }}\n"
                    f" *   .component-{scope_type_value} h1 {{ }}\n"
                    f" *   .component-{scope_type_value} blockquote {{ }}\n"
                    f" */\n\n"
                )
            elif scope_type == "component":
                initial_css = (
                    f"/* Estilos para este componente (tipo «{scope_type_value}»)\n"
                    f" * Selector principal: .component-{scope_type_value}\n"
                    f" * Ejemplos:\n"
                    f" *   .component-{scope_type_value} p {{ }}\n"
                    f" *   .component-{scope_type_value} img {{ }}\n"
                    f" */\n\n"
                )
            elif scope_type == "book":
                initial_css = (
                    "/* Estilos globales del libro\n"
                    " * Afectan a todos los componentes.\n"
                    " * Selectores principales:\n"
                    " *   body { }  p { }  h1, h2, h3 { }\n"
                    " *   .component-chapter { }  .component-title { }  etc.\n"
                    " */\n\n"
                )
        buffer.set_text(initial_css)
        textview = GtkSource.View.new_with_buffer(buffer)
        textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        textview.set_monospace(True)
        scrolled.add(textview)

        box.pack_start(scrolled, True, True, 0)
        dialog.show_all()

        result = dialog.run()
        css = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        dialog.destroy()
        if result == Gtk.ResponseType.OK:
            return css
        return None

    def _on_edit_book_css(self, widget):
        if not self.project:
            self._show_info("Abre un proyecto primero")
            return
        css = self._edit_css_dialog("Estilos del libro", self.project.custom_css, scope_type="book")
        if css is None:
            return
        self.project.custom_css = css
        FileService.save_project(self.project)
        self._update_preview()
        self._update_styles_panel(
            self.current_component.type if self.current_component else None
        )
        self._update_status("Estilos del libro actualizados")

    def _on_edit_type_css(self, widget, component):
        if not self.project:
            return
        type_key = component.type.value
        current = self.project.type_css_overrides.get(type_key, "")
        label = self._resolve_labels().get(component.type.value, COMPONENT_TYPE_LABELS.get(component.type, type_key))
        css = self._edit_css_dialog(f"Estilos del tipo: {label}", current, scope_type="type", scope_type_value=component.type.value)
        if css is None:
            return
        if css.strip():
            self.project.type_css_overrides[type_key] = css
        else:
            self.project.type_css_overrides.pop(type_key, None)
        FileService.save_project(self.project)
        self._update_preview()
        self._update_styles_panel(component.type)
        self._update_status(f"Estilos del tipo '{label}' actualizados")

    def _on_edit_component_css(self, widget, component):
        if not self.project:
            return
        css = self._edit_css_dialog(
            f"Estilos del componente: {component.get_display_name(self._resolve_labels())}",
            component.custom_css,
            scope_type="component",
            scope_type_value=component.type.value,
        )
        if css is None:
            return
        component.custom_css = css
        FileService.save_project(self.project)
        self._update_preview()
        self._update_styles_panel(component.type)
        self._update_status(f"Estilos del componente '{component.get_display_name(self._resolve_labels())}' actualizados")

    def _on_manage_type_css(self, widget):
        if not self.project:
            self._show_info("Abre un proyecto primero")
            return

        dialog = Gtk.Dialog(
            title="Gestionar estilos por tipo",
            transient_for=self.window,
            flags=0,
        )
        dialog.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(450, 400)

        store = Gtk.ListStore(str, str, str)
        for ct in ComponentType:
            label = self._resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct])
            has_css = ct.value in self.project.type_css_overrides
            status = "Editado" if has_css else "Por defecto del tema"
            store.append([label, status, ct.value])

        tree = Gtk.TreeView(model=store)
        tree.set_headers_visible(True)
        renderer_label = Gtk.CellRendererText()
        col_label = Gtk.TreeViewColumn("Tipo", renderer_label, text=0)
        col_label.set_resizable(True)
        col_label.set_expand(True)
        tree.append_column(col_label)
        renderer_status = Gtk.CellRendererText()
        col_status = Gtk.TreeViewColumn("Estado", renderer_status, text=1)
        col_status.set_resizable(True)
        tree.append_column(col_status)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.add(tree)
        box = dialog.get_content_area()
        box.pack_start(scrolled, True, True, 0)

        btn_box = Gtk.Box(spacing=6)
        btn_edit = Gtk.Button(label="Editar")
        btn_reset = Gtk.Button(label="Restablecer")
        btn_box.pack_start(btn_edit, False, False, 0)
        btn_box.pack_start(btn_reset, False, False, 0)
        box.pack_start(btn_box, False, False, 0)

        def _selected_type():
            sel = tree.get_selection()
            model, it = sel.get_selected()
            if it is None:
                return None
            return model.get_value(it, 2)

        def _on_edit(btn):
            type_key = _selected_type()
            if not type_key:
                return
            ct = ComponentType(type_key)
            label = self._resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct])
            current = self.project.type_css_overrides.get(type_key, "")
            css = self._edit_css_dialog(f"Estilos del tipo: {label}", current, scope_type="type", scope_type_value=ct.value)
            if css is None:
                return
            if css.strip():
                self.project.type_css_overrides[type_key] = css
            else:
                self.project.type_css_overrides.pop(type_key, None)
            FileService.save_project(self.project)
            self._update_preview()
            if self.current_component:
                self._update_styles_panel(self.current_component.type)
            self._update_status(f"Estilos del tipo '{label}' actualizados")
            _refresh_list()

        def _on_reset(btn):
            type_key = _selected_type()
            if not type_key:
                return
            ct = ComponentType(type_key)
            label = self._resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct])
            if type_key not in self.project.type_css_overrides:
                return
            if not self._confirm(f"Restablecer estilos del tipo «{label}»?\nSe perderán los cambios personalizados."):
                return
            del self.project.type_css_overrides[type_key]
            FileService.save_project(self.project)
            self._update_preview()
            if self.current_component:
                self._update_styles_panel(self.current_component.type)
            self._update_status(f"Estilos del tipo '{label}' restablecidos al tema")
            _refresh_list()

        def _refresh_list():
            store.clear()
            for ct in ComponentType:
                label = self._resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct])
                has_css = ct.value in self.project.type_css_overrides
                status = "Editado" if has_css else "Por defecto del tema"
                store.append([label, status, ct.value])

        tree.connect("row-activated", lambda t, path, col: _on_edit(None))
        btn_edit.connect("clicked", _on_edit)
        btn_reset.connect("clicked", _on_reset)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def _on_drag_begin(self, treeview, context):
        if self._read_only:
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
        if self._read_only:
            return False
        dest = treeview.get_dest_row_at_pos(int(x), int(y))
        if dest:
            path, pos = dest
            treeview.set_drag_dest_row(path, pos)
        return False

    def _on_drag_data_get(self, treeview, drag_context, data, info, time_):
        if self._read_only:
            return
        if not self._drag_component_ids:
            return
        data.set(Gdk.atom_intern("MOVE_ROW", False), 8, b"x")

    def _on_drag_data_received(self, treeview, context, x, y, selection_data, info, time_):
        if not self.project or self._read_only:
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

        # Ignore drop on dragged item (no-op)
        dest_iter = self.project_store.get_iter(dest_path)
        if dest_iter is not None:
            dest_obj = self.project_store.get_value(dest_iter, 1)
            if isinstance(dest_obj, Component) and dest_obj.id in source_ids:
                context.finish(True, False, time_)
                return

        # Build an ordered list of all component rows from the tree
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

        # Extract dragged items and remove from list (in reverse order to preserve indices)
        dragged = [rows[i] for i in source_indices]
        for i in reversed(source_indices):
            rows.pop(i)

        # Adjust dest_row: items before it have been removed
        removed_before = sum(1 for i in source_indices if i < dest_row)
        adjusted_dest = dest_row - removed_before

        # Determine insertion index in the modified rows list
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

        # Build final component list with correct order
        new_components = []
        for idx, (cid, is_part) in enumerate(rows):
            comp = next((c for c in self.project.components if c.id == cid), None)
            if comp is None:
                continue
            comp.order = idx
            if not is_part:
                comp_part = self._find_part_for_row(rows, idx)
                comp.part_id = comp_part.id if comp_part else None
            new_components.append(comp)

        self.project.components = new_components
        FileService.save_project(self.project)
        self._refresh_project_tree()
        self._update_status("Componente(s) reordenado(s)")
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
                return next((c for c in self.project.components if c.id == cid), None)
        return None

    def _on_text_changed(self, buffer):
        self._update_preview()

    def _update_status(self, message):
        self.status_label.set_text(message)
        if self.project:
            self.project_label.set_text(f"Proyecto: {self.project.name}")

    def _get_config_path(self) -> tuple:
        config_dir = os.path.join(GLib.get_user_config_dir(), "mdtoepub")
        os.makedirs(config_dir, exist_ok=True)
        return config_dir, os.path.join(config_dir, "config.yaml")

    def _load_recent_projects(self):
        _, config_file = self._get_config_path()
        config = YamlService.load(config_file)
        self._recent_projects = config.get("recent_projects", [])
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

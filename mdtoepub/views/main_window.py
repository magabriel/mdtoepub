from ..utils.dialogs import show_error, show_info, confirm
import os
import shutil
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from ..models.component import Component
from ..services.file_service import FileService
from ..services.yaml_service import YamlService

from ..i18n import _


class MainWindow:
    def __init__(self, app):
        self.app = app
        self._recent_menu = None
        self._recent_projects = []
        self.selected_folder = ""
        self.folder_chooser_btn = None
        self._project_config_btn = None
        self._project_config_menu_item = None
        self._project_dependent_items = []

    def build(self, container):
        self._setup_menubar(container)
        self._setup_toolbar(container)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        container.pack_start(paned, True, True, 0)

        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left_box.set_size_request(250, -1)
        left_box.set_vexpand(True)
        paned.pack1(left_box, True, True)

        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right_box.set_vexpand(True)
        paned.pack2(right_box, True, True)

        self._setup_statusbar(container)

        return (left_box, right_box)

    # ─── Menubar ──────────────────────────────────────────────────────

    def _setup_menubar(self, container):
        menubar = Gtk.MenuBar()

        # File
        archivo = Gtk.MenuItem(label=_("File"))
        archivo_menu = Gtk.Menu()
        archivo.set_submenu(archivo_menu)
        item = Gtk.MenuItem(label=_("New Project"))
        item.connect("activate", self._on_new_project)
        archivo_menu.append(item)
        item = Gtk.MenuItem(label=_("Open Project"))
        item.connect("activate", self._on_open_project)
        archivo_menu.append(item)
        item = Gtk.MenuItem(label=_("Save"))
        item.connect("activate", self._on_save_project)
        item.set_sensitive(False)
        self._project_dependent_items.append(item)
        archivo_menu.append(item)
        item = Gtk.MenuItem(label=_("Save As"))
        item.connect("activate", self._on_save_project_as)
        item.set_sensitive(False)
        self._project_dependent_items.append(item)
        archivo_menu.append(item)
        archivo_menu.append(Gtk.SeparatorMenuItem())
        item = Gtk.MenuItem(label=_("Close Project"))
        item.connect("activate", self.app.project_tree_view._on_close_project)
        item.set_sensitive(False)
        self._project_dependent_items.append(item)
        archivo_menu.append(item)
        archivo_menu.append(Gtk.SeparatorMenuItem())
        self._recent_menu = Gtk.Menu()
        recent_item = Gtk.MenuItem(label=_("Recent Projects"))
        recent_item.set_submenu(self._recent_menu)
        archivo_menu.append(recent_item)
        archivo_menu.append(Gtk.SeparatorMenuItem())
        item = Gtk.MenuItem(label=_("Import Book..."))
        item.connect("activate", self.app.export_import_ctrl.import_book)
        item.set_sensitive(False)
        self._project_dependent_items.append(item)
        archivo_menu.append(item)
        item = Gtk.MenuItem(label=_("Import EPUB Book..."))
        item.connect("activate", self.app.export_import_ctrl.import_epub)
        item.set_sensitive(False)
        self._project_dependent_items.append(item)
        archivo_menu.append(item)
        archivo_menu.append(Gtk.SeparatorMenuItem())
        item = Gtk.MenuItem(label=_("Quit"))
        item.connect("activate", lambda w: self.app.window.destroy())
        archivo_menu.append(item)
        menubar.append(archivo)

        # Component
        componente = Gtk.MenuItem(label=_("Component"))
        componente_menu = Gtk.Menu()
        componente.set_submenu(componente_menu)
        item = Gtk.MenuItem(label=_("Add Component"))
        item.connect("activate", self.app.project_tree_view._on_add_component)
        item.set_sensitive(False)
        self._project_dependent_items.append(item)
        componente_menu.append(item)
        componente_menu.append(Gtk.SeparatorMenuItem())
        item = Gtk.MenuItem(label=_("Rename Component"))
        item.connect("activate", self.app.project_tree_view._on_menu_rename_component)
        item.set_sensitive(False)
        self._project_dependent_items.append(item)
        componente_menu.append(item)
        item = Gtk.MenuItem(label=_("Delete Component"))
        item.connect("activate", self.app.project_tree_view._on_menu_delete_component)
        item.set_sensitive(False)
        self._project_dependent_items.append(item)
        componente_menu.append(item)
        menubar.append(componente)

        # View
        ver = Gtk.MenuItem(label=_("View"))
        ver_menu = Gtk.Menu()
        ver.set_submenu(ver_menu)
        item = Gtk.MenuItem(label=_("Editor"))
        item.connect("activate", lambda w: self.app.editor_view._focus_editor())
        ver_menu.append(item)
        item = Gtk.MenuItem(label=_("Preview"))
        item.connect("activate", lambda w: self.app.editor_view._focus_preview())
        ver_menu.append(item)
        menubar.append(ver)

        # Export
        exportar = Gtk.MenuItem(label=_("Export"))
        exportar_menu = Gtk.Menu()
        exportar.set_submenu(exportar_menu)
        item = Gtk.MenuItem(label=_("Export EPUB"))
        item.connect("activate", self.app.export_import_ctrl.export_epub)
        item.set_sensitive(False)
        self._project_dependent_items.append(item)
        exportar_menu.append(item)
        item = Gtk.MenuItem(label=_("Open EPUB"))
        item.connect("activate", self.app.export_import_ctrl.open_epub)
        item.set_sensitive(False)
        self._project_dependent_items.append(item)
        exportar_menu.append(item)
        menubar.append(exportar)

        # Settings
        config = Gtk.MenuItem(label=_("Settings"))
        config_menu = Gtk.Menu()
        config.set_submenu(config_menu)
        self._project_config_menu_item = Gtk.MenuItem(label=_("Project"))
        self._project_config_menu_item.connect("activate", self._on_project_config)
        self._project_config_menu_item.set_sensitive(False)
        config_menu.append(self._project_config_menu_item)
        item = Gtk.MenuItem(label=_("Global"))
        item.connect("activate", self._on_global_config)
        config_menu.append(item)
        item = Gtk.MenuItem(label=_("Themes"))
        item.connect("activate", self._on_theme_manager)
        item.set_sensitive(False)
        self._project_dependent_items.append(item)
        config_menu.append(item)
        menubar.append(config)

        # Help
        ayuda = Gtk.MenuItem(label=_("Help"))
        ayuda_menu = Gtk.Menu()
        ayuda.set_submenu(ayuda_menu)
        libros_ejemplo = Gtk.MenuItem(label=_("Sample Books"))
        libros_menu = Gtk.Menu()
        libros_ejemplo.set_submenu(libros_menu)

        espanol_item = Gtk.MenuItem(label=_("Spanish"))
        espanol_menu = Gtk.Menu()
        espanol_item.set_submenu(espanol_menu)
        item = Gtk.MenuItem(label=_("Classic Novel"))
        item.connect("activate", self._on_load_sample_book, "sample_book")
        espanol_menu.append(item)
        item = Gtk.MenuItem(label=_("Textbook"))
        item.connect("activate", self._on_load_sample_book, "sample_book_textbook")
        espanol_menu.append(item)
        libros_menu.append(espanol_item)

        english_item = Gtk.MenuItem(label=_("English"))
        english_menu = Gtk.Menu()
        english_item.set_submenu(english_menu)
        item = Gtk.MenuItem(label=_("Classic Novel"))
        item.connect("activate", self._on_load_sample_book, "sample_book_en")
        english_menu.append(item)
        item = Gtk.MenuItem(label=_("Textbook"))
        item.connect("activate", self._on_load_sample_book, "sample_book_textbook_en")
        english_menu.append(item)
        libros_menu.append(english_item)

        ayuda_menu.append(libros_ejemplo)
        ayuda_menu.append(Gtk.SeparatorMenuItem())
        item = Gtk.MenuItem(label=_("About"))
        item.connect("activate", self._on_about)
        ayuda_menu.append(item)
        menubar.append(ayuda)

        container.pack_start(menubar, False, False, 0)

    # ─── Toolbar ──────────────────────────────────────────────────────

    def _setup_toolbar(self, container):
        toolbar = Gtk.Toolbar()
        toolbar.get_style_context().add_class("primary-toolbar")

        new_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("document-new-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        new_btn.set_label(_("New"))
        new_btn.set_tooltip_text(_("New Project"))
        new_btn.connect("clicked", self._on_new_project)
        toolbar.insert(new_btn, -1)

        open_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("folder-open-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        open_btn.set_label(_("Open"))
        open_btn.set_tooltip_text(_("Open Project"))
        open_btn.connect("clicked", self._on_open_project)
        toolbar.insert(open_btn, -1)

        self.app._toolbar_save_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("document-save-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        self.app._toolbar_save_btn.set_label(_("Save"))
        self.app._toolbar_save_btn.set_tooltip_text(_("Save"))
        self.app._toolbar_save_btn.connect("clicked", self._on_save_project)
        toolbar.insert(self.app._toolbar_save_btn, -1)

        sep1 = Gtk.SeparatorToolItem()
        toolbar.insert(sep1, -1)

        self._project_config_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("preferences-system-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        self._project_config_btn.set_label(_("Configure"))
        self._project_config_btn.set_tooltip_text(_("Project Settings"))
        self._project_config_btn.connect("clicked", self._on_project_config)
        self._project_config_btn.set_sensitive(False)
        toolbar.insert(self._project_config_btn, -1)

        sep2 = Gtk.SeparatorToolItem()
        toolbar.insert(sep2, -1)

        export_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("document-send-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        export_btn.set_label(_("Export EPUB"))
        export_btn.set_tooltip_text(_("Export EPUB"))
        export_btn.get_style_context().add_class("suggested-action")
        export_btn.connect("clicked", self.app.export_import_ctrl.export_epub)
        toolbar.insert(export_btn, -1)

        open_epub_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("x-office-document-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        open_epub_btn.set_label(_("Open EPUB"))
        open_epub_btn.set_tooltip_text(_("Open EPUB"))
        open_epub_btn.connect("clicked", self.app.export_import_ctrl.open_epub)
        toolbar.insert(open_epub_btn, -1)

        container.pack_start(toolbar, False, False, 0)

    # ─── Statusbar ────────────────────────────────────────────────────

    def _setup_statusbar(self, container):
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        status_box.set_margin_top(4)
        status_box.set_margin_bottom(4)
        status_box.set_margin_start(8)
        status_box.set_margin_end(8)
        container.pack_start(status_box, False, False, 0)

        self.app.status_label = Gtk.Label(label=_("Ready"))
        self.app.status_label.set_xalign(0)
        self.app.status_label.set_hexpand(True)
        status_box.pack_start(self.app.status_label, True, True, 0)

        self.app.project_label = Gtk.Label(label="")
        self.app.project_label.set_xalign(1)
        status_box.pack_end(self.app.project_label, False, False, 0)

    def update_project_sensitivity(self, has_project: bool):
        """Enable/disable project-dependent UI elements."""
        for item in self._project_dependent_items:
            item.set_sensitive(has_project)
        if self._project_config_btn:
            self._project_config_btn.set_sensitive(has_project)
        if self._project_config_menu_item:
            self._project_config_menu_item.set_sensitive(has_project)

    # ─── Project lifecycle ────────────────────────────────────────────

    def _confirm_discard_project(self):
        if self.app.project is None:
            return True
        return confirm(self.app.window, _("The current project will be closed. Continue?"))

    def _on_new_project(self, button):
        if not self._confirm_discard_project():
            return
        dialog = Gtk.Dialog(
            title=_("New Project"),
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Create"), Gtk.ResponseType.ACCEPT)
        dialog.set_default_size(500, -1)

        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        folder_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        folder_label = Gtk.Label(label=_("Parent folder:"))
        folder_label.set_size_request(80, -1)
        folder_box.pack_start(folder_label, False, False, 0)

        self.folder_chooser_btn = Gtk.Button(label=GLib.get_home_dir())
        self.folder_chooser_btn.set_hexpand(True)
        self.selected_folder = GLib.get_home_dir()

        def on_folder_clicked(btn):
            fc_dialog = Gtk.FileChooserNative(
                title=_("Select folder"),
                transient_for=dialog,
                action=Gtk.FileChooserAction.SELECT_FOLDER,
                accept_label=_("_Select"),
                cancel_label=_("_Cancel"),
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
        name_label = Gtk.Label(label=_("Name:"))
        name_label.set_size_request(80, -1)
        name_box.pack_start(name_label, False, False, 0)
        entry_name = Gtk.Entry()
        entry_name.set_hexpand(True)
        entry_name.set_placeholder_text("mi_libro")
        name_box.pack_start(entry_name, True, True, 0)
        content.add(name_box)

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        title_label = Gtk.Label(label=_("Title:"))
        title_label.set_size_request(80, -1)
        title_box.pack_start(title_label, False, False, 0)
        entry_title = Gtk.Entry()
        entry_title.set_hexpand(True)
        entry_title.set_placeholder_text("Mi Gran Libro")
        title_box.pack_start(entry_title, True, True, 0)
        content.add(title_box)

        author_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        author_label = Gtk.Label(label=_("Author:"))
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
                    show_error(self.app.window, _("Project name is required"))
                    d.destroy()
                    return

                project_path = FileService.create_project_structure(self.selected_folder, name)
                project_path.title = title
                project_path.author = author
                FileService.save_project(project_path)

                self.app.project = project_path
                self.update_project_sensitivity(True)
                self.app.editor_view._update_spell_lang()
                self.app.current_component = None
                self.app.project_tree_view._set_read_only_mode(False)
                self._add_recent_project(project_path.path)
                self.app.project_tree_view._refresh_project_tree()
                self.app._update_status(_("Project created: {name}").format(name=name))

            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_open_project(self, button):
        if not self._confirm_discard_project():
            return
        dialog = Gtk.FileChooserNative(
            title=_("Open Project"),
            transient_for=self.app.window,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            accept_label=_("_Open"),
            cancel_label=_("_Cancel"),
        )
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            path = dialog.get_filename()
            if path:
                yaml_file = os.path.join(path, "project.yaml")
                if os.path.exists(yaml_file):
                    project = FileService.load_project(path)
                    if project:
                        self.app.project = project
                        self.update_project_sensitivity(True)
                        self.app.editor_view._update_spell_lang()
                        self.app.current_component = None
                        self.app.project_tree_view._set_read_only_mode(False)
                        self._add_recent_project(project.path)
                        self.app.project_tree_view._refresh_project_tree()
                        self.app.text_view.get_buffer().set_text("")
                        self.app._update_status(_("Project opened: {name}").format(name=project.name))
                    else:
                        show_error(self.app.window, _("Error loading project"))
                else:
                    show_error(self.app.window, _("No project.yaml found in this folder"))
        dialog.destroy()

    def _on_save_project(self, button):
        if not self.app.project:
            show_info(self.app.window, _("No project open"))
            return
        if self.app._read_only:
            return
        if self.app.current_component:
            self.app.project_manager.save_component_content()
        FileService.save_project(self.app.project)
        self.app._update_status(_("Project saved"))

    def _on_save_project_as(self, button):
        if not self.app.project:
            show_info(self.app.window, _("No project open"))
            return
        if self.app._read_only:
            return
        dialog = Gtk.FileChooserNative(
            title=_("Save Project As"),
            transient_for=self.app.window,
            action=Gtk.FileChooserAction.SELECT_FOLDER,
            accept_label=_("_Save"),
            cancel_label=_("_Cancel"),
        )
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            path = dialog.get_filename()
            if path:
                new_project = FileService.create_project_structure(path, self.app.project.name)
                new_project.title = self.app.project.title
                new_project.author = self.app.project.author
                new_project.language = self.app.project.language
                new_project.theme_id = self.app.project.theme_id
                new_project.epub_version = self.app.project.epub_version
                new_project.figure_numbering = self.app.project.figure_numbering
                new_project.figure_numbering_style = self.app.project.figure_numbering_style
                new_project.table_numbering = self.app.project.table_numbering
                new_project.table_numbering_style = self.app.project.table_numbering_style
                new_project.chapter_numbering_style = self.app.project.chapter_numbering_style
                new_project.appendix_numbering_style = self.app.project.appendix_numbering_style
                new_project.part_numbering_style = self.app.project.part_numbering_style
                new_project.edition = self.app.project.edition
                new_project.isbn = self.app.project.isbn
                new_project.publisher = self.app.project.publisher
                new_project.subtitle = self.app.project.subtitle

                old_components_dir = os.path.join(self.app.project.path, "components")
                new_components_dir = os.path.join(new_project.path, "components")
                if os.path.exists(old_components_dir):
                    for item in os.listdir(old_components_dir):
                        src = os.path.join(old_components_dir, item)
                        dst = os.path.join(new_components_dir, item)
                        if os.path.isfile(src):
                            shutil.copy2(src, dst)

                for comp in self.app.project.components:
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
                self.app.project = new_project
                self._add_recent_project(new_project.path)
                self.app.project_tree_view._refresh_project_tree()
                self.app._update_status(_("Project saved to: {path}").format(path=new_project.path))
        dialog.destroy()

    def _on_load_sample_book(self, widget, book_dir="sample_book"):
        if not self._confirm_discard_project():
            return
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "data", book_dir)
        yaml_path = os.path.join(sample_dir, "project.yaml")
        if not os.path.exists(yaml_path):
            show_error(self.app.window, _("Sample book not found"))
            return
        project = FileService.load_project(sample_dir)
        if project:
            self.app.project = project
            self.app.project.path = sample_dir
            self.update_project_sensitivity(True)
            self.app.editor_view._update_spell_lang()
            self.app.current_component = None
            self.app.project_tree_view._set_read_only_mode(True)
            self.app.project_tree_view._refresh_project_tree()
            self.app.text_view.get_buffer().set_text("")
            self.app._update_status(_("Sample book loaded: {name} [READ ONLY]").format(name=project.name))
        else:
            show_error(self.app.window, _("Error loading sample book"))

    # ─── About dialog ─────────────────────────────────────────────────

    @staticmethod
    def _get_app_version() -> str:
        try:
            from .._version import __version__
            return __version__
        except ImportError:
            return "dev"

    def _on_about(self, widget):
        dialog = Gtk.AboutDialog(
            transient_for=self.app.window,
            modal=True,
        )
        dialog.set_program_name(_("MDToEPUB"))
        dialog.set_version(self._get_app_version())
        dialog.set_comments(_("EPUB editor from Markdown"))
        dialog.set_license_type(Gtk.License.GPL_3_0)
        try:
            from gi.repository import GdkPixbuf
            icon_path = os.path.join(os.path.dirname(__file__), "..", "..",
                                      "data", "icons", "hicolor", "scalable",
                                      "apps", "com.github.mdtoepub.svg")
            if os.path.exists(icon_path):
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(icon_path, 128, 128)
                dialog.set_logo(pixbuf)
        except Exception:
            pass
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.show_all()

    # ─── Global config ────────────────────────────────────────────────

    def _on_global_config(self, action, param=None):
        config_dir = os.path.join(GLib.get_user_config_dir(), "mdtoepub")
        config_file = os.path.join(config_dir, "config.yaml")
        os.makedirs(config_dir, exist_ok=True)
        config = YamlService.load(config_file)

        if not config:
            config = {}
        config.setdefault("editor", {"font_size": 12, "tab_size": 4, "auto_save_interval": 30})
        config.setdefault("preview", {"zoom": 100})
        config.setdefault("general", {"window_width": 1200, "window_height": 800})
        config.setdefault("epub_reader_path", "")
        config.setdefault("ui_language", "")

        dialog = Gtk.Dialog(
            title=_("Global Settings"),
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Save"), Gtk.ResponseType.ACCEPT)
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
        notebook.append_page(editor_page, Gtk.Label(label=_("Editor")))

        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(12)
        grid.set_hexpand(True)
        editor_page.pack_start(grid, False, False, 0)

        row = 0
        label = Gtk.Label(label=_("Font size:"))
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        spin_font_size = Gtk.SpinButton()
        spin_font_size.set_range(8, 48)
        spin_font_size.set_value(config.get("editor", {}).get("font_size", 12))
        grid.attach(spin_font_size, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label=_("Tab size:"))
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        spin_tab = Gtk.SpinButton()
        spin_tab.set_range(2, 8)
        spin_tab.set_value(config.get("editor", {}).get("tab_size", 4))
        grid.attach(spin_tab, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label=_("Auto-save (s):"))
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
        notebook.append_page(general_page, Gtk.Label(label=_("General")))

        grid_general = Gtk.Grid()
        grid_general.set_row_spacing(8)
        grid_general.set_column_spacing(12)
        grid_general.set_hexpand(True)
        general_page.pack_start(grid_general, False, False, 0)

        reader_row = 0
        reader_label = Gtk.Label(label=_("EPUB reader:"))
        reader_label.set_xalign(1)
        grid_general.attach(reader_label, 0, reader_row, 1, 1)

        reader_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entry_reader = Gtk.Entry()
        entry_reader.set_hexpand(True)
        entry_reader.set_placeholder_text(_("Leave empty to use system viewer"))
        entry_reader.set_text(config.get("epub_reader_path", ""))
        reader_box.pack_start(entry_reader, True, True, 0)

        def on_reader_browse(btn):
            fc = Gtk.FileChooserNative(
                title=_("Select EPUB reader"),
                transient_for=dialog,
                action=Gtk.FileChooserAction.OPEN,
                accept_label=_("_Select"),
                cancel_label=_("_Cancel"),
            )
            response = fc.run()
            if response == Gtk.ResponseType.ACCEPT:
                entry_reader.set_text(fc.get_filename())
            fc.destroy()

        browse_btn = Gtk.Button(label=_("Browse..."))
        browse_btn.connect("clicked", on_reader_browse)
        reader_box.pack_start(browse_btn, False, False, 0)
        grid_general.attach(reader_box, 1, reader_row, 1, 1)

        # UI language selector
        reader_row += 1
        lang_label = Gtk.Label(label=_("UI Language:"))
        lang_label.set_xalign(1)
        grid_general.attach(lang_label, 0, reader_row, 1, 1)

        lang_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        combo_lang = Gtk.ComboBoxText()
        combo_lang.append_text(_("Auto (system)"))
        combo_lang.append_text("English")
        combo_lang.append_text("Español")
        current_lang = config.get("ui_language", "").strip()
        if current_lang == "en":
            combo_lang.set_active(1)
        elif current_lang == "es":
            combo_lang.set_active(2)
        else:
            combo_lang.set_active(0)
        lang_box.pack_start(combo_lang, True, True, 0)
        grid_general.attach(lang_box, 1, reader_row, 1, 1)

        def on_global_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                config["editor"]["font_size"] = int(spin_font_size.get_value())
                config["editor"]["tab_size"] = int(spin_tab.get_value())
                config["editor"]["auto_save_interval"] = int(spin_auto.get_value())
                config["epub_reader_path"] = entry_reader.get_text().strip()
                lang_idx = combo_lang.get_active()
                lang_map = {0: "", 1: "en", 2: "es"}
                config["ui_language"] = lang_map.get(lang_idx, "")
                YamlService.save(config, config_file)
                from ..i18n import setup_i18n
                setup_i18n(config)
                show_info(self.app.window, _("Global settings saved. Please restart the application for language changes to take full effect."))
            d.destroy()

        dialog.connect("response", on_global_response)
        dialog.show_all()

    # ─── Dialog wrappers ──────────────────────────────────────────────

    def _on_project_config(self, button):
        from .dialogs.project_config import show_project_config
        show_project_config(self.app)

    def _on_theme_manager(self, widget):
        from .dialogs.theme_manager import show_theme_manager
        show_theme_manager(self.app)

    # ─── Recent projects ──────────────────────────────────────────────

    def load_recent_projects(self):
        config = None
        try:
            config_dir = os.path.join(GLib.get_user_config_dir(), "mdtoepub")
            config_file = os.path.join(config_dir, "config.yaml")
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
        config_dir = os.path.join(GLib.get_user_config_dir(), "mdtoepub")
        os.makedirs(config_dir, exist_ok=True)
        config_file = os.path.join(config_dir, "config.yaml")
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
            item = Gtk.MenuItem(label=_("(no recent projects)"))
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
            show_error(self.app.window, _("Project no longer exists:\n{path}").format(path=path))
            self._recent_projects = [p for p in self._recent_projects if p != path]
            self._save_recent_projects()
            self._rebuild_recent_menu()
            return
        project = FileService.load_project(path)
        if project:
            self.app.project = project
            self.update_project_sensitivity(True)
            self.app.editor_view._update_spell_lang()
            self.app.current_component = None
            self.app.project_tree_view._set_read_only_mode(False)
            self.app.project_tree_view._refresh_project_tree()
            self.app.text_view.get_buffer().set_text("")
            self.app._update_status(_("Project opened: {name}").format(name=project.name))
            self._add_recent_project(path)
        else:
            show_error(self.app.window, _("Error loading project"))

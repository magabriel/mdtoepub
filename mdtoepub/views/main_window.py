import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


class MainWindow:
    def __init__(self, app):
        self.app = app

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

    def _setup_menubar(self, container):
        menubar = Gtk.MenuBar()

        # Archivo
        archivo = Gtk.MenuItem(label="Archivo")
        archivo_menu = Gtk.Menu()
        archivo.set_submenu(archivo_menu)
        item = Gtk.MenuItem(label="Nuevo proyecto")
        item.connect("activate", self.app._on_new_project)
        archivo_menu.append(item)
        item = Gtk.MenuItem(label="Abrir proyecto")
        item.connect("activate", self.app._on_open_project)
        archivo_menu.append(item)
        item = Gtk.MenuItem(label="Guardar")
        item.connect("activate", self.app._on_save_project)
        archivo_menu.append(item)
        item = Gtk.MenuItem(label="Guardar como")
        item.connect("activate", self.app._on_save_project_as)
        archivo_menu.append(item)
        archivo_menu.append(Gtk.SeparatorMenuItem())
        item = Gtk.MenuItem(label="Cerrar proyecto")
        item.connect("activate", self.app._on_close_project)
        archivo_menu.append(item)
        archivo_menu.append(Gtk.SeparatorMenuItem())
        self.app._recent_menu = Gtk.Menu()
        recent_item = Gtk.MenuItem(label="Proyectos recientes")
        recent_item.set_submenu(self.app._recent_menu)
        archivo_menu.append(recent_item)
        archivo_menu.append(Gtk.SeparatorMenuItem())
        item = Gtk.MenuItem(label="Importar libro...")
        item.connect("activate", self.app._on_import_book)
        archivo_menu.append(item)
        item = Gtk.MenuItem(label="Importar libro EPUB...")
        item.connect("activate", self.app._on_import_epub)
        archivo_menu.append(item)
        archivo_menu.append(Gtk.SeparatorMenuItem())
        item = Gtk.MenuItem(label="Salir")
        item.connect("activate", lambda w: self.app.window.destroy())
        archivo_menu.append(item)
        menubar.append(archivo)

        # Componente
        componente = Gtk.MenuItem(label="Componente")
        componente_menu = Gtk.Menu()
        componente.set_submenu(componente_menu)
        item = Gtk.MenuItem(label="Anadir componente")
        item.connect("activate", self.app._on_add_component)
        componente_menu.append(item)
        componente_menu.append(Gtk.SeparatorMenuItem())
        item = Gtk.MenuItem(label="Renombrar componente")
        item.connect("activate", self.app._on_menu_rename_component)
        componente_menu.append(item)
        item = Gtk.MenuItem(label="Eliminar componente")
        item.connect("activate", self.app._on_menu_delete_component)
        componente_menu.append(item)
        menubar.append(componente)

        # Ver
        ver = Gtk.MenuItem(label="Ver")
        ver_menu = Gtk.Menu()
        ver.set_submenu(ver_menu)
        item = Gtk.MenuItem(label="Editor")
        item.connect("activate", lambda w: self.app._focus_editor())
        ver_menu.append(item)
        item = Gtk.MenuItem(label="Preview")
        item.connect("activate", lambda w: self.app._focus_preview())
        ver_menu.append(item)
        menubar.append(ver)

        # Exportar
        exportar = Gtk.MenuItem(label="Exportar")
        exportar_menu = Gtk.Menu()
        exportar.set_submenu(exportar_menu)
        item = Gtk.MenuItem(label="Exportar EPUB")
        item.connect("activate", self.app._on_export_epub)
        exportar_menu.append(item)
        item = Gtk.MenuItem(label="Abrir EPUB")
        item.connect("activate", self.app._on_open_epub)
        exportar_menu.append(item)
        menubar.append(exportar)

        # Configuracion
        config = Gtk.MenuItem(label="Configuracion")
        config_menu = Gtk.Menu()
        config.set_submenu(config_menu)
        item = Gtk.MenuItem(label="Proyecto")
        item.connect("activate", self.app._on_project_config)
        config_menu.append(item)
        item = Gtk.MenuItem(label="Global")
        item.connect("activate", lambda w: self.app._on_global_config(None, None))
        config_menu.append(item)
        item = Gtk.MenuItem(label="Temas")
        item.connect("activate", self.app._on_theme_manager)
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
        item.connect("activate", self.app._on_load_sample_book, "sample_book")
        libros_menu.append(item)
        item = Gtk.MenuItem(label="Libro de texto")
        item.connect("activate", self.app._on_load_sample_book, "sample_book_textbook")
        libros_menu.append(item)
        ayuda_menu.append(libros_ejemplo)
        ayuda_menu.append(Gtk.SeparatorMenuItem())
        item = Gtk.MenuItem(label="Acerca de")
        item.connect("activate", self.app._on_about)
        ayuda_menu.append(item)
        menubar.append(ayuda)

        container.pack_start(menubar, False, False, 0)

    def _setup_toolbar(self, container):
        toolbar = Gtk.Toolbar()
        toolbar.get_style_context().add_class("primary-toolbar")

        new_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("document-new-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        new_btn.set_label("Nuevo")
        new_btn.set_tooltip_text("Nuevo proyecto")
        new_btn.connect("clicked", self.app._on_new_project)
        toolbar.insert(new_btn, -1)

        open_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("folder-open-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        open_btn.set_label("Abrir")
        open_btn.set_tooltip_text("Abrir proyecto")
        open_btn.connect("clicked", self.app._on_open_project)
        toolbar.insert(open_btn, -1)

        self.app._toolbar_save_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("document-save-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        self.app._toolbar_save_btn.set_label("Guardar")
        self.app._toolbar_save_btn.set_tooltip_text("Guardar proyecto")
        self.app._toolbar_save_btn.connect("clicked", self.app._on_save_project)
        toolbar.insert(self.app._toolbar_save_btn, -1)

        sep1 = Gtk.SeparatorToolItem()
        toolbar.insert(sep1, -1)

        project_config_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("preferences-system-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        project_config_btn.set_label("Configurar")
        project_config_btn.set_tooltip_text("Configuracion del proyecto")
        project_config_btn.connect("clicked", self.app._on_project_config)
        toolbar.insert(project_config_btn, -1)

        sep2 = Gtk.SeparatorToolItem()
        toolbar.insert(sep2, -1)

        export_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("document-send-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        export_btn.set_label("Exportar EPUB")
        export_btn.set_tooltip_text("Exportar a EPUB")
        export_btn.get_style_context().add_class("suggested-action")
        export_btn.connect("clicked", self.app._on_export_epub)
        toolbar.insert(export_btn, -1)

        open_epub_btn = Gtk.ToolButton(icon_widget=Gtk.Image.new_from_icon_name("document-open-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        open_epub_btn.set_label("Abrir EPUB")
        open_epub_btn.set_tooltip_text("Abrir EPUB generado")
        open_epub_btn.connect("clicked", self.app._on_open_epub)
        toolbar.insert(open_epub_btn, -1)

        container.pack_start(toolbar, False, False, 0)

    def _setup_statusbar(self, container):
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        status_box.set_margin_top(4)
        status_box.set_margin_bottom(4)
        status_box.set_margin_start(8)
        status_box.set_margin_end(8)
        container.pack_start(status_box, False, False, 0)

        self.app.status_label = Gtk.Label(label="Listo")
        self.app.status_label.set_xalign(0)
        self.app.status_label.set_hexpand(True)
        status_box.pack_start(self.app.status_label, True, True, 0)

        self.app.project_label = Gtk.Label(label="")
        self.app.project_label.set_xalign(1)
        status_box.pack_end(self.app.project_label, False, False, 0)

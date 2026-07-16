#!/usr/bin/env python3
import sys
import os

if sys.platform == "linux":
    system_paths = ["/usr/lib/python3/dist-packages"]
    for path in system_paths:
        if path not in sys.path:
            sys.path.insert(0, path)

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk, Gio, GLib

from .services.markdown_service import MarkdownService


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
        self._last_epub_path = None
        self._in_cursor_change = False
        self._read_only = False
        self._dev_mode = os.environ.get("MDTOEPUB_DEV") == "1"
        self._toolbar_save_btn = None
        self._styles_current_component = None
        self._styles_current_comp_type = None

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

        from .controllers.project_manager import ProjectManager
        from .views.project_tree import ProjectTree
        from .views.styles_panel import StylesPanel
        from .views.editor_view import EditorView
        from .views.main_window import MainWindow
        from .controllers.export_import import ExportImportController

        self.project_manager = ProjectManager(self)
        self.project_tree_view = ProjectTree(self)
        self._styles_panel = StylesPanel(self)
        self.editor_view = EditorView(self)
        self.export_import_ctrl = ExportImportController(self)

        self.main_window = MainWindow(self)
        left_box, right_box = self.main_window.build(main_box)

        self._styles_scrolled = self._styles_panel.build()
        self.editor_view.build(right_box)
        self.project_tree_view.build(left_box)
        self.project_tree = self.project_tree_view.project_tree

        self.window.add(main_box)
        self.window.show_all()
        self.main_window.load_recent_projects()

    def _update_status(self, message):
        self.status_label.set_text(message)

    def _get_config_path(self) -> tuple:
        config_dir = os.path.join(GLib.get_user_config_dir(), "mdtoepub")
        os.makedirs(config_dir, exist_ok=True)
        config_file = os.path.join(config_dir, "config.yaml")
        return config_dir, config_file


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

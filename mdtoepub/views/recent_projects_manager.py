import os

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from ..services.file_service import FileService
from ..services.yaml_service import YamlService
from ..utils.dialogs import show_error

from ..i18n import _


class RecentProjectsManager:
    """Manages the list of recently opened projects."""

    MAX_RECENT = 10

    def __init__(self, app, recent_menu):
        """Initialize with the application and recent projects menu.

        Args:
            app: The application instance.
            recent_menu: The GTK Menu to populate with recent projects.
        """
        self.app = app
        self._recent_menu = recent_menu
        self._recent_projects = []

    def load(self):
        """Load recent projects from the global config file."""
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
        self._rebuild_menu()

    def add(self, project_path):
        """Add a project path to the recent list and rebuild the menu.

        Args:
            project_path: Absolute path to the project directory.
        """
        if project_path in self._recent_projects:
            self._recent_projects.remove(project_path)
        self._recent_projects.insert(0, project_path)
        self._recent_projects = self._recent_projects[:self.MAX_RECENT]
        self._save()
        self._rebuild_menu()

    def _save(self):
        """Save the recent projects list to the global config file."""
        config_dir = os.path.join(GLib.get_user_config_dir(), "mdtoepub")
        os.makedirs(config_dir, exist_ok=True)
        config_file = os.path.join(config_dir, "config.yaml")
        config = YamlService.load(config_file)
        config["recent_projects"] = self._recent_projects
        YamlService.save(config, config_file)

    def _rebuild_menu(self):
        """Rebuild the recent projects menu from the current list."""
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
        """Open a recent project by path.

        Args:
            path: Absolute path to the project directory.
        """
        if not self.app.main_window._confirm_discard_project():
            return
        yaml_file = os.path.join(path, "project.yaml")
        if not os.path.exists(yaml_file):
            show_error(self.app.window, _("Project no longer exists:\n{path}").format(path=path))
            self._recent_projects = [p for p in self._recent_projects if p != path]
            self._save()
            self._rebuild_menu()
            return
        project = FileService.load_project(path)
        if project:
            self.app.project = project
            self.app.main_window.update_project_sensitivity(True)
            self.app.editor_view.update_spell_lang()
            self.app.current_component = None
            self.app.project_tree_view.set_read_only_mode(False)
            self.app.project_tree_view.refresh_project_tree()
            self.app.text_view.get_buffer().set_text("")
            self.app.update_status(_("Project opened: {name}").format(name=project.name))
            self.add(path)
        else:
            show_error(self.app.window, _("Error loading project"))

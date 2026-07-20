import os

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk, GtkSource

from ...services.file_service import FileService
from ...services.theme_service import ThemeService
from ...services.yaml_service import YamlService

from ...i18n import _


def _show_info(parent, message):
    """Show an info dialog."""
    d = Gtk.MessageDialog(
        transient_for=parent, modal=True,
        message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK,
        text=message,
    )
    d.run()
    d.destroy()


class ThemeManagerDialog:
    """Theme manager dialog for viewing, activating, creating, and managing themes."""

    def __init__(self, app):
        """Initialize with the application instance.

        Args:
            app: The application instance.
        """
        self.app = app
        self.dialog = None
        self.store = None
        self.tree = None
        self.btn_view_css = None
        self.btn_rename = None
        self.btn_delete = None

    def show(self):
        """Show the theme manager dialog."""
        if not self.app.project:
            _show_info(self.app.window, _("Open a project first"))
            return

        self.dialog = Gtk.Dialog(
            title=_("Theme Manager"),
            transient_for=self.app.window,
            modal=True,
        )
        self.dialog.add_button(_("Close"), Gtk.ResponseType.CLOSE)
        self.dialog.set_default_size(650, 500)

        content = self.dialog.get_content_area()
        content.set_spacing(8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        self.store = Gtk.ListStore(str, str, str, str)
        self._refresh_theme_store()

        self.tree = Gtk.TreeView(model=self.store)
        self.tree.set_headers_visible(True)

        r_name = Gtk.CellRendererText()
        c_name = Gtk.TreeViewColumn(_("Theme"), r_name, text=0)
        c_name.set_resizable(True)
        c_name.set_expand(True)
        self.tree.append_column(c_name)

        r_id = Gtk.CellRendererText()
        c_id = Gtk.TreeViewColumn("ID", r_id, text=1)
        c_id.set_resizable(True)
        self.tree.append_column(c_id)

        r_active = Gtk.CellRendererText()
        c_active = Gtk.TreeViewColumn(_("Active"), r_active, text=2)
        self.tree.append_column(c_active)

        r_type = Gtk.CellRendererText()
        c_type = Gtk.TreeViewColumn(_("Type"), r_type, text=3)
        self.tree.append_column(c_type)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.add(self.tree)
        content.pack_start(scrolled, True, True, 0)

        btn_box = Gtk.Box(spacing=6)

        btn_activate = Gtk.Button(label=_("Activate Theme"))
        btn_activate.connect("clicked", lambda b: self._on_activate_theme())
        btn_box.pack_start(btn_activate, False, False, 0)

        btn_create = Gtk.Button(label=_("Create Blank Theme"))
        btn_create.connect("clicked", lambda b: self._on_create_blank_theme())
        btn_box.pack_start(btn_create, False, False, 0)

        btn_clone = Gtk.Button(label=_("Clone Theme"))
        btn_clone.connect("clicked", lambda b: self._on_clone_theme())
        btn_box.pack_start(btn_clone, False, False, 0)

        self.btn_view_css = Gtk.Button(label=_("View CSS"))
        self.btn_view_css.connect("clicked", lambda b: self._on_view_theme_css())
        btn_box.pack_start(self.btn_view_css, False, False, 0)

        self.btn_rename = Gtk.Button(label=_("Rename"))
        self.btn_rename.connect("clicked", lambda b: self._on_rename_theme())
        btn_box.pack_start(self.btn_rename, False, False, 0)

        self.btn_delete = Gtk.Button(label=_("Delete"))
        self.btn_delete.connect("clicked", lambda b: self._on_delete_theme())
        btn_box.pack_start(self.btn_delete, False, False, 0)

        btn_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)

        btn_export = Gtk.Button(label=_("Export"))
        btn_export.connect("clicked", lambda b: self._on_export_theme())
        btn_box.pack_start(btn_export, False, False, 0)

        btn_import = Gtk.Button(label=_("Import"))
        btn_import.connect("clicked", lambda b: self._on_import_theme())
        btn_box.pack_start(btn_import, False, False, 0)

        content.pack_start(btn_box, False, False, 0)

        self.tree.get_selection().connect("changed", self._on_selection_changed)
        self._on_selection_changed(self.tree.get_selection())

        self.dialog.show_all()
        self.dialog.connect("response", lambda d, r: d.destroy())

    def _refresh_theme_store(self):
        """Refresh the theme list store from ThemeService."""
        self.store.clear()
        themes_list = ThemeService.list_themes()
        for theme in themes_list:
            is_active = _("Yes") if theme.id == self.app.project.theme_id else ""
            type_label = _("Built-in") if theme.is_builtin else _("Custom")
            self.store.append([theme.name, theme.id, is_active, type_label])

    def _on_selection_changed(self, sel):
        """Handle tree selection changes to update button sensitivity."""
        model, iter_ = sel.get_selected()
        if iter_ is not None:
            type_label = model.get_value(iter_, 3)
            is_custom = type_label == _("Custom")
            self.btn_view_css.set_label(_("Edit CSS") if is_custom else _("View CSS"))
            self.btn_rename.set_sensitive(is_custom)
            self.btn_delete.set_sensitive(is_custom)
        else:
            self.btn_view_css.set_label(_("View CSS"))
            self.btn_rename.set_sensitive(False)
            self.btn_delete.set_sensitive(False)

    def _get_selected_theme(self):
        """Get the selected theme from the tree view.

        Returns:
            Tuple of (model, iter_, theme_id, theme_name, type_label) or None if nothing selected.
        """
        sel = self.tree.get_selection()
        model, iter_ = sel.get_selected()
        if iter_ is None:
            return None
        theme_id = model.get_value(iter_, 1)
        theme_name = model.get_value(iter_, 0)
        type_label = model.get_value(iter_, 3)
        return model, iter_, theme_id, theme_name, type_label

    def _on_activate_theme(self):
        """Activate the selected theme."""
        selected = self._get_selected_theme()
        if not selected:
            return
        _, _, theme_id, theme_name, _ = selected
        if theme_id:
            self.app.project.theme_id = theme_id
            FileService.save_project(self.app.project)
            self.app.style_doc_svc = None
            self._refresh_theme_store()
            self.app.editor_view.update_preview()
            self.app.styles_panel.update(
                self.app.current_component.type if self.app.current_component else None
            )
            self.app.update_status(_("Theme activated: {name}").format(name=theme_name))
            self.dialog.destroy()

    def _on_create_blank_theme(self):
        """Show dialog to create a blank theme."""
        dialog = Gtk.Dialog(
            title=_("Create Blank Theme"),
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Create"), Gtk.ResponseType.ACCEPT)
        dialog.set_default_size(400, 200)

        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        grid = Gtk.Grid(row_spacing=6, column_spacing=6)
        row = 0

        label = Gtk.Label(label=_("Name:"))
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        entry_name = Gtk.Entry()
        grid.attach(entry_name, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label=_("Description:"))
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        entry_desc = Gtk.Entry()
        grid.attach(entry_desc, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label=_("Author:"))
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        entry_author = Gtk.Entry()
        grid.attach(entry_author, 1, row, 1, 1)

        content.pack_start(grid, False, False, 0)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                name = entry_name.get_text().strip()
                if not name:
                    _show_info(self.app.window, _("Name is required"))
                    return
                theme = ThemeService.create_blank(
                    name=name,
                    description=entry_desc.get_text().strip(),
                    author=entry_author.get_text().strip(),
                )
                if theme:
                    self._refresh_theme_store()
                    self.app.update_status(_("Theme created: {name}").format(name=name))
                else:
                    _show_info(self.app.window, _("Could not create theme (ID already exists)"))
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_clone_theme(self):
        """Show dialog to clone the selected theme."""
        selected = self._get_selected_theme()
        if not selected:
            _show_info(self.app.window, _("Select a theme to clone"))
            return

        _, _, source_id, source_name, _ = selected

        dialog = Gtk.Dialog(
            title=_("Clone theme: {name}").format(name=source_name),
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Clone"), Gtk.ResponseType.ACCEPT)
        dialog.set_default_size(400, 250)

        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        grid = Gtk.Grid(row_spacing=6, column_spacing=6)
        row = 0

        label = Gtk.Label(label=_("Name:"))
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        entry_name = Gtk.Entry()
        entry_name.set_text(f"{source_name} ({_('copy')})")
        entry_name.select_region(0, -1)
        grid.attach(entry_name, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label=_("Description:"))
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        entry_desc = Gtk.Entry()
        grid.attach(entry_desc, 1, row, 1, 1)
        row += 1

        label = Gtk.Label(label=_("Author:"))
        label.set_xalign(1)
        grid.attach(label, 0, row, 1, 1)
        entry_author = Gtk.Entry()
        grid.attach(entry_author, 1, row, 1, 1)

        content.pack_start(grid, False, False, 0)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                name = entry_name.get_text().strip()
                if not name:
                    _show_info(self.app.window, _("Name is required"))
                    return
                theme = ThemeService.clone_theme(
                    source_id=source_id,
                    new_name=name,
                    description=entry_desc.get_text().strip(),
                    author=entry_author.get_text().strip(),
                )
                if theme:
                    self._refresh_theme_store()
                    self.app.update_status(_("Theme cloned: {name}").format(name=name))
                else:
                    _show_info(self.app.window, _("Could not clone theme (ID already exists)"))
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_view_theme_css(self):
        """View or edit CSS files for the selected theme."""
        selected = self._get_selected_theme()
        if not selected:
            return

        _, _, theme_id, theme_name, type_label = selected
        is_read_only = type_label == _("Built-in")

        theme = ThemeService.get_theme(theme_id)
        if not theme:
            return

        theme_dir = theme.path

        theme_config = {}
        tyaml = os.path.join(theme_dir, "theme.yaml")
        if os.path.exists(tyaml):
            theme_config = YamlService.load(tyaml)

        css_files = {"style.css": _("Base")}
        for comp_type, css_file in theme_config.get("styles", {}).items():
            if css_file not in css_files:
                css_files[css_file] = f"{_('Component')}: {comp_type}"

        mode_title = _("View") if is_read_only else _("Edit")
        editor_dialog = Gtk.Dialog(
            title=f"{mode_title} CSS: {theme_name}",
            transient_for=self.app.window,
            modal=True,
        )
        editor_dialog.add_button(_("Close"), Gtk.ResponseType.CLOSE)
        if not is_read_only:
            editor_dialog.add_button(_("Save"), Gtk.ResponseType.ACCEPT)
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
                self.app.update_status(_("CSS saved: {name}").format(name=fname))
                if self.app.project and self.app.project.theme_id == theme_id:
                    self.app.editor_view.update_preview()
                    self.app.styles_panel.update()
            d.destroy()

        editor_dialog.connect("response", on_editor_response)
        editor_dialog.show_all()

    def _on_rename_theme(self):
        """Rename the selected custom theme."""
        selected = self._get_selected_theme()
        if not selected:
            return

        _, _, theme_id, current_name, type_label = selected
        if type_label == _("Built-in"):
            _show_info(self.app.window, _("Built-in themes cannot be renamed"))
            return

        dialog = Gtk.Dialog(
            title=_("Rename theme"),
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Rename"), Gtk.ResponseType.ACCEPT)
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
                    self._refresh_theme_store()
                    self.app.update_status(_("Theme renamed: {name}").format(name=new_name))
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_delete_theme(self):
        """Delete the selected custom theme."""
        selected = self._get_selected_theme()
        if not selected:
            return

        _, _, theme_id, theme_name, type_label = selected
        if type_label == _("Built-in"):
            _show_info(self.app.window, _("Built-in themes cannot be deleted"))
            return

        if theme_id == self.app.project.theme_id:
            _show_info(self.app.window, _(
                "The theme '{name}' is in use.\n"
                "Switch to another theme before deleting it."
            ).format(name=theme_name))
            return

        confirm_dlg = Gtk.MessageDialog(
            transient_for=self.dialog,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Delete theme: {name}").format(name=theme_name),
        )
        confirm_dlg.format_secondary_text(
            _("This action cannot be undone.\n"
              "All theme files will be permanently deleted.")
        )
        resp = confirm_dlg.run()
        confirm_dlg.destroy()

        if resp == Gtk.ResponseType.YES:
            if ThemeService.delete_theme(theme_id):
                self._refresh_theme_store()
                self.app.update_status(_("Theme deleted: {name}").format(name=theme_name))
            else:
                _show_info(self.app.window, _("Could not delete theme"))

    def _on_export_theme(self):
        """Export the selected theme as a .mdtotheme file."""
        selected = self._get_selected_theme()
        if not selected:
            _show_info(self.app.window, _("Select a theme first"))
            return

        _, _, theme_id, theme_name, _ = selected

        dialog = Gtk.FileChooserNative(
            title=_("Export theme: {name}").format(name=theme_name),
            transient_for=self.app.window,
            action=Gtk.FileChooserAction.SAVE,
            accept_label=_("_Export"),
            cancel_label=_("_Cancel"),
        )
        dialog.set_current_name(f"{theme_id}.mdtotheme")

        f_filter = Gtk.FileFilter()
        f_filter.set_name(_("Theme files (*.mdtotheme)"))
        f_filter.add_pattern("*.mdtotheme")
        dialog.add_filter(f_filter)

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            output_path = dialog.get_filename()
            dialog.destroy()
            if not output_path.endswith(".mdtotheme"):
                output_path += ".mdtotheme"

            if ThemeService.export_theme(theme_id, output_path):
                self.app.update_status(_("Theme exported: {path}").format(path=output_path))
                _show_info(self.app.window, _("Theme '{name}' exported successfully.").format(name=theme_name))
            else:
                _show_info(self.app.window, _("Could not export theme '{name}'").format(name=theme_name))
        else:
            dialog.destroy()

    def _on_import_theme(self):
        """Import a theme from a .mdtotheme file."""
        dialog = Gtk.FileChooserNative(
            title=_("Import theme"),
            transient_for=self.app.window,
            action=Gtk.FileChooserAction.OPEN,
            accept_label=_("_Import"),
            cancel_label=_("_Cancel"),
        )

        f_filter = Gtk.FileFilter()
        f_filter.set_name(_("Theme files (*.mdtotheme)"))
        f_filter.add_pattern("*.mdtotheme")
        dialog.add_filter(f_filter)
        f_filter = Gtk.FileFilter()
        f_filter.set_name(_("All files"))
        f_filter.add_pattern("*")
        dialog.add_filter(f_filter)

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_filename()
            dialog.destroy()

            imported = ThemeService.import_theme(file_path)
            if imported:
                self._refresh_theme_store()
                self.app.update_status(_("Theme imported: {name}").format(name=imported.name))
                _show_info(self.app.window, _("Theme '{name}' imported successfully.").format(name=imported.name))
            else:
                _show_info(self.app.window, _(
                    "Could not import theme.\n"
                    "Make sure the file is a valid .mdtotheme."
                ))
        else:
            dialog.destroy()


def show_theme_manager(app):
    """Show the theme manager dialog.

    Args:
        app: The application instance.
    """
    dialog = ThemeManagerDialog(app)
    dialog.show()

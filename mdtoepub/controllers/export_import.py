from ..utils.dialogs import show_error, show_info, confirm
import gettext
import os
import subprocess

from gi.repository import GLib, Gtk

from ..services.file_service import FileService, slugify
from ..services.epub_service import EpubService
from ..services.yaml_service import YamlService

_ = gettext.gettext


class ExportImportController:
    def __init__(self, app):
        self.app = app

    def export_epub(self, button):
        if not self.app.project:
            show_info(self.app.window, _("No project open"))
            return

        self.app.project_manager.save_component_content()

        epub_name = self.app.project.export_filename or slugify(
            self.app.project.title or self.app.project.name
        )
        if not epub_name.endswith(".epub"):
            epub_name += ".epub"

        if self.app._read_only:
            output_dir = "/tmp/mdtoepub_export"
            epub_path = os.path.join(output_dir, epub_name)
        else:
            output_dir = os.path.join(self.app.project.path, "output")
            epub_path = os.path.join(output_dir, epub_name)

        save_dialog = Gtk.FileChooserNative(
            title=_("Save EPUB as..."),
            transient_for=self.app.window,
            action=Gtk.FileChooserAction.SAVE,
            accept_label=_("_Save"),
            cancel_label=_("_Cancel"),
        )
        save_dialog.set_current_name(epub_name)
        epub_filter = Gtk.FileFilter()
        epub_filter.set_name("EPUB (*.epub)")
        epub_filter.add_pattern("*.epub")
        save_dialog.add_filter(epub_filter)

        if not self.app._read_only and os.path.isdir(output_dir):
            save_dialog.set_current_folder(output_dir)
        else:
            save_dialog.set_current_folder(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS) or os.path.expanduser("~"))

        if save_dialog.run() == Gtk.ResponseType.ACCEPT:
            epub_path = save_dialog.get_filename()
            save_dialog.destroy()
        else:
            save_dialog.destroy()
            return

        if not epub_path.endswith(".epub"):
            epub_path += ".epub"

        os.makedirs(os.path.dirname(epub_path) or ".", exist_ok=True)
        if os.path.exists(epub_path):
            if not confirm(self.app.window, _("The file already exists:\n{path}\n\nOverwrite?").format(path=epub_path)):
                return
        epub_service = EpubService(self.app.project)
        _, config_file = self.app._get_config_path()
        global_config = YamlService.load(config_file)
        result = epub_service.generate(epub_path, self.app.project.epub_version, global_config=global_config)
        if result:
            self.app._last_epub_path = result
            self.app._update_status(_("EPUB exported: {path}").format(path=result))
            show_info(self.app.window, _("EPUB generated successfully:\n{path}").format(path=result))
        else:
            show_error(self.app.window, _("Error generating EPUB"))

    def import_book(self, button):
        if not self.app.project:
            show_info(self.app.window, _("No project open"))
            return
        if self.app._read_only:
            show_info(self.app.window, _("Cannot import into the sample book"))
            return

        dialog = Gtk.FileChooserNative(
            title=_("Import Markdown Book"),
            transient_for=self.app.window,
            action=Gtk.FileChooserAction.OPEN,
            accept_label=_("_Import"),
            cancel_label=_("_Cancel"),
        )

        f_filter = Gtk.FileFilter()
        f_filter.set_name(_("Markdown files (*.md)"))
        f_filter.add_pattern("*.md")
        dialog.add_filter(f_filter)
        f_filter = Gtk.FileFilter()
        f_filter.set_name(_("All files"))
        f_filter.add_pattern("*")
        dialog.add_filter(f_filter)

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_filename()
            dialog.destroy()

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                show_error(self.app.window, _("Error reading file: {error}").format(error=e))
                return

            if not content.strip():
                show_info(self.app.window, _("The file is empty"))
                return

            parsed = FileService.parse_imported_markdown(content)
            total_chars = sum(len(md) for _, _, md in parsed)
            desc_lines = [_("About to import {n} components:").format(n=len(parsed))]
            for ctype, title, md in parsed:
                title_str = f' \u2014 "{title}"' if title else ""
                desc_lines.append(f"  - {ctype}{title_str} ({len(md)} chars)")
            desc_lines.append("")
            desc_lines.append(_("Total: {n} characters in {m} components.").format(n=total_chars, m=len(parsed)))
            desc_lines.append("")
            desc_lines.append(_("New components will be added to existing ones."))

            confirm_dlg = Gtk.MessageDialog(
                parent=self.app.window,
                modal=True,
                type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text=_("Confirm Import"),
            )
            confirm_dlg.format_secondary_text("\n".join(desc_lines))

            if confirm_dlg.run() == Gtk.ResponseType.YES:
                confirm_dlg.destroy()
                count = FileService.import_book(self.app.project.path, self.app.project, content, file_path)
                self.app._update_status(_("Imported {n} components").format(n=count))
                self.app.project_tree_view._refresh_project_tree()
                self.app.editor_view._update_preview()
                show_info(self.app.window, _("Successfully imported {n} components.").format(n=count))
            else:
                confirm_dlg.destroy()
        else:
            dialog.destroy()

    def import_epub(self, button):
        if not self.app.project:
            show_info(self.app.window, _("No project open"))
            return
        if self.app._read_only:
            show_info(self.app.window, _("Cannot import into the sample book"))
            return

        dialog = Gtk.FileChooserNative(
            title=_("Import EPUB Book"),
            transient_for=self.app.window,
            action=Gtk.FileChooserAction.OPEN,
            accept_label=_("_Import"),
            cancel_label=_("_Cancel"),
        )

        f_filter = Gtk.FileFilter()
        f_filter.set_name(_("EPUB files (*.epub)"))
        f_filter.add_pattern("*.epub")
        dialog.add_filter(f_filter)
        f_filter = Gtk.FileFilter()
        f_filter.set_name(_("All files"))
        f_filter.add_pattern("*")
        dialog.add_filter(f_filter)

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_filename()
            dialog.destroy()

            try:
                components, images = FileService.parse_imported_epub(file_path)
            except Exception as e:
                show_error(self.app.window, _("Error reading EPUB: {error}").format(error=e))
                return

            if not components:
                show_info(self.app.window, _("The EPUB does not contain importable documents."))
                return

            total_chars = sum(len(md) for _, _, md in components)
            desc_lines = [_("About to import {n} components:").format(n=len(components))]
            for ctype, title, md in components:
                title_str = f' \u2014 "{title}"' if title else ""
                desc_lines.append(f"  - {ctype}{title_str} ({len(md)} chars)")
            desc_lines.append("")
            desc_lines.append(_("Images found: {n}").format(n=len(images)))
            desc_lines.append(_("Total: {n} characters in {m} components.").format(n=total_chars, m=len(components)))
            desc_lines.append("")
            desc_lines.append(_("New components will be added to existing ones."))

            confirm_dlg = Gtk.MessageDialog(
                parent=self.app.window,
                modal=True,
                type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text=_("Confirm Import"),
            )
            confirm_dlg.format_secondary_text("\n".join(desc_lines))

            if confirm_dlg.run() == Gtk.ResponseType.YES:
                confirm_dlg.destroy()
                count = FileService.import_epub(self.app.project.path, self.app.project, file_path)
                self.app._update_status(_("Imported {n} components").format(n=count))
                self.app.project_tree_view._refresh_project_tree()
                self.app.editor_view._update_preview()
                show_info(self.app.window, _("Successfully imported {n} components.").format(n=count))
            else:
                confirm_dlg.destroy()
        else:
            dialog.destroy()

    def open_epub(self, button):
        if not self.app._last_epub_path or not os.path.exists(self.app._last_epub_path):
            show_info(self.app.window, _("No EPUB generated. Export first."))
            return
        try:
            config_dir = os.path.join(GLib.get_user_config_dir(), "mdtoepub")
            config_file = os.path.join(config_dir, "config.yaml")
            config = YamlService.load(config_file) or {}
            reader_path = config.get("epub_reader_path", "").strip()
            if reader_path and os.path.exists(reader_path):
                subprocess.Popen([reader_path, self.app._last_epub_path])
            else:
                subprocess.Popen(["xdg-open", self.app._last_epub_path])
        except Exception as e:
            show_error(self.app.window, _("Could not open EPUB: {error}").format(error=e))

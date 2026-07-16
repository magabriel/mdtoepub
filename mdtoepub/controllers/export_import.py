import os
import subprocess

from gi.repository import GLib, Gtk

from ..services.file_service import FileService, slugify
from ..services.epub_service import EpubService
from ..services.yaml_service import YamlService


class ExportImportController:
    def __init__(self, app):
        self.app = app

    def export_epub(self, button):
        if not self.app.project:
            self.app._show_info("No hay proyecto abierto")
            return

        self.app._save_current_component()

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
            title="Guardar EPUB como...",
            transient_for=self.app.window,
            action=Gtk.FileChooserAction.SAVE,
            accept_label="_Guardar",
            cancel_label="_Cancelar",
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
            if not self.app._confirm(f"El archivo ya existe:\n{epub_path}\n\n¿Sobrescribirlo?"):
                return
        epub_service = EpubService(self.app.project)
        _, config_file = self.app._get_config_path()
        global_config = YamlService.load(config_file)
        result = epub_service.generate(epub_path, self.app.project.epub_version, global_config=global_config)
        if result:
            self.app._last_epub_path = result
            self.app._update_status(f"EPUB exportado: {result}")
            self.app._show_info(f"EPUB generado correctamente:\n{result}")
        else:
            self.app._show_error("Error al generar el EPUB")

    def import_book(self, button):
        if not self.app.project:
            self.app._show_info("No hay proyecto abierto")
            return
        if self.app._read_only:
            self.app._show_info("No se puede importar en el libro de ejemplo")
            return

        dialog = Gtk.FileChooserNative(
            title="Importar libro Markdown",
            transient_for=self.app.window,
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
                self.app._show_error(f"Error al leer el archivo: {e}")
                return

            if not content.strip():
                self.app._show_info("El archivo esta vacio")
                return

            parsed = FileService.parse_imported_markdown(content)
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
                parent=self.app.window,
                modal=True,
                type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text="Confirmar importacion",
            )
            confirm.format_secondary_text("\n".join(desc_lines))

            if confirm.run() == Gtk.ResponseType.YES:
                confirm.destroy()
                count = FileService.import_book(self.app.project.path, self.app.project, content, file_path)
                self.app._update_status(f"Importados {count} componentes")
                self.app.project_tree_view._refresh_project_tree()
                self.app.editor_view._update_preview()
                self.app._show_info(f"Se importaron {count} componentes correctamente.")
            else:
                confirm.destroy()
        else:
            dialog.destroy()

    def import_epub(self, button):
        if not self.app.project:
            self.app._show_info("No hay proyecto abierto")
            return
        if self.app._read_only:
            self.app._show_info("No se puede importar en el libro de ejemplo")
            return

        dialog = Gtk.FileChooserNative(
            title="Importar libro EPUB",
            transient_for=self.app.window,
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

            try:
                components, images = FileService.parse_imported_epub(file_path)
            except Exception as e:
                self.app._show_error(f"Error al leer el EPUB: {e}")
                return

            if not components:
                self.app._show_info("El EPUB no contiene documentos importables.")
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
                parent=self.app.window,
                modal=True,
                type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text="Confirmar importacion",
            )
            confirm.format_secondary_text("\n".join(desc_lines))

            if confirm.run() == Gtk.ResponseType.YES:
                confirm.destroy()
                count = FileService.import_epub(self.app.project.path, self.app.project, file_path)
                self.app._update_status(f"Importados {count} componentes")
                self.app.project_tree_view._refresh_project_tree()
                self.app.editor_view._update_preview()
                self.app._show_info(f"Se importaron {count} componentes correctamente.")
            else:
                confirm.destroy()
        else:
            dialog.destroy()

    def open_epub(self, button):
        if not self.app._last_epub_path or not os.path.exists(self.app._last_epub_path):
            self.app._show_info("No hay EPUB generado. Exportalo primero.")
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
            self.app._show_error(f"No se pudo abrir el EPUB: {e}")

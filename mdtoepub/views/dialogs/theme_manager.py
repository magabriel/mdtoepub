import os

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk, GtkSource

from ...services.file_service import FileService
from ...services.theme_service import ThemeService
from ...services.yaml_service import YamlService


def show_theme_manager(app):
    if not app.project:
        info_dlg = Gtk.MessageDialog(
            transient_for=app.window,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Abre un proyecto primero",
        )
        info_dlg.run()
        info_dlg.destroy()
        return

    themes = ThemeService.list_themes()

    def _refresh_theme_store(store):
        store.clear()
        themes_list = ThemeService.list_themes()
        for theme in themes_list:
            is_active = "Si" if theme.id == app.project.theme_id else ""
            type_label = "Integrado" if theme.is_builtin else "Personalizado"
            store.append([theme.name, theme.id, is_active, type_label])

    def _on_activate_theme(tree, store, dialog):
        sel = tree.get_selection()
        model, iter_ = sel.get_selected()
        if iter_ is None:
            return
        theme_id = model.get_value(iter_, 1)
        if theme_id:
            app.project.theme_id = theme_id
            FileService.save_project(app.project)
            app._style_doc_svc = None
            _refresh_theme_store(store)
            app.editor_view._update_preview()
            app._styles_panel.update(
                app.current_component.type if app.current_component else None
            )
            app._update_status(f"Tema activado: {model.get_value(iter_, 0)}")
            dialog.destroy()

    def _on_create_blank_theme(tree, store):
        dialog = Gtk.Dialog(
            title="Crear tema en blanco",
            transient_for=app.window,
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
                    info_dlg = Gtk.MessageDialog(
                        transient_for=app.window,
                        modal=True,
                        message_type=Gtk.MessageType.INFO,
                        buttons=Gtk.ButtonsType.OK,
                        text="El nombre es obligatorio",
                    )
                    info_dlg.run()
                    info_dlg.destroy()
                    return
                theme = ThemeService.create_blank(
                    name=name,
                    description=entry_desc.get_text().strip(),
                    author=entry_author.get_text().strip(),
                )
                if theme:
                    _refresh_theme_store(store)
                    app._update_status(f"Tema creado: {name}")
                else:
                    info_dlg = Gtk.MessageDialog(
                        transient_for=app.window,
                        modal=True,
                        message_type=Gtk.MessageType.INFO,
                        buttons=Gtk.ButtonsType.OK,
                        text="No se pudo crear el tema (el ID ya existe)",
                    )
                    info_dlg.run()
                    info_dlg.destroy()
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_clone_theme(tree, store):
        sel = tree.get_selection()
        model, iter_ = sel.get_selected()
        if iter_ is None:
            info_dlg = Gtk.MessageDialog(
                transient_for=app.window,
                modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Selecciona un tema para clonar",
            )
            info_dlg.run()
            info_dlg.destroy()
            return

        source_id = model.get_value(iter_, 1)
        source_name = model.get_value(iter_, 0)

        dialog = Gtk.Dialog(
            title=f"Clonar tema: {source_name}",
            transient_for=app.window,
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
                    info_dlg = Gtk.MessageDialog(
                        transient_for=app.window,
                        modal=True,
                        message_type=Gtk.MessageType.INFO,
                        buttons=Gtk.ButtonsType.OK,
                        text="El nombre es obligatorio",
                    )
                    info_dlg.run()
                    info_dlg.destroy()
                    return
                theme = ThemeService.clone_theme(
                    source_id=source_id,
                    new_name=name,
                    description=entry_desc.get_text().strip(),
                    author=entry_author.get_text().strip(),
                )
                if theme:
                    _refresh_theme_store(store)
                    app._update_status(f"Tema clonado: {name}")
                else:
                    info_dlg = Gtk.MessageDialog(
                        transient_for=app.window,
                        modal=True,
                        message_type=Gtk.MessageType.INFO,
                        buttons=Gtk.ButtonsType.OK,
                        text="No se pudo clonar el tema (el ID ya existe)",
                    )
                    info_dlg.run()
                    info_dlg.destroy()
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_view_theme_css(tree, store):
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
            transient_for=app.window,
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
                app._update_status(f"CSS guardado: {fname}")
                if app.project and app.project.theme_id == theme_id:
                    app.editor_view._update_preview()
                    app._styles_panel.update()
            d.destroy()

        editor_dialog.connect("response", on_editor_response)
        editor_dialog.show_all()

    def _on_rename_theme(tree, store):
        sel = tree.get_selection()
        model, iter_ = sel.get_selected()
        if iter_ is None:
            return
        type_label = model.get_value(iter_, 3)
        if type_label == "Integrado":
            info_dlg = Gtk.MessageDialog(
                transient_for=app.window,
                modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Los temas integrados no se pueden renombrar",
            )
            info_dlg.run()
            info_dlg.destroy()
            return

        theme_id = model.get_value(iter_, 1)
        current_name = model.get_value(iter_, 0)

        dialog = Gtk.Dialog(
            title="Renombrar tema",
            transient_for=app.window,
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
                    _refresh_theme_store(store)
                    app._update_status(f"Tema renombrado: {new_name}")
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def _on_delete_theme(tree, store, parent_dialog):
        sel = tree.get_selection()
        model, iter_ = sel.get_selected()
        if iter_ is None:
            return
        type_label = model.get_value(iter_, 3)
        if type_label == "Integrado":
            info_dlg = Gtk.MessageDialog(
                transient_for=app.window,
                modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Los temas integrados no se pueden eliminar",
            )
            info_dlg.run()
            info_dlg.destroy()
            return

        theme_id = model.get_value(iter_, 1)
        theme_name = model.get_value(iter_, 0)

        if theme_id == app.project.theme_id:
            info_dlg = Gtk.MessageDialog(
                transient_for=app.window,
                modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text=f"El tema '{theme_name}' esta en uso.\n"
                     "Cambia a otro tema antes de eliminarlo.",
            )
            info_dlg.run()
            info_dlg.destroy()
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
                _refresh_theme_store(store)
                app._update_status(f"Tema eliminado: {theme_name}")
            else:
                info_dlg = Gtk.MessageDialog(
                    transient_for=app.window,
                    modal=True,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    text="No se pudo eliminar el tema",
                )
                info_dlg.run()
                info_dlg.destroy()

    def _on_export_theme(tree, store):
        sel = tree.get_selection()
        model, iter_ = sel.get_selected()
        if iter_ is None:
            info_dlg = Gtk.MessageDialog(
                transient_for=app.window,
                modal=True,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Selecciona un tema primero",
            )
            info_dlg.run()
            info_dlg.destroy()
            return

        theme_id = model.get_value(iter_, 1)
        theme_name = model.get_value(iter_, 0)

        dialog = Gtk.FileChooserNative(
            title=f"Exportar tema: {theme_name}",
            transient_for=app.window,
            action=Gtk.FileChooserAction.SAVE,
            accept_label="_Exportar",
            cancel_label="_Cancelar",
        )
        dialog.set_current_name(f"{theme_id}.mdtotheme")

        f_filter = Gtk.FileFilter()
        f_filter.set_name("Archivos de tema (*.mdtotheme)")
        f_filter.add_pattern("*.mdtotheme")
        dialog.add_filter(f_filter)

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            output_path = dialog.get_filename()
            dialog.destroy()
            if not output_path.endswith(".mdtotheme"):
                output_path += ".mdtotheme"

            if ThemeService.export_theme(theme_id, output_path):
                app._update_status(f"Tema exportado: {output_path}")
                info_dlg = Gtk.MessageDialog(
                    transient_for=app.window,
                    modal=True,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    text=f"Tema '{theme_name}' exportado correctamente.",
                )
                info_dlg.run()
                info_dlg.destroy()
            else:
                error_dlg = Gtk.MessageDialog(
                    transient_for=app.window,
                    modal=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text=f"No se pudo exportar el tema '{theme_name}'",
                )
                error_dlg.run()
                error_dlg.destroy()
        else:
            dialog.destroy()

    def _on_import_theme(tree, store):
        dialog = Gtk.FileChooserNative(
            title="Importar tema",
            transient_for=app.window,
            action=Gtk.FileChooserAction.OPEN,
            accept_label="_Importar",
            cancel_label="_Cancelar",
        )

        f_filter = Gtk.FileFilter()
        f_filter.set_name("Archivos de tema (*.mdtotheme)")
        f_filter.add_pattern("*.mdtotheme")
        dialog.add_filter(f_filter)
        f_filter = Gtk.FileFilter()
        f_filter.set_name("Todos los archivos")
        f_filter.add_pattern("*")
        dialog.add_filter(f_filter)

        if dialog.run() == Gtk.ResponseType.ACCEPT:
            file_path = dialog.get_filename()
            dialog.destroy()

            imported = ThemeService.import_theme(file_path)
            if imported:
                _refresh_theme_store(store)
                app._update_status(f"Tema importado: {imported.name}")
                info_dlg = Gtk.MessageDialog(
                    transient_for=app.window,
                    modal=True,
                    message_type=Gtk.MessageType.INFO,
                    buttons=Gtk.ButtonsType.OK,
                    text=f"Tema '{imported.name}' importado correctamente.",
                )
                info_dlg.run()
                info_dlg.destroy()
            else:
                error_dlg = Gtk.MessageDialog(
                    transient_for=app.window,
                    modal=True,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.OK,
                    text="No se pudo importar el tema.\n"
                         "Asegurate de que el archivo es un .mdtotheme valido.",
                )
                error_dlg.run()
                error_dlg.destroy()
        else:
            dialog.destroy()

    dialog = Gtk.Dialog(
        title="Gestor de temas",
        transient_for=app.window,
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
        is_active = "Si" if theme.id == app.project.theme_id else ""
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
    btn_activate.connect("clicked", lambda b: _on_activate_theme(tree, store, dialog))
    btn_box.pack_start(btn_activate, False, False, 0)

    btn_create = Gtk.Button(label="Crear tema en blanco")
    btn_create.connect("clicked", lambda b: _on_create_blank_theme(tree, store))
    btn_box.pack_start(btn_create, False, False, 0)

    btn_clone = Gtk.Button(label="Clonar tema")
    btn_clone.connect("clicked", lambda b: _on_clone_theme(tree, store))
    btn_box.pack_start(btn_clone, False, False, 0)

    btn_view_css = Gtk.Button(label="Visualizar CSS")
    btn_view_css.connect("clicked", lambda b: _on_view_theme_css(tree, store))
    btn_box.pack_start(btn_view_css, False, False, 0)

    btn_rename = Gtk.Button(label="Renombrar")
    btn_rename.connect("clicked", lambda b: _on_rename_theme(tree, store))
    btn_box.pack_start(btn_rename, False, False, 0)

    btn_delete = Gtk.Button(label="Eliminar")
    btn_delete.connect("clicked", lambda b: _on_delete_theme(tree, store, dialog))
    btn_box.pack_start(btn_delete, False, False, 0)

    btn_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL), False, False, 0)

    btn_export = Gtk.Button(label="Exportar")
    btn_export.connect("clicked", lambda b: _on_export_theme(tree, store))
    btn_box.pack_start(btn_export, False, False, 0)

    btn_import = Gtk.Button(label="Importar")
    btn_import.connect("clicked", lambda b: _on_import_theme(tree, store))
    btn_box.pack_start(btn_import, False, False, 0)

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

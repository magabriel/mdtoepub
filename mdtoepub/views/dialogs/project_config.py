from ...utils.dialogs import show_error, show_info, confirm
import os
import shutil
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango, GdkPixbuf

from ...services.file_service import FileService, slugify
from ...services.yaml_service import YamlService
from ...services.theme_service import ThemeService
from ...services.spell_service import SpellCheckService
from ...services.image_service import ImageService
from ...models.component import ComponentType, COMPONENT_TYPE_LABELS
from ...services.labels_service import DEFAULT_LABELS

from ...i18n import _


def _show_info(parent, msg):
    d = Gtk.MessageDialog(
        parent=parent, modal=True,
        type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK,
        text=msg,
    )
    d.run()
    d.destroy()


def _show_error(parent, msg):
    d = Gtk.MessageDialog(
        parent=parent, modal=True,
        type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK,
        text=msg,
    )
    d.run()
    d.destroy()


def _confirm(parent, msg):
    d = Gtk.MessageDialog(
        parent=parent, modal=True,
        type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.YES_NO,
        text=msg,
    )
    response = d.run()
    d.destroy()
    return response == Gtk.ResponseType.YES


def _import_image(app, parent_window, on_imported=None):
    parent = parent_window or app.window

    dialog = Gtk.FileChooserDialog(
        title=_("Select image"),
        transient_for=parent,
        action=Gtk.FileChooserAction.OPEN,
    )
    dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
    dialog.add_button(_("Import"), Gtk.ResponseType.ACCEPT)
    dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

    img_filter = Gtk.FileFilter()
    img_filter.set_name(_("Images (JPEG, PNG, GIF)"))
    for ext in ImageService.get_supported_formats():
        img_filter.add_pattern(f"*{ext}")
        img_filter.add_pattern(f"*{ext.upper()}")
    dialog.add_filter(img_filter)

    dialog.show_all()
    dialog.present()
    response = dialog.run()

    if response == Gtk.ResponseType.ACCEPT:
        src_path = dialog.get_filename()
        dialog.destroy()
        if src_path:
            category_dialog = Gtk.Dialog(
                title=_("Image type"),
                transient_for=parent,
                modal=True,
            )
            category_dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
            category_dialog.add_button(_("Import"), Gtk.ResponseType.ACCEPT)

            cat_content = category_dialog.get_content_area()
            cat_content.set_spacing(12)
            cat_content.set_margin_top(12)
            cat_content.set_margin_bottom(12)
            cat_content.set_margin_start(12)
            cat_content.set_margin_end(12)

            cat_label = Gtk.Label(label=_("Select the image type:"))
            cat_content.add(cat_label)

            combo_cat = Gtk.ComboBoxText()
            combo_cat.append_text(_("Illustration (figures, diagrams)"))
            combo_cat.append_text(_("Decorative (separators, ornaments)"))
            combo_cat.set_active(0)
            cat_content.add(combo_cat)

            category_dialog.show_all()
            cat_response = category_dialog.run()

            if cat_response == Gtk.ResponseType.ACCEPT:
                category = "illustrations" if combo_cat.get_active() == 0 else "decorative"
                images_dir = os.path.join(app.project.path, "images")
                result = ImageService.copy_to_project(src_path, images_dir, category)
                if result:
                    app._update_status(_("Image imported: {name}").format(name=os.path.basename(src_path)))
                    if on_imported:
                        on_imported()
                else:
                    _show_error(parent, _("Error importing image"))
            category_dialog.destroy()
    else:
        dialog.destroy()


def _build_image_manager_widget(app, parent_window):
    images_dir = Path(app.project.path) / "images"

    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    hbox.set_margin_top(12)
    hbox.set_margin_bottom(12)
    hbox.set_margin_start(12)
    hbox.set_margin_end(12)

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
    col_name = Gtk.TreeViewColumn(_("Name"), r_name, text=IMG_COL_NAME)
    col_name.set_resizable(True)
    col_name.set_expand(True)
    tree_view.append_column(col_name)

    r_cat = Gtk.CellRendererText()
    col_cat = Gtk.TreeViewColumn(_("Category"), r_cat, text=IMG_COL_CAT)
    col_cat.set_resizable(True)
    tree_view.append_column(col_cat)

    r_size = Gtk.CellRendererText()
    col_size = Gtk.TreeViewColumn(_("Size"), r_size, text=IMG_COL_SIZE)
    col_size.set_resizable(True)
    tree_view.append_column(col_size)

    def populate_store():
        store.clear()
        for cat_name, cat_label in [("illustrations", _("Illustration")), ("decorative", _("Decorative"))]:
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

    btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    left_box.pack_start(btn_box, False, False, 0)

    btn_import = Gtk.Button(label=_("Import"))
    btn_import.connect("clicked", lambda b: _import_image(app, parent_window=parent_window, on_imported=populate_store))
    btn_box.pack_start(btn_import, False, False, 0)

    btn_delete = Gtk.Button(label=_("Delete"))
    btn_box.pack_start(btn_delete, False, False, 0)

    btn_rename = Gtk.Button(label=_("Rename"))
    btn_box.pack_start(btn_rename, False, False, 0)

    btn_change_type = Gtk.Button(label=_("Change Type"))
    btn_box.pack_start(btn_change_type, False, False, 0)

    right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    right_box.set_size_request(280, -1)
    hbox.pack_start(right_box, False, False, 0)

    preview_img = Gtk.Image()
    preview_frame = Gtk.Frame(label=_("Preview"))
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

    def on_delete(_btn):
        sel = tree_view.get_selection()
        model, paths = sel.get_selected_rows()
        if not paths:
            _show_info(parent_window, _("Select one or more images"))
            return
        names = []
        for p in paths:
            iter_ = model.get_iter(p)
            names.append(model.get_value(iter_, IMG_COL_NAME))
        confirm_dlg = Gtk.MessageDialog(
            transient_for=parent_window, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Delete {n} images").format(n=len(names)),
        )
        confirm_dlg.format_secondary_text("\n".join(f"  - {n}" for n in names))
        if confirm_dlg.run() == Gtk.ResponseType.YES:
            confirm_dlg.destroy()
            for p in reversed(sorted(paths)):
                iter_ = model.get_iter(p)
                fpath = model.get_value(iter_, IMG_COL_PATH)
                ImageService.delete_image(fpath)
            populate_store()
            update_preview()
        else:
            confirm_dlg.destroy()

    btn_delete.connect("clicked", on_delete)

    def on_rename(_btn):
        sel = tree_view.get_selection()
        model, paths = sel.get_selected_rows()
        if len(paths) != 1:
            _show_info(parent_window, _("Select a single image to rename"))
            return
        iter_ = model.get_iter(paths[0])
        old_name = model.get_value(iter_, IMG_COL_NAME)
        fpath = model.get_value(iter_, IMG_COL_PATH)
        cat_label = model.get_value(iter_, IMG_COL_CAT)
        cat_name = "illustrations" if cat_label == _("Illustration") else "decorative"

        rename_dialog = Gtk.Dialog(
            title=_("Rename image"),
            transient_for=parent_window, modal=True,
        )
        rename_dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        rename_dialog.add_button(_("Rename"), Gtk.ResponseType.ACCEPT)

        r_content = rename_dialog.get_content_area()
        r_content.set_spacing(12)
        r_content.set_margin_top(12)
        r_content.set_margin_bottom(12)
        r_content.set_margin_start(12)
        r_content.set_margin_end(12)

        r_content.add(Gtk.Label(label=_("New name:")))
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

            src_suffix = Path(old_name).suffix.lower()
            new_suffix = Path(new_name).suffix.lower()
            if new_suffix != src_suffix:
                _show_error(parent_window, _("The extension must be the same"))
                return

            result = ImageService.rename_image(fpath, new_name)
            if result is None:
                _show_error(parent_window, _("Could not rename (does '{name}' already exist?)").format(name=new_name))
                return

            updated = FileService.rename_image_references(
                app.project.path, old_path, new_path, app.project
            )

            if app.current_component:
                content = FileService.load_component(app.project.path, app.current_component)
                if content:
                    buf = app.text_view.get_buffer()
                    buf.set_text(content)
                    app.editor_view._update_preview()

            populate_store()
            app._update_status(_("Image renamed to '{name}' ({n} component(s) updated)").format(name=new_name, n=updated))
        else:
            rename_dialog.destroy()

    btn_rename.connect("clicked", on_rename)

    def on_change_type(_btn):
        sel = tree_view.get_selection()
        model, paths = sel.get_selected_rows()
        if len(paths) != 1:
            _show_info(parent_window, _("Select a single image to change type"))
            return
        iter_ = model.get_iter(paths[0])
        name = model.get_value(iter_, IMG_COL_NAME)
        fpath = model.get_value(iter_, IMG_COL_PATH)
        current_cat_label = model.get_value(iter_, IMG_COL_CAT)
        current_cat = "illustrations" if current_cat_label == _("Illustration") else "decorative"
        new_cat = "decorative" if current_cat == "illustrations" else "illustrations"
        new_cat_label = _("Decorative") if new_cat == "decorative" else _("Illustration")

        new_dir = images_dir / new_cat
        new_dir.mkdir(parents=True, exist_ok=True)
        new_path = new_dir / name

        if new_path.exists():
            _show_error(parent_window, _("An image with that name already exists in '{category}'").format(category=new_cat_label))
            return

        try:
            shutil.move(str(fpath), str(new_path))
        except OSError:
            _show_error(parent_window, _("Could not move the image"))
            return

        old_rel = f"images/{current_cat}/{name}"
        new_rel = f"images/{new_cat}/{name}"
        updated = FileService.rename_image_references(
            app.project.path, old_rel, new_rel, app.project
        )

        if app.current_component:
            content = FileService.load_component(app.project.path, app.current_component)
            if content:
                buf = app.text_view.get_buffer()
                buf.set_text(content)
                app.editor_view._update_preview()

        populate_store()
        update_preview()
        app._update_status(_("Image moved to '{category}' ({n} component(s) updated)").format(category=new_cat_label, n=updated))

    btn_change_type.connect("clicked", on_change_type)

    return hbox


def show_project_config(app):
    if not app.project:
        _show_info(app.window, _("No project open"))
        return

    read_only = app._read_only

    dialog = Gtk.Dialog(
        title=_("Project Settings") + (" [READ ONLY]" if read_only else ""),
        transient_for=app.window,
        modal=True,
    )
    dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
    if not read_only:
        dialog.add_button(_("Save"), Gtk.ResponseType.ACCEPT)
    dialog.set_default_size(520, 420)

    content = dialog.get_content_area()
    content.set_spacing(12)
    content.set_margin_top(12)
    content.set_margin_bottom(12)
    content.set_margin_start(12)
    content.set_margin_end(12)

    if read_only:
        note_rw = Gtk.Label()
        note_rw.set_markup(f'<span foreground="#c00"><b>{_("This project is read-only. Changes cannot be saved.")}</b></span>')
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
    notebook.append_page(grid_book, Gtk.Label(label=_("Book")))

    row = 0

    label = Gtk.Label(label=_("Title") + " *:")
    label.set_xalign(1)
    grid_book.attach(label, 0, row, 1, 1)
    entry_title = Gtk.Entry()
    interactive_widgets.append(entry_title)
    entry_title.set_text(app.project.title)
    entry_title.set_hexpand(True)
    title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    title_box.pack_start(entry_title, True, True, 0)
    hint = Gtk.Label(label="{{title}}")
    hint.set_opacity(0.55)
    hint.set_tooltip_text(_("Use {{title}} in text to insert this value"))
    title_box.pack_start(hint, False, False, 0)
    grid_book.attach(title_box, 1, row, 1, 1)
    row += 1

    label = Gtk.Label(label=_("Subtitle") + " *:")
    label.set_xalign(1)
    grid_book.attach(label, 0, row, 1, 1)
    entry_subtitle = Gtk.Entry()
    interactive_widgets.append(entry_subtitle)
    entry_subtitle.set_text(app.project.subtitle)
    entry_subtitle.set_hexpand(True)
    entry_subtitle.set_placeholder_text(_("Book subtitle"))
    sub_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    sub_box.pack_start(entry_subtitle, True, True, 0)
    hint = Gtk.Label(label="{{subtitle}}")
    hint.set_opacity(0.55)
    hint.set_tooltip_text(_("Use {{subtitle}} in text to insert this value"))
    sub_box.pack_start(hint, False, False, 0)
    grid_book.attach(sub_box, 1, row, 1, 1)
    row += 1

    label = Gtk.Label(label=_("EPUB file:"))
    label.set_xalign(1)
    grid_book.attach(label, 0, row, 1, 1)
    entry_export = Gtk.Entry()
    interactive_widgets.append(entry_export)

    def _update_export_filename(*_a):
        current = entry_export.get_text().strip()
        old_slug = slugify(entry_title.get_text().strip())
        if current and current != old_slug:
            return
        entry_export.set_text(slugify(entry_title.get_text().strip()))

    entry_title.connect("changed", _update_export_filename)
    if app.project.export_filename:
        entry_export.set_text(app.project.export_filename)
    else:
        entry_export.set_text(slugify(app.project.title or app.project.name))
    entry_export.set_hexpand(True)
    entry_export.set_placeholder_text(".epub")
    grid_book.attach(entry_export, 1, row, 1, 1)
    row += 1

    label = Gtk.Label(label=_("Author") + " *:")
    label.set_xalign(1)
    grid_book.attach(label, 0, row, 1, 1)
    entry_author = Gtk.Entry()
    interactive_widgets.append(entry_author)
    entry_author.set_text(app.project.author)
    entry_author.set_hexpand(True)
    aut_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    aut_box.pack_start(entry_author, True, True, 0)
    hint = Gtk.Label(label="{{author}}")
    hint.set_opacity(0.55)
    hint.set_tooltip_text(_("Use {{author}} in text to insert this value"))
    aut_box.pack_start(hint, False, False, 0)
    grid_book.attach(aut_box, 1, row, 1, 1)
    row += 1

    label = Gtk.Label(label=_("Language:"))
    label.set_xalign(1)
    grid_book.attach(label, 0, row, 1, 1)
    entry_lang = Gtk.Entry()
    interactive_widgets.append(entry_lang)
    entry_lang.set_text(app.project.language)
    entry_lang.set_hexpand(True)
    entry_lang.set_placeholder_text("es")
    grid_book.attach(entry_lang, 1, row, 1, 1)
    row += 1

    label = Gtk.Label(label=_("EPUB version:"))
    label.set_xalign(1)
    grid_book.attach(label, 0, row, 1, 1)
    combo_epub = Gtk.ComboBoxText()
    interactive_widgets.append(combo_epub)
    combo_epub.append_text("epub2")
    combo_epub.append_text("epub3")
    if app.project.epub_version == "epub2":
        combo_epub.set_active(0)
    else:
        combo_epub.set_active(1)
    grid_book.attach(combo_epub, 1, row, 1, 1)
    row += 1

    label = Gtk.Label(label=_("Edition") + " *:")
    label.set_xalign(1)
    grid_book.attach(label, 0, row, 1, 1)
    entry_edicion = Gtk.Entry()
    interactive_widgets.append(entry_edicion)
    entry_edicion.set_text(app.project.edition)
    entry_edicion.set_hexpand(True)
    entry_edicion.set_placeholder_text(_("1st edition"))
    edi_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    edi_box.pack_start(entry_edicion, True, True, 0)
    hint = Gtk.Label(label="{{edition}}")
    hint.set_opacity(0.55)
    hint.set_tooltip_text(_("Use {{edition}} in text to insert this value"))
    edi_box.pack_start(hint, False, False, 0)
    grid_book.attach(edi_box, 1, row, 1, 1)
    row += 1

    label = Gtk.Label(label=_("Publication date") + " *:")
    label.set_xalign(1)
    grid_book.attach(label, 0, row, 1, 1)
    entry_fecha = Gtk.Entry()
    interactive_widgets.append(entry_fecha)
    entry_fecha.set_text(app.project.publication_date)
    entry_fecha.set_hexpand(True)
    entry_fecha.set_placeholder_text("2025-01-15")
    fec_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    fec_box.pack_start(entry_fecha, True, True, 0)
    hint = Gtk.Label(label="{{publication_date}}  {{publication_date:year}}")
    hint.set_opacity(0.55)
    hint.set_tooltip_text(_("Use {{publication_date}} or {{publication_date:year}} (year only) in text"))
    fec_box.pack_start(hint, False, False, 0)
    grid_book.attach(fec_box, 1, row, 1, 1)
    row += 1

    label = Gtk.Label(label="ISBN *:")
    label.set_xalign(1)
    grid_book.attach(label, 0, row, 1, 1)
    entry_isbn = Gtk.Entry()
    interactive_widgets.append(entry_isbn)
    entry_isbn.set_text(app.project.isbn)
    entry_isbn.set_hexpand(True)
    entry_isbn.set_placeholder_text("978-84-999-9999-9")
    isbn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    isbn_box.pack_start(entry_isbn, True, True, 0)
    hint = Gtk.Label(label="{{isbn}}")
    hint.set_opacity(0.55)
    hint.set_tooltip_text(_("Use {{isbn}} in text to insert this value"))
    isbn_box.pack_start(hint, False, False, 0)
    grid_book.attach(isbn_box, 1, row, 1, 1)
    row += 1

    label = Gtk.Label(label=_("Publisher") + " *:")
    label.set_xalign(1)
    grid_book.attach(label, 0, row, 1, 1)
    entry_editorial = Gtk.Entry()
    interactive_widgets.append(entry_editorial)
    entry_editorial.set_text(app.project.publisher)
    entry_editorial.set_hexpand(True)
    entry_editorial.set_placeholder_text("Ediciones Aprender")
    pub_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    pub_box.pack_start(entry_editorial, True, True, 0)
    hint = Gtk.Label(label="{{publisher}}")
    hint.set_opacity(0.55)
    hint.set_tooltip_text(_("Use {{publisher}} in text to insert this value"))
    pub_box.pack_start(hint, False, False, 0)
    grid_book.attach(pub_box, 1, row, 1, 1)
    row += 1

    note = Gtk.Label()
    note.set_markup(
        '<span size="small" foreground="#555">'
        + _('* Marked fields can be inserted in text using <tt>{{name}}</tt>. Example: <tt>{{title}}</tt>, <tt>{{isbn}}</tt>, <tt>{{publisher}}</tt>.')
        + '</span>'
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
    notebook.append_page(grid_app, Gtk.Label(label=_("Appearance")))

    row = 0

    label = Gtk.Label(label=_("Auto component title:"))
    label.set_xalign(1)
    grid_app.attach(label, 0, row, 1, 1)
    combo_auto_title = Gtk.ComboBoxText()
    interactive_widgets.append(combo_auto_title)
    combo_auto_title.append_text(_("No"))
    combo_auto_title.append_text(_("Chapter <n>"))
    combo_auto_title.append_text("<n>")
    combo_auto_title.append_text(_("Chapter <n> + title"))
    combo_auto_title.append_text("<n> + " + _("title"))
    auto_title_values = ["none", "chapter_number", "number", "chapter_number_with_title", "number_with_title"]
    auto_title_index = 0
    for i, v in enumerate(auto_title_values):
        if v == app.project.auto_chapter_title:
            auto_title_index = i
            break
    combo_auto_title.set_active(auto_title_index)
    grid_app.attach(combo_auto_title, 1, row, 1, 1)
    row += 1

    label_part = Gtk.Label(label=_("Auto part title:"))
    label_part.set_xalign(1)
    grid_app.attach(label_part, 0, row, 1, 1)
    combo_auto_part = Gtk.ComboBoxText()
    interactive_widgets.append(combo_auto_part)
    combo_auto_part.append_text(_("No"))
    combo_auto_part.append_text(_("Part <n>"))
    combo_auto_part.append_text("<n>")
    combo_auto_part.append_text(_("Part <n> + title"))
    combo_auto_part.append_text("<n> + " + _("title"))
    auto_part_values = ["none", "part_number", "number", "part_number_with_title", "number_with_title"]
    auto_part_index = 0
    for i, v in enumerate(auto_part_values):
        if v == app.project.auto_part_title:
            auto_part_index = i
            break
    combo_auto_part.set_active(auto_part_index)
    grid_app.attach(combo_auto_part, 1, row, 1, 1)
    row += 1

    label = Gtk.Label(label=_("Theme:"))
    label.set_xalign(1)
    grid_app.attach(label, 0, row, 1, 1)

    themes_list = ThemeService.list_themes()
    available_themes = [(t.id, t.name) for t in themes_list]

    combo_theme = Gtk.ComboBoxText()
    interactive_widgets.append(combo_theme)
    theme_index = 0
    for i, (tid, tname) in enumerate(available_themes):
        combo_theme.append_text(tname)
        if tid == app.project.theme_id:
            theme_index = i
    combo_theme.set_active(theme_index)
    grid_app.attach(combo_theme, 1, row, 1, 1)
    row += 1

    sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
    grid_app.attach(sep, 0, row, 2, 1)
    row += 1

    label = Gtk.Label(label=_("Drop cap:"))
    label.set_xalign(1)
    label.set_valign(Gtk.Align.START)
    grid_app.attach(label, 0, row, 1, 1)

    right_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    grid_app.attach(right_vbox, 1, row, 1, 1)
    row += 1

    check_drop_cap = Gtk.CheckButton(label=_("Enable"))
    interactive_widgets.append(check_drop_cap)
    check_drop_cap.set_active(app.project.drop_cap_enabled)
    right_vbox.pack_start(check_drop_cap, False, False, 0)

    label_cap_types = Gtk.Label(label=_("Types with drop cap:"), xalign=0)
    right_vbox.pack_start(label_cap_types, False, False, 0)

    type_list = Gtk.ListBox()
    type_list.set_selection_mode(Gtk.SelectionMode.NONE)
    type_list.set_vexpand(True)
    type_list.set_hexpand(True)

    skip_types = {ComponentType.PART, ComponentType.TOC, ComponentType.COVER,
                  ComponentType.TITLE, ComponentType.LICENSE, ComponentType.FOOTNOTES}
    drop_cap_checkbuttons = {}
    for ct in ComponentType:
        if ct in skip_types:
            continue
        label_text = app.project_manager.resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS.get(ct, ct.value))
        cb = Gtk.CheckButton(label=label_text)
        cb.set_active(ct.value in app.project.drop_cap_types)
        drop_cap_checkbuttons[ct.value] = cb
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
    label_fig = Gtk.Label(label=_("Figure numbering:"))
    label_fig.set_xalign(1)
    label_fig.set_valign(Gtk.Align.START)
    grid_app.attach(label_fig, 0, row, 1, 1)

    fig_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    grid_app.attach(fig_vbox, 1, row, 1, 1)
    row += 1

    check_figure_numbering = Gtk.CheckButton(label=_("Number figures automatically"))
    interactive_widgets.append(check_figure_numbering)
    check_figure_numbering.set_active(app.project.figure_numbering)
    fig_vbox.pack_start(check_figure_numbering, False, False, 0)

    fig_style_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    fig_style_label = Gtk.Label(label=_("Style:"))
    fig_style_box.pack_start(fig_style_label, False, False, 0)
    combo_fig_style = Gtk.ComboBoxText()
    interactive_widgets.append(combo_fig_style)
    combo_fig_style.append_text(_("Arabic numbers"))
    combo_fig_style.append_text(_("Roman numerals"))
    fig_style_values = ["arabic", "roman"]
    fig_style_index = 0
    for i, v in enumerate(fig_style_values):
        if v == app.project.figure_numbering_style:
            fig_style_index = i
            break
    combo_fig_style.set_active(fig_style_index)
    fig_style_box.pack_start(combo_fig_style, False, False, 0)
    fig_vbox.pack_start(fig_style_box, False, False, 0)

    def _on_fig_numbering_toggle(cb):
        combo_fig_style.set_sensitive(cb.get_active())

    check_figure_numbering.connect("toggled", _on_fig_numbering_toggle)
    _on_fig_numbering_toggle(check_figure_numbering)

    sep3 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
    grid_app.attach(sep3, 0, row, 2, 1)
    row += 1

    # ── Table numbering ──
    label_tab = Gtk.Label(label=_("Table numbering:"))
    label_tab.set_xalign(1)
    label_tab.set_valign(Gtk.Align.START)
    grid_app.attach(label_tab, 0, row, 1, 1)

    tab_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    grid_app.attach(tab_vbox, 1, row, 1, 1)
    row += 1

    check_table_numbering = Gtk.CheckButton(label=_("Number tables automatically"))
    interactive_widgets.append(check_table_numbering)
    check_table_numbering.set_active(app.project.table_numbering)
    tab_vbox.pack_start(check_table_numbering, False, False, 0)

    tab_style_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    tab_style_label = Gtk.Label(label=_("Style:"))
    tab_style_box.pack_start(tab_style_label, False, False, 0)
    combo_tab_style = Gtk.ComboBoxText()
    interactive_widgets.append(combo_tab_style)
    combo_tab_style.append_text(_("Arabic numbers"))
    combo_tab_style.append_text(_("Roman numerals"))
    tab_style_values = ["arabic", "roman"]
    tab_style_index = 0
    for i, v in enumerate(tab_style_values):
        if v == app.project.table_numbering_style:
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
    label_lang = Gtk.Label(label=_("Spell checker:"))
    label_lang.set_xalign(1)
    grid_app.attach(label_lang, 0, row, 1, 1)

    combo_lang = Gtk.ComboBoxText()
    interactive_widgets.append(combo_lang)
    langs = app.spell_service.get_language_list()
    lang_index = 0
    for i, l in enumerate(langs):
        combo_lang.append_text(l)
        if l == app.project.spell_lang:
            lang_index = i
    combo_lang.set_active(lang_index)
    combo_lang.set_hexpand(True)
    grid_app.attach(combo_lang, 1, row, 1, 1)
    row += 1

    # ── Tab 3: Labels ──
    labels_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    labels_page.set_margin_top(12)
    labels_page.set_margin_bottom(12)
    labels_page.set_margin_start(12)
    labels_page.set_margin_end(12)
    notebook.append_page(labels_page, Gtk.Label(label=_("Labels")))

    __, config_file = app._get_config_path()
    global_cfg = YamlService.load(config_file) or {}
    global_labels = global_cfg.get("labels", {})
    label_keys = [k for k in DEFAULT_LABELS.get("es", {})]

    def _build_labels_page(lang_code):
        for child in labels_page.get_children():
            labels_page.remove(child)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top_row.pack_start(Gtk.Label(label=_("Language:"), xalign=0), False, False, 0)

        combo_label_lang = Gtk.ComboBoxText()
        for lang in sorted(set(list(DEFAULT_LABELS.keys()) + list(global_labels.keys()))):
            combo_label_lang.append_text(lang)
        top_row.pack_start(combo_label_lang, False, False, 0)

        btn_new_lang = Gtk.Button(label=_("New Language..."))
        interactive_widgets.append(btn_new_lang)
        top_row.pack_start(btn_new_lang, False, False, 0)

        btn_reset = Gtk.Button(label=_("Restore Defaults"))
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
                label=_("These labels replace component type names (e.g. \"Chapter\", \"Table of contents\") "
                        "in the tree and in the EPUB when the component has no title.")
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
                title=_("New Language"),
                transient_for=dialog,
                modal=True,
            )
            dlg.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
            dlg.add_button(_("Create"), Gtk.ResponseType.ACCEPT)
            c = dlg.get_content_area()
            c.set_spacing(8)
            c.set_margin_top(8)
            c.set_margin_bottom(8)
            c.set_margin_start(8)
            c.set_margin_end(8)

            c.pack_start(Gtk.Label(label=_("Language code (e.g. fr, de, it):")), False, False, 0)
            code_entry = Gtk.Entry()
            c.pack_start(code_entry, False, False, 0)

            c.pack_start(Gtk.Label(label=_("Copy labels from:")), False, False, 0)
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

    _build_labels_page(app.project.language)

    images_page = _build_image_manager_widget(app, dialog)
    if images_page:
        notebook.append_page(images_page, Gtk.Label(label=_("Images")))

    def on_config_response(d, response):
        if response == Gtk.ResponseType.ACCEPT:
            app.project.title = entry_title.get_text().strip()
            app.project.author = entry_author.get_text().strip()
            app.project.language = entry_lang.get_text().strip() or "es"
            epub_idx = combo_epub.get_active()
            app.project.epub_version = ["epub2", "epub3"][epub_idx]
            auto_idx = combo_auto_title.get_active()
            if 0 <= auto_idx < len(auto_title_values):
                app.project.auto_chapter_title = auto_title_values[auto_idx]
            auto_part_idx = combo_auto_part.get_active()
            if 0 <= auto_part_idx < len(auto_part_values):
                app.project.auto_part_title = auto_part_values[auto_part_idx]
            theme_idx = combo_theme.get_active()
            if theme_idx >= 0 and theme_idx < len(available_themes):
                app.project.theme_id = available_themes[theme_idx][0]
            app.project.drop_cap_enabled = check_drop_cap.get_active()
            app.project.drop_cap_types = [
                t for t, cb in drop_cap_checkbuttons.items() if cb.get_active()
            ] or ["chapter"]
            app.project.figure_numbering = check_figure_numbering.get_active()
            fig_style_idx = combo_fig_style.get_active()
            if 0 <= fig_style_idx < len(fig_style_values):
                app.project.figure_numbering_style = fig_style_values[fig_style_idx]
            app.project.table_numbering = check_table_numbering.get_active()
            tab_style_idx = combo_tab_style.get_active()
            if 0 <= tab_style_idx < len(tab_style_values):
                app.project.table_numbering_style = tab_style_values[tab_style_idx]
            app.project.export_filename = entry_export.get_text().strip()
            app.project.edition = entry_edicion.get_text().strip()
            app.project.publication_date = entry_fecha.get_text().strip()
            app.project.isbn = entry_isbn.get_text().strip()
            app.project.publisher = entry_editorial.get_text().strip()
            app.project.subtitle = entry_subtitle.get_text().strip()
            lang_idx = combo_lang.get_active()
            if lang_idx >= 0 and lang_idx < len(langs):
                app.project.spell_lang = langs[lang_idx]
            FileService.save_project(app.project)
            global_cfg["labels"] = global_labels
            YamlService.save(global_cfg, config_file)
            app.editor_view._update_spell_lang()
            app.project_tree_view._update_window_title()
            app.project_tree_view._refresh_project_tree()
            if app.current_component:
                app._styles_panel.update(app.current_component.type)
            elif app.current_part:
                app._styles_panel.update(app.current_part.type)
            app._update_status(_("Project settings saved"))
            app.editor_view._update_preview()
        d.destroy()

    dialog.connect("response", on_config_response)

    if read_only:
        for w in interactive_widgets:
            w.set_sensitive(False)
    dialog.show_all()

from ...utils.dialogs import show_error, show_info, confirm
import os
import shutil
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, GdkPixbuf

from ...services.file_service import FileService
from ...services.image_service import ImageService

from ...i18n import _


def _show_info(parent, message):
    dialog = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.OK,
        text=_("Information"),
    )
    dialog.format_secondary_text(message)
    dialog.connect("response", lambda d, r: d.destroy())
    dialog.show_all()


def _show_error(parent, message):
    dialog = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK,
        text=_("Error"),
    )
    dialog.format_secondary_text(message)
    dialog.connect("response", lambda d, r: d.destroy())
    dialog.show_all()


def _confirm(parent, message):
    dialog = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.YES_NO,
        text=_("Confirm"),
    )
    dialog.format_secondary_text(message)
    response = dialog.run()
    dialog.destroy()
    return response == Gtk.ResponseType.YES


def import_image(app, parent_window=None, on_imported=None):
    if not app.project:
        return

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
                    app.update_status(_("Image imported: {name}").format(name=os.path.basename(src_path)))
                    app.project_tree_view.refresh_project_tree()
                    app.editor_view.update_preview()
                    if on_imported:
                        on_imported()
                else:
                    _show_error(parent, _("Error importing image"))
            category_dialog.destroy()
    else:
        dialog.destroy()


def build_image_manager_widget(app, parent_dialog):
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
    btn_import.connect("clicked", lambda b: import_image(app, parent_window=parent_dialog, on_imported=populate_store))
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
            _show_info(parent_dialog, _("Select one or more images"))
            return
        names = []
        for p in paths:
            iter_ = model.get_iter(p)
            names.append(model.get_value(iter_, IMG_COL_NAME))
        if not _confirm(parent_dialog, "\n".join(f"  - {n}" for n in names)):
            return
        for p in reversed(sorted(paths)):
            iter_ = model.get_iter(p)
            fpath = model.get_value(iter_, IMG_COL_PATH)
            ImageService.delete_image(fpath)
        populate_store()
        update_preview()
        app.project_tree_view.refresh_project_tree()
        app.editor_view.update_preview()

    btn_delete.connect("clicked", on_delete)

    def on_rename(_btn):
        sel = tree_view.get_selection()
        model, paths = sel.get_selected_rows()
        if len(paths) != 1:
            _show_info(parent_dialog, _("Select a single image to rename"))
            return
        iter_ = model.get_iter(paths[0])
        old_name = model.get_value(iter_, IMG_COL_NAME)
        fpath = model.get_value(iter_, IMG_COL_PATH)
        cat_label = model.get_value(iter_, IMG_COL_CAT)
        cat_name = "illustrations" if cat_label == _("Illustration") else "decorative"

        rename_dialog = Gtk.Dialog(
            title=_("Rename image"),
            transient_for=parent_dialog, modal=True,
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
                _show_error(parent_dialog, _("The extension must be the same"))
                return

            result = ImageService.rename_image(fpath, new_name)
            if result is None:
                _show_error(parent_dialog, _("Could not rename (does '{name}' already exist?)").format(name=new_name))
                return

            updated = FileService.rename_image_references(
                app.project.path, old_path, new_path, app.project
            )

            if app.current_component:
                content = app.project_manager.load_component_content(app.current_component)
                if content:
                    buf = app.text_view.get_buffer()
                    buf.set_text(content)
                    app.editor_view.update_preview()

            populate_store()
            app.project_tree_view.refresh_project_tree()
            app.update_status(_("Image renamed to '{name}' ({n} component(s) updated)").format(name=new_name, n=updated))
        else:
            rename_dialog.destroy()

    btn_rename.connect("clicked", on_rename)

    def on_change_type(_btn):
        sel = tree_view.get_selection()
        model, paths = sel.get_selected_rows()
        if len(paths) != 1:
            _show_info(parent_dialog, _("Select a single image to change type"))
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
            _show_error(parent_dialog, _("An image with that name already exists in '{category}'").format(category=new_cat_label))
            return

        try:
            shutil.move(str(fpath), str(new_path))
        except OSError:
            _show_error(parent_dialog, _("Could not move the image"))
            return

        old_rel = f"images/{current_cat}/{name}"
        new_rel = f"images/{new_cat}/{name}"
        updated = FileService.rename_image_references(
            app.project.path, old_rel, new_rel, app.project
        )

        if app.current_component:
            content = app.project_manager.load_component_content(app.current_component)
            if content:
                buf = app.text_view.get_buffer()
                buf.set_text(content)
                app.editor_view.update_preview()

        populate_store()
        update_preview()
        app.project_tree_view.refresh_project_tree()
        app.update_status(_("Image moved to '{category}' ({n} component(s) updated)").format(category=new_cat_label, n=updated))

    btn_change_type.connect("clicked", on_change_type)

    return hbox

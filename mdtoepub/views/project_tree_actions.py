import uuid

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..models.component import Component, ComponentType, COMPONENT_TYPE_LABELS
from ..services.file_service import FileService
from ..services.labels_service import resolve_labels
from ..utils.dialogs import show_info, confirm

from ..i18n import _


class ProjectTreeActions:
    """Handles context menu actions for the project tree."""

    def __init__(self, app, project_tree):
        """Initialize with app and project tree references.

        Args:
            app: The application instance.
            project_tree: The ProjectTree instance.
        """
        self.app = app
        self.pt = project_tree

    def on_add_component(self, button, part=None):
        """Show dialog to add a new component.

        Args:
            button: Button that triggered the action.
            part: Optional part component to add to.
        """
        if not self.app.project:
            show_info(self.app.window, _("Create or open a project first"))
            return
        if self.app.read_only:
            show_info(self.app.window, _("Cannot modify a read-only project"))
            return

        dialog = Gtk.Dialog(
            title=_("Add Component"),
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Add"), Gtk.ResponseType.ACCEPT)

        content_area = dialog.get_content_area()
        content_area.set_spacing(12)
        content_area.set_margin_top(12)
        content_area.set_margin_bottom(12)
        content_area.set_margin_start(12)
        content_area.set_margin_end(12)

        type_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        type_label = Gtk.Label(label=_("Type:"))
        type_label.set_size_request(80, -1)
        type_box.pack_start(type_label, False, False, 0)

        combo_type = Gtk.ComboBoxText()
        for ct in ComponentType:
            combo_type.append_text(self.app.project_manager.resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct]))
        combo_type.set_active(0)
        type_box.pack_start(combo_type, True, True, 0)
        content_area.add(type_box)

        comp_title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        comp_title_label = Gtk.Label(label=_("Title:"))
        comp_title_label.set_size_request(80, -1)
        comp_title_box.pack_start(comp_title_label, False, False, 0)
        entry_title = Gtk.Entry()
        entry_title.set_hexpand(True)
        entry_title.set_placeholder_text(_("Component title"))
        comp_title_box.pack_start(entry_title, True, True, 0)
        content_area.add(comp_title_box)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                type_index = combo_type.get_active()
                if type_index < 0:
                    type_index = 0
                component_type = list(ComponentType)[type_index]
                title = entry_title.get_text().strip()

                component = Component(type=component_type, title=title)
                component.filename = FileService.generate_filename(
                    component_type.value, title
                )
                if part is not None:
                    component.part_id = part.id

                self.app.project.add_component(component)
                initial_content = f"# {title}\n\n" if title else ""
                FileService.save_component(self.app.project.path, component, initial_content)
                FileService.save_project(self.app.project)
                self.pt.refresh_project_tree()
                self.app.update_status(_("Component added: {name}").format(name=component.get_display_name(self.app.project_manager.resolve_labels())))
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def on_add_part(self, button):
        """Show dialog to add a new part."""
        if not self.app.project:
            show_info(self.app.window, _("Create or open a project first"))
            return
        if self.app.read_only:
            show_info(self.app.window, _("Cannot modify a read-only project"))
            return

        dialog = Gtk.Dialog(
            title=_("Add Part"),
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Add"), Gtk.ResponseType.ACCEPT)

        content_area = dialog.get_content_area()
        content_area.set_spacing(12)
        content_area.set_margin_top(12)
        content_area.set_margin_bottom(12)
        content_area.set_margin_start(12)
        content_area.set_margin_end(12)

        part_title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        part_title_label = Gtk.Label(label=_("Title:"))
        part_title_label.set_size_request(80, -1)
        part_title_box.pack_start(part_title_label, False, False, 0)
        entry_title = Gtk.Entry()
        entry_title.set_hexpand(True)
        entry_title.set_placeholder_text(_("Part I: Beginnings"))
        part_title_box.pack_start(entry_title, True, True, 0)
        content_area.add(part_title_box)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                title = entry_title.get_text().strip()
                if not title:
                    labels = resolve_labels(self.app.project.language)
                    title = labels.get("part", "Part")
                component_id = str(uuid.uuid4())
                part = Component(
                    id=component_id,
                    type=ComponentType.PART,
                    title=title,
                    filename=FileService.generate_filename("part", title),
                )
                self.app.project.add_component(part)
                initial_content = f"# {title}\n\n"
                FileService.save_component(self.app.project.path, part, initial_content)
                FileService.save_project(self.app.project)
                self.pt.refresh_project_tree()
                self.app.update_status(_("Part added: {title}").format(title=title))
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def on_rename_part(self, menu_item, part, iter_):
        """Show dialog to rename a part.

        Args:
            menu_item: Menu item that triggered the action.
            part: Part component to rename.
            iter_: Tree iter for the part.
        """
        dialog = Gtk.Dialog(
            title=_("Rename Part"),
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Rename"), Gtk.ResponseType.ACCEPT)

        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        entry = Gtk.Entry()
        entry.set_text(part.title)
        entry.set_hexpand(True)
        content.add(entry)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                new_title = entry.get_text().strip()
                if not new_title:
                    labels = resolve_labels(self.app.project.language)
                    new_title = labels.get("part", "Part")
                part.title = new_title
                self.pt.project_store.set_value(iter_, 0, part.get_display_name(self.app.project_manager.resolve_labels()))
                FileService.save_project(self.app.project)
                self.app.update_status(_("Part renamed: {title}").format(title=new_title))
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def on_delete_part(self, menu_item, part):
        """Confirm and delete a part.

        Args:
            menu_item: Menu item that triggered the action.
            part: Part component to delete.
        """
        dialog = Gtk.MessageDialog(
            transient_for=self.app.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Delete Part"),
        )
        dialog.format_secondary_text(_("The part \"{name}\" will be deleted and its components will be ungrouped.").format(name=part.get_display_name(self.app.project_manager.resolve_labels())))

        def on_response(d, response):
            if response == Gtk.ResponseType.YES:
                for c in self.app.project.components:
                    if c.part_id == part.id:
                        c.part_id = None
                self.app.project.remove_component(part.id)
                FileService.save_project(self.app.project)
                self.pt.refresh_project_tree()
                self.app.update_status(_("Part deleted: {name}").format(name=part.get_display_name(self.app.project_manager.resolve_labels())))
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def on_rename_component(self, menu_item, component, iter_):
        """Show dialog to rename a component.

        Args:
            menu_item: Menu item that triggered the action.
            component: Component to rename.
            iter_: Tree iter for the component.
        """
        dialog = Gtk.Dialog(
            title=_("Rename Component"),
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Rename"), Gtk.ResponseType.ACCEPT)

        content = dialog.get_content_area()
        content.set_spacing(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        entry = Gtk.Entry()
        entry.set_text(component.title)
        entry.set_hexpand(True)
        content.add(entry)

        def on_response(d, response):
            if response == Gtk.ResponseType.ACCEPT:
                new_title = entry.get_text().strip()
                if new_title:
                    component.title = new_title
                    self.pt.project_store.set_value(iter_, 0, component.get_display_name(self.app.project_manager.resolve_labels()))
                    FileService.save_project(self.app.project)
                    self.app.update_status(_("Component renamed: {title}").format(title=new_title))
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def on_duplicate_component(self, menu_item, component):
        """Duplicate a component.

        Args:
            menu_item: Menu item that triggered the action.
            component: Component to duplicate.
        """
        new_comp = Component(
            id=str(uuid.uuid4()),
            type=component.type,
            title=component.title,
            filename=FileService.generate_filename(component.type.value, component.title),
            order=component.order + 1,
            part_id=component.part_id,
            frontmatter=component.frontmatter.copy(),
            custom_css=component.custom_css,
        )
        for c in self.app.project.components:
            if c.order >= new_comp.order:
                c.order += 1

        content = FileService.load_component(self.app.project.path, component)
        self.app.project.add_component(new_comp)
        FileService.save_component(self.app.project.path, new_comp, content or "")
        FileService.save_project(self.app.project)
        self.pt.refresh_project_tree()
        self.app.update_status(_("Component duplicated: {name}").format(name=new_comp.get_display_name(self.app.project_manager.resolve_labels())))

    def on_move_to_part(self, menu_item, component, part):
        """Move a component to a part.

        Args:
            menu_item: Menu item that triggered the action.
            component: Component to move.
            part: Target part.
        """
        if component.part_id == part.id:
            return
        component.part_id = part.id
        FileService.save_project(self.app.project)
        self.pt.refresh_project_tree()
        self.app.update_status(_("{name} moved to {part}").format(name=component.get_display_name(self.app.project_manager.resolve_labels()), part=part.get_display_name(self.app.project_manager.resolve_labels())))

    def on_detach_from_part(self, menu_item, component):
        """Detach a component from its part.

        Args:
            menu_item: Menu item that triggered the action.
            component: Component to detach.
        """
        if not component.part_id:
            return
        if not confirm(self.app.window, _("Detach '{name}' from its part?").format(name=component.get_display_name(self.app.project_manager.resolve_labels()))):
            return
        component.part_id = None
        FileService.save_project(self.app.project)
        self.pt.refresh_project_tree()
        self.app.update_status(_("{name} detached from part").format(name=component.get_display_name(self.app.project_manager.resolve_labels())))

    def on_delete_component(self, menu_item, component):
        """Confirm and delete a component.

        Args:
            menu_item: Menu item that triggered the action.
            component: Component to delete.
        """
        dialog = Gtk.MessageDialog(
            transient_for=self.app.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Delete Component"),
        )
        dialog.format_secondary_text(_("The component \"{name}\" will be deleted.").format(name=component.get_display_name(self.app.project_manager.resolve_labels())))

        def on_response(d, response):
            if response == Gtk.ResponseType.YES:
                if self.app.current_component and self.app.current_component.id == component.id:
                    self.app.text_view.get_buffer().set_text("")
                    self.app.webview.load_html(self.app.default_html, self.app.editor_view.get_base_uri())
                    self.app.current_component = None
                self.app.project.remove_component(component.id)
                FileService.save_project(self.app.project)
                self.pt.refresh_project_tree()
                self.app.update_status(_("Component deleted: {name}").format(name=component.get_display_name(self.app.project_manager.resolve_labels())))
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def on_delete_multiple_components(self, menu_item, components):
        """Confirm and delete multiple components.

        Args:
            menu_item: Menu item that triggered the action.
            components: List of components to delete.
        """
        names = "\n".join(f"  - {c.get_display_name(self.app.project_manager.resolve_labels())}" for c in components)
        dialog = Gtk.MessageDialog(
            transient_for=self.app.window,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_("Delete {n} components").format(n=len(components)),
        )
        dialog.format_secondary_text(_("The following components will be deleted:\n{names}").format(names=names))

        def on_response(d, response):
            if response == Gtk.ResponseType.YES:
                ids = {c.id for c in components}
                if self.app.current_component and self.app.current_component.id in ids:
                    self.app.text_view.get_buffer().set_text("")
                    self.app.webview.load_html(self.app.default_html, self.app.editor_view.get_base_uri())
                    self.app.current_component = None
                for comp in components:
                    self.app.project.remove_component(comp.id)
                FileService.save_project(self.app.project)
                self.pt.refresh_project_tree()
                self.app.update_status(_("Deleted {n} components").format(n=len(components)))
            d.destroy()

        dialog.connect("response", on_response)
        dialog.show_all()

    def on_change_component_type(self, menu_item, component, new_type):
        """Change a component's type.

        Args:
            menu_item: Menu item that triggered the action.
            component: Component to change.
            new_type: New ComponentType.
        """
        component.type = new_type
        if not component.title:
            component.title = ""
        FileService.save_project(self.app.project)
        self.pt.refresh_project_tree()
        self.app.update_status(_("Type changed to: {type}").format(type=self.app.project_manager.resolve_labels().get(new_type.value, COMPONENT_TYPE_LABELS[new_type])))
        self.app.editor_view.update_preview()

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..i18n import _


def show_error(parent, message):
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


def show_info(parent, message):
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


def confirm(parent, message) -> bool:
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

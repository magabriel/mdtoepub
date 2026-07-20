import re

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango

from ..services.file_service import FileService

from ..i18n import _


class SpellCheckHandler:
    """Handles spell checking, highlighting, and popup suggestions in the editor."""

    def __init__(self, app):
        """Initialize with the application instance.

        Args:
            app: The application instance.
        """
        self.app = app
        self._spell_timer_id = 0
        self._misspelled_words = []
        self._session_ignored_words = set()
        self._spell_tag = None

    def setup(self, text_view):
        """Set up spell check on the given text view.

        Creates the spell tag and connects buffer change signal.

        Args:
            text_view: The GtkSource.View to attach spell checking to.
        """
        buf = text_view.get_buffer()
        self._spell_tag = buf.create_tag("misspelled",
                                         underline=Pango.Underline.ERROR)

        def _on_buffer_changed(*_a):
            if self._spell_timer_id:
                GLib.source_remove(self._spell_timer_id)
            self._spell_timer_id = GLib.timeout_add(600, self.run_spell_check)

        buf.connect("changed", _on_buffer_changed)
        text_view.connect("populate-popup", self.on_spell_popup)

    def update_spell_lang(self):
        """Update the spell check language from the project settings and re-check."""
        if self.app.project:
            self.app.spell_service.default_lang = self.app.project.spell_lang
        self.run_spell_check()

    def run_spell_check(self):
        """Run spell check on the current editor content.

        Highlights misspelled words in the text buffer.

        Returns:
            False (to stop GLib timeout repetition).
        """
        self._spell_timer_id = 0
        buf = self.app.text_view.get_buffer()
        if not self.app.project or not self.app.project.path:
            return False

        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
        if not text:
            return False

        start = buf.get_start_iter()
        end = buf.get_end_iter()
        buf.remove_tag(self._spell_tag, start, end)

        project_words = set(self.app.project.spell_words) if self.app.project else set()
        all_ignored = project_words | self._session_ignored_words
        self._misspelled_words = self.app.spell_service.check_text(text, all_ignored)

        for w_start, w_end, word, lang in self._misspelled_words:
            try:
                it1 = buf.get_iter_at_offset(w_start)
                it2 = buf.get_iter_at_offset(w_end)
                buf.apply_tag(self._spell_tag, it1, it2)
            except Exception:
                pass

        return False

    def on_spell_popup(self, textview, popup):
        """Add spell check suggestions to the editor context menu.

        Args:
            textview: The text view that owns the popup.
            popup: The popup menu to add items to.
        """
        buf = textview.get_buffer()
        cursor = buf.get_iter_at_mark(buf.get_insert())
        offset = cursor.get_offset()

        for w_start, w_end, word, lang in self._misspelled_words:
            if w_start <= offset <= w_end:
                suggestions = self.app.spell_service.get_suggestions(word, lang)
                if suggestions:
                    sep = Gtk.SeparatorMenuItem()
                    sep.show()
                    popup.append(sep)

                    item = Gtk.MenuItem(label=_("Spelling Suggestions"))
                    item.set_sensitive(False)
                    item.show()
                    popup.append(item)

                    for sug in suggestions[:10]:
                        def _replace(menu_item, s=sug, ws=w_start, we=w_end):
                            it1 = buf.get_iter_at_offset(ws)
                            it2 = buf.get_iter_at_offset(we)
                            buf.delete(it1, it2)
                            it = buf.get_iter_at_offset(ws)
                            buf.insert(it, s)
                        sug_item = Gtk.MenuItem(label=sug)
                        sug_item.connect("activate", _replace)
                        sug_item.show()
                        popup.append(sug_item)

                sep2 = Gtk.SeparatorMenuItem()
                sep2.show()
                popup.append(sep2)

                def _ignore_word(*_a, w=word, ws=w_start, we=w_end):
                    self._session_ignored_words.add(w.lower())
                    it1 = buf.get_iter_at_offset(ws)
                    it2 = buf.get_iter_at_offset(we)
                    buf.remove_tag(self._spell_tag, it1, it2)
                    self.run_spell_check()

                item_ignore = Gtk.MenuItem(label=_("Ignore word"))
                item_ignore.connect("activate", _ignore_word)
                item_ignore.show()
                popup.append(item_ignore)

                def _add_book_word(*_a, w=word, ws=w_start, we=w_end):
                    if self.app.project:
                        self.app.project.spell_words.append(w.lower())
                        FileService.save_project(self.app.project)
                    it1 = buf.get_iter_at_offset(ws)
                    it2 = buf.get_iter_at_offset(we)
                    buf.remove_tag(self._spell_tag, it1, it2)
                    self.app.editor_view.update_preview()

                item_book = Gtk.MenuItem(label=_("Add to book dictionary"))
                item_book.connect("activate", _add_book_word)
                item_book.show()
                popup.append(item_book)

                def _add_global_word(*_a, w=word, ws=w_start, we=w_end):
                    self.app.spell_service.add_global_word(w)
                    if self.app.project:
                        self.app.project.spell_words.append(w.lower())
                    it1 = buf.get_iter_at_offset(ws)
                    it2 = buf.get_iter_at_offset(we)
                    buf.remove_tag(self._spell_tag, it1, it2)
                    self.app.editor_view.update_preview()

                item_global = Gtk.MenuItem(label=_("Add to global dictionary"))
                item_global.connect("activate", _add_global_word)
                item_global.show()
                popup.append(item_global)
                break

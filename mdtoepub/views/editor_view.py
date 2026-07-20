import os
import re
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk, GLib, GdkPixbuf, Pango, WebKit2, GtkSource

from ..models.component import ComponentType
from ..services.epub_service import EpubService
from ..services.file_service import FileService
from ..services.yaml_service import YamlService
from ..services.image_service import ImageService
from ..services.markdown_service import MarkdownService
from ..services.spell_service import SpellCheckService
from .spell_check_handler import SpellCheckHandler

from ..i18n import _


class EditorView:
    def __init__(self, app):
        self.app = app
        self._spell_handler = SpellCheckHandler(app)

    def build(self, right_box):
        lang_dir = os.path.join(os.path.dirname(__file__), "..", "lang-specs")
        if os.path.isdir(lang_dir):
            lm = GtkSource.LanguageManager.get_default()
            sp = list(lm.get_search_path())
            sp.insert(0, lang_dir)
            lm.set_search_path(sp)
        help_lang = GtkSource.LanguageManager.get_default().get_language("mdtoepub-help")

        editor_scrolled = Gtk.ScrolledWindow()
        editor_scrolled.set_vexpand(True)
        self.app.text_view = GtkSource.View.new_with_buffer(
            GtkSource.Buffer.new_with_language(
                GtkSource.LanguageManager.get_default().get_language("markdown")
            )
        )
        self.app.text_view.set_editable(True)
        self.app.text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.app.text_view.set_monospace(True)
        editor_scrolled.add(self.app.text_view)

        self.app.spell_service = SpellCheckService()
        self._spell_handler.setup(self.app.text_view)

        self.app.text_view.connect("populate-popup", self._on_editor_image_popup)

        self.app.webview = WebKit2.WebView()
        self.app.webview.set_vexpand(True)

        front_scrolled = Gtk.ScrolledWindow()
        front_scrolled.set_vexpand(True)
        front_buf = GtkSource.Buffer.new_with_language(help_lang)
        self.app.front_textview = GtkSource.View.new_with_buffer(front_buf)
        self.app.front_textview.set_editable(False)
        self.app.front_textview.set_cursor_visible(False)
        self.app.front_textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        front_scrolled.add(self.app.front_textview)

        syntax_scrolled = Gtk.ScrolledWindow()
        syntax_scrolled.set_vexpand(True)
        syntax_buf = GtkSource.Buffer.new_with_language(help_lang)
        self.app.syntax_textview = GtkSource.View.new_with_buffer(syntax_buf)
        self.app.syntax_textview.set_editable(False)
        self.app.syntax_textview.set_cursor_visible(False)
        self.app.syntax_textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.app.syntax_textview.set_monospace(True)
        syntax_scrolled.add(self.app.syntax_textview)
        self._init_syntax_help(syntax_buf)

        self.app.content_notebook = Gtk.Notebook()
        self.app.content_notebook.append_page(editor_scrolled, Gtk.Label(label=_("Editor")))
        self.app.content_notebook.append_page(self.app.webview, Gtk.Label(label=_("Preview")))

        help_notebook = Gtk.Notebook()
        help_notebook.append_page(front_scrolled, Gtk.Label(label=_("Metadata")))
        help_notebook.append_page(syntax_scrolled, Gtk.Label(label=_("Syntax")))

        self.app.main_stack = Gtk.Stack()
        self.app.main_stack.set_vexpand(True)
        self.app.main_stack.add_titled(self.app.content_notebook, "content", _("Content"))
        self.app.main_stack.add_titled(self.app.styles_scrolled, "styles", _("Styles"))
        self.app.main_stack.add_titled(help_notebook, "help", _("Help"))

        sidebar = Gtk.StackSidebar()
        sidebar.set_stack(self.app.main_stack)

        side_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        side_box.pack_start(sidebar, False, False, 0)
        side_box.pack_start(self.app.main_stack, True, True, 0)
        right_box.pack_start(side_box, True, True, 0)

        self.app.default_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body { font-family: Georgia, serif; margin: 2em; color: #333; line-height: 1.6; }
h1 { font-size: 1.8em; border-bottom: 2px solid #ccc; }
h2 { font-size: 1.4em; }
p { margin: 0.5em 0; }
pre { background: #f4f4f4; padding: 1em; border-radius: 4px; }
code { background: #f4f4f4; padding: 0.1em 0.3em; border-radius: 3px; }
img { max-width: 90%; display: block; margin: 1em auto; }
figure { margin: 1.5em 0; text-align: center; }
figcaption { font-style: italic; font-size: 0.9em; margin-top: 0.5em; color: #555; }
blockquote { border-left: 3px solid #ccc; margin: 1em 0; padding-left: 1em; color: #555; }
hr { border: none; border-top: 1px solid #ccc; }
</style></head><body>
<p style="color:#999;text-align:center;margin-top:4em;">Markdown content preview</p>
</body></html>"""
        self.app.webview.load_html(self.app.default_html, self.get_base_uri())

        self.app.text_view.get_buffer().connect("changed", self._on_text_changed)

    def _init_syntax_help(self, buf):
        lines = [
            _("Markdown Syntax"),
            "",
            "\u2014 " + _("Text") + " \u2014",
            "",
            "  *cursiva*                _cursiva_",
            "  **negrita**              __negrita__",
            "  ~~tachado~~              `codigo`",
            "  > cita                   > cita anidada",
            "",
            "\u2014 " + _("Headings") + " \u2014",
            "",
            "  # Titulo                 ## Seccion",
            "  ### Subseccion           #### Sub-sub",
            "",
            "\u2014 " + _("Links and Images") + " \u2014",
            "",
            "  [Texto](url)             [Texto](url \"Titulo\")",
            "  ![Alt](ruta/imagen.jpg)",
            "",
            "\u2014 " + _("Lists") + " \u2014",
            "",
            "  - item                   * item",
            "    - subitem",
            "  1. numerada              1) numerada",
            "",
            "\u2014 " + _("Separator") + " \u2014",
            "",
            "  ---                      ***",
            "",
            _("Active Extensions"),
            "",
            "\u2014 " + _("Tables") + " \u2014  (tables)",
            "",
            "  | Col A | Col B | Col C |",
            "  |-------|-------|-------|",
            "  | a     | b     | c     |",
            "",
            "  * " + _("Alignment with :") + "   |:---|:---:|---:|",
            "",
            "\u2014 " + _("Code Block") + " \u2014  (fenced_code + codehilite)",
            "",
            "  ```python",
            "  def hola():",
            "      print(\"Hola\")",
            "  ```",
            "",
            "  * " + _("Languages: python, js, html, css, bash, json, yaml..."),
            "  * " + _("Syntax highlighting with Pygments in exported EPUB."),
            "",
            "\u2014 " + _("Definition Lists") + " \u2014  (def_list)",
            "",
            "  Termino",
            "  : Definicion del termino.",
            "  : Parrafo adicional de la definicion.",
            "",
            "\u2014 " + _("CSS Attributes") + " \u2014  (attr_list)",
            "",
            "  {.clase}                 \u2192 <elemento class=\"clase\">",
            "  {.c1 .c2}                \u2192 " + _("multiple classes"),
            "  {#id-unico}              \u2192 " + _("anchor with id"),
            "",
            "  * " + _("Placed on the line after the element."),
            "  * " + _("Available classes depend on the active theme."),
            "",
            "\u2014 " + _("Footnotes") + " \u2014  (footnotes)",
            "",
            "  Texto con nota[^1] y otra nota[^2].",
            "",
            "  [^1]: Contenido de la primera nota.",
            "  [^2]: Contenido de la segunda nota.",
            "",
            "  * " + _("Auto-numbered per component."),
            "  * " + _("Collected at the end in the Footnotes component."),
            "",
            "\u2014 " + _("Table of Contents") + " \u2014  (toc)",
            "",
            "  [TOC]",
            "",
            "  * " + _("Generates a local index within the component itself."),
            "",
            "\u2014 " + _("Line Breaks") + " \u2014  (" + _("CommonMark standard") + ")",
            "",
            "  * " + _("A blank line between text blocks creates a new paragraph."),
            "  * " + _("A simple line break joins text in the same paragraph (soft break)."),
            "  * " + _("Two spaces at the end of a line + line break creates an explicit <br> (hard break)."),
            "  * " + _("Backslash at the end of a line + line break also creates a hard break."),
            "",
            _("Custom Syntax"),
            "",
            "\u2014 " + _("Tables with Title") + " \u2014",
            "",
            "  <!-- Table: Mi tabla de datos -->",
            "  | A | B |",
            "  |---|---|",
            "  | 1 | 2 |",
            "",
            "  * " + _("Appear in the List of Tables if numbering is enabled in Project Settings."),
            "  * " + _("Tables without a comment are not numbered or listed."),
            "",
            "\u2014 " + _("Numbered Figures") + " \u2014",
            "",
            "  ![Pie de figura](images/illustrations/foto.jpg)",
            "",
            "  * " + _("Images in images/illustrations/ are automatically numbered and appear in the List of Figures."),
            "",
            "\u2014 " + _("Decorative Images") + " \u2014",
            "",
            "  ![Alt](images/decorative/ornamento.jpg)",
            "",
            "  * " + _("Excluded from numbering and LOF."),
            "  * " + _("Still get <figure> with alt as caption."),
            "",
            "\u2014 " + _("Spell Checker Language") + " \u2014",
            "",
            "  {lang=en}This text is in English.{lang=es}",
            "",
            "  * " + _("Changes the spell checker language."),
            "  * " + _("Markers are removed from the EPUB."),
            "",
            "\u2014 " + _("Component Metadata") + " \u2014  (frontmatter)",
            "",
            "  ---",
            "  show_title: false",
            "  toc_deep: 2",
            "  ---",
            "",
            "  * " + _("In YAML, between --- at the beginning of the file."),
            "  * " + _("Common variables: show_title, toc_deep, toc_include, split_title."),
            "",
            "\u2014 " + _("Project Variables") + " \u2014  (" + _("interpolation") + ")",
            "",
            "  {{title}}       {{subtitle}}",
            "  {{author}}      {{publisher}}",
            "  {{isbn}}        {{edition}}",
            "  {{publication_date}}",
            "  {{publication_date:year}}",
            "",
            "  * " + _("Replaced by values from project settings (File \u2192 Settings)."),
            "  * " + _("{{publication_date:year}} extracts only the year (e.g.: 2025-01-15 \u2192 2025)."),
            "  * " + _("Undefined fields remain as {{key}}."),
        ]
        buf.set_text("\n".join(lines))

    def update_spell_lang(self):
        """Update the spell check language from project settings."""
        self._spell_handler.update_spell_lang()

    def _on_editor_image_popup(self, textview, popup):
        if not self.app.project:
            return

        images_dir = Path(self.app.project.path) / "images"
        has_images = False
        for cat in ("illustrations", "decorative"):
            cat_dir = images_dir / cat
            if cat_dir.exists():
                for f in cat_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in ImageService.get_supported_formats():
                        has_images = True
                        break
            if has_images:
                break

        if not has_images:
            return

        sep = Gtk.SeparatorMenuItem()
        sep.show()
        popup.append(sep)

        item = Gtk.MenuItem(label=_("Insert Image..."))
        item.connect("activate", self._on_insert_image_dialog)
        item.show()
        popup.append(item)

    def _on_insert_image_dialog(self, menu_item):
        if not self.app.project:
            return

        images_dir = Path(self.app.project.path) / "images"

        dialog = Gtk.Dialog(
            title=_("Insert Image"),
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("Insert"), Gtk.ResponseType.ACCEPT)
        dialog.set_default_size(600, 450)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        hbox.set_margin_top(12)
        hbox.set_margin_bottom(12)
        hbox.set_margin_start(12)
        hbox.set_margin_end(12)
        dialog.get_content_area().pack_start(hbox, True, True, 0)

        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        hbox.pack_start(left_box, True, True, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        left_box.pack_start(scrolled, True, True, 0)

        IMG_COL_NAME = 0
        IMG_COL_CAT = 1
        IMG_COL_PATH = 2

        store = Gtk.ListStore(str, str, str)
        tree_view = Gtk.TreeView(model=store)
        tree_view.set_headers_visible(True)

        r_name = Gtk.CellRendererText()
        col_name = Gtk.TreeViewColumn(_("Name"), r_name, text=IMG_COL_NAME)
        col_name.set_resizable(True)
        col_name.set_expand(True)
        tree_view.append_column(col_name)

        r_cat = Gtk.CellRendererText()
        col_cat = Gtk.TreeViewColumn(_("Category"), r_cat, text=IMG_COL_CAT)
        col_cat.set_resizable(True)
        tree_view.append_column(col_cat)

        for cat_name, cat_label in [("illustrations", _("Illustration")), ("decorative", _("Decorative"))]:
            cat_dir = images_dir / cat_name
            if cat_dir.exists():
                for f in sorted(cat_dir.iterdir()):
                    if not f.is_file() or f.suffix.lower() not in ImageService.get_supported_formats():
                        continue
                    store.append([f.name, cat_label, str(f)])

        scrolled.add(tree_view)

        right_box2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        right_box2.set_size_request(240, -1)
        hbox.pack_start(right_box2, False, False, 0)

        preview_img = Gtk.Image()
        preview_frame = Gtk.Frame(label=_("Preview"))
        preview_frame.set_size_request(220, 260)
        preview_frame.add(preview_img)
        right_box2.pack_start(preview_frame, True, True, 0)

        def update_preview():
            sel = tree_view.get_selection()
            model, iter_ = sel.get_selected()
            if iter_ is None:
                preview_img.clear()
                return
            fpath = model.get_value(iter_, IMG_COL_PATH)
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(fpath, 200, 240)
                preview_img.set_from_pixbuf(pixbuf)
            except Exception:
                preview_img.clear()

        tree_view.get_selection().connect("changed", lambda *a: update_preview())
        tree_view.connect("row-activated", lambda tv, path, col: dialog.response(Gtk.ResponseType.ACCEPT))

        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.ACCEPT:
            sel = tree_view.get_selection()
            model, iter_ = sel.get_selected()
            if iter_ is not None:
                name = model.get_value(iter_, IMG_COL_NAME)
                cat_label = model.get_value(iter_, IMG_COL_CAT)
                cat_name = "illustrations" if cat_label == _("Illustration") else "decorative"
                rel_path = f"images/{cat_name}/{name}"

                buf = self.app.text_view.get_buffer()
                sel_bounds = buf.get_selection_bounds()
                alt_text = ""
                if sel_bounds:
                    alt_text = buf.get_text(sel_bounds[0], sel_bounds[1], True)
                    buf.delete(sel_bounds[0], sel_bounds[1])
                cursor = buf.get_iter_at_mark(buf.get_insert())
                buf.insert(cursor, f"![{alt_text}]({rel_path})")

        dialog.destroy()

    def get_base_uri(self) -> str:
        if self.app.project and self.app.project.path:
            return f"file://{self.app.project.path}/"
        return "file:///"

    def _build_preview_html(self, html_content: str, component_type=None, component=None) -> str:
        css = self.app.styles_panel.load_theme_css(component_type)
        if self.app.project and self.app.project.custom_css:
            css += "\n" + self.app.project.custom_css
        if (self.app.project and component_type is not None
                and component_type.value in self.app.project.type_css_overrides):
            css += "\n" + self.app.project.type_css_overrides[component_type.value]
        if component and component.custom_css:
            css += "\n" + component.custom_css
        css += "\n" + MarkdownService.get_code_css()
        css += """
.auto-notice {
    margin-top: 2em;
    padding: 0.8em 1em;
    border: 1px solid #ccc;
    border-radius: 6px;
    background: #f5f5f5;
    font-style: italic;
    color: #666;
    font-size: 0.9em;
}
"""
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>{css}</style>
</head><body>
{html_content}
</body></html>"""

    def focus_editor(self):
        self.app.main_stack.set_visible_child(self.app.content_notebook)
        self.app.content_notebook.set_current_page(0)

    def focus_preview(self):
        self.app.main_stack.set_visible_child(self.app.content_notebook)
        self.app.content_notebook.set_current_page(1)

    def update_preview(self):
        if not self.app.webview:
            return

        text = self._get_editor_text()
        component = self.app.current_component
        if not text.strip():
            if (self.app.project and component
                    and component.type
                    in (ComponentType.FOOTNOTES, ComponentType.TOC,
                        ComponentType.LOF, ComponentType.LOT, ComponentType.PART)):
                text = '\u200b'
            else:
        self.app.webview.load_html(self.app.default_html, self.get_base_uri())
                return

        if text.strip():
            component_id = ""
            if component:
                component_type = component.type
                component_id = component.id
            elif self.app.current_part:
                component_type = ComponentType.CHAPTER
            else:
                component_type = ComponentType.CHAPTER

            editor_fm, md_text = YamlService.parse_frontmatter(text)
            if component:
                component.frontmatter = editor_fm

            variables = {}
            if self.app.project:
                for k in ("title", "subtitle", "author", "isbn", "publisher",
                          "edition", "publication_date", "language"):
                    v = getattr(self.app.project, k, None)
                    if v:
                        variables[k] = v

            if self.app.project and component:
                from ..services.epub_service import EpubService
                from ..services.header_builder import HeaderBuilder
                epub_svc = EpubService(self.app.project)
                __, config_file = self.app.get_config_path()
                global_config = YamlService.load(config_file)
                labels = epub_svc.resolve_labels(global_config)
                header_builder = HeaderBuilder(self.app.project, labels)

                if (component.type == ComponentType.COVER
                        and EpubService.is_cover_only_image(md_text)):
                    img_info = EpubService.extract_cover_image(md_text)
                    if img_info:
                        alt, src = img_info
                        preview_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body {{ margin:0; padding:0; height:100vh; display:flex; align-items:center; justify-content:center; }}
img {{ max-width:100%; max-height:100%; object-fit:contain; }}
</style>
</head><body>
<img src="{src}" alt="{alt}"/>
</body></html>"""
                        self.app.webview.load_html(preview_html, self.get_base_uri())
                        return
                chapter_number = None
                part_number = None
                if component.should_use_numbering():
                    ch_count = 0
                    ap_count = 0
                    for c in self.app.project.get_ordered_components():
                        if c.type == ComponentType.CHAPTER:
                            ch_count += 1
                        elif c.type == ComponentType.APPENDIX:
                            ap_count += 1
                        if c.id == component.id:
                            chapter_number = ch_count if component.type == ComponentType.CHAPTER else ap_count
                            break
                elif component.type == ComponentType.PART:
                    count = 0
                    for c in self.app.project.get_ordered_components():
                        if c.type == ComponentType.PART:
                            count += 1
                        if c.id == component.id:
                            part_number = count
                            break

                h1_match = re.search(r'^# (.+)$', md_text, re.MULTILINE)
                default_title = h1_match.group(1).strip() if h1_match else ""
                show_title = editor_fm.get("show_title", True)

                if component.type == ComponentType.PART:
                    num_part, title_part, _dp = header_builder.get_part_header(
                        component, part_number
                    )
                    replaces = self.app.project.auto_part_title in ("part_number", "number", "word_part")
                else:
                    num_part, title_part, _dp = header_builder.get_component_header(
                        component, chapter_number
                    )
                    mode = self.app.project.auto_appendix_title if component.type == ComponentType.APPENDIX else self.app.project.auto_chapter_title
                    replaces = mode in ("chapter_number", "number")
                if show_title:
                    if default_title and not title_part and not replaces:
                        title_part = default_title
                    if default_title and title_part and default_title != component.title:
                        title_part = default_title

                subtitle_part = ""
                if title_part:
                    subtitle_part, title_part = HeaderBuilder.split_title(
                        title_part, editor_fm
                    )

                header_html = header_builder.build_header_html(num_part, subtitle_part, title_part)
                if header_html:
                    if h1_match:
                        md_text = md_text[:h1_match.start()] + md_text[h1_match.end():]
                        md_text = md_text.strip()
                    md_text = header_html + md_text
                elif not show_title:
                    if h1_match:
                        md_text = md_text[:h1_match.start()] + md_text[h1_match.end():]
                        md_text = md_text.strip()
                elif not default_title:
                    display = component.title or labels.get(component.type.value, component.get_display_name())
                    md_text = f"# {display}\n\n{md_text}"

                html = self.app.md_service.render(md_text, component_type, component_id,
                                                  variables=variables,
                                                  labels=labels)

                if (self.app.project.drop_cap_enabled
                        and component_type.value in self.app.project.drop_cap_types):
                    html = epub_svc.apply_drop_cap(html)
            else:
                html = self.app.md_service.render(md_text, component_type, component_id,
                                                  variables=variables)

            if self.app.project and component:
                if component.type == ComponentType.FOOTNOTES:
                    html = html.replace(
                        '</section>',
                        '<div class="auto-notice">'
                        '<p>' + _('All footnotes from the book will appear here automatically.') + '</p>'
                        '</div>\n</section>',
                        1
                    )
                elif component.type == ComponentType.TOC:
                    html = html.replace(
                        '</section>',
                        '<div class="auto-notice">'
                        '<p>' + _('The table of contents will appear here automatically.') + '</p>'
                        '</div>\n</section>',
                        1
                    )
                elif component.type == ComponentType.LOF:
                    html = html.replace(
                        '</section>',
                        '<div class="auto-notice">'
                        '<p>' + _('The list of figures will appear here automatically.') + '</p>'
                        '</div>\n</section>',
                        1
                    )
                elif component.type == ComponentType.LOT:
                    html = html.replace(
                        '</section>',
                        '<div class="auto-notice">'
                        '<p>' + _('The list of tables will appear here automatically.') + '</p>'
                        '</div>\n</section>',
                        1
                    )

            full_html = self._build_preview_html(html, component_type, component)
            self.app.webview.load_html(full_html, self.get_base_uri())
        else:
            self.app.webview.load_html(self.app.default_html, self.get_base_uri())

    def get_editor_text(self) -> str:
        buffer = self.app.text_view.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        return buffer.get_text(start, end, True)

    def _on_text_changed(self, buffer):
        self._update_preview()

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


class EditorView:
    def __init__(self, app):
        self.app = app
        self._spell_timer_id = 0
        self._misspelled_words = []
        self._session_ignored_words = set()
        self._spell_tag = None

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
        self._spell_timer_id = 0
        self._misspelled_words = []
        self._session_ignored_words = set()

        buf = self.app.text_view.get_buffer()
        self._spell_tag = buf.create_tag("misspelled",
                                         underline=Pango.Underline.ERROR)

        def _on_buffer_changed(*_a):
            if self._spell_timer_id:
                GLib.source_remove(self._spell_timer_id)
            self._spell_timer_id = GLib.timeout_add(600, self._run_spell_check)

        buf.connect("changed", _on_buffer_changed)

        self.app.text_view.connect("populate-popup", self._on_spell_popup)
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
        self.app.content_notebook.append_page(editor_scrolled, Gtk.Label(label="Editor"))
        self.app.content_notebook.append_page(self.app.webview, Gtk.Label(label="Vista previa"))

        help_notebook = Gtk.Notebook()
        help_notebook.append_page(front_scrolled, Gtk.Label(label="Metadatos"))
        help_notebook.append_page(syntax_scrolled, Gtk.Label(label="Sintaxis"))

        self.app.main_stack = Gtk.Stack()
        self.app.main_stack.set_vexpand(True)
        self.app.main_stack.add_titled(self.app.content_notebook, "content", "Contenido")
        self.app.main_stack.add_titled(self.app._styles_scrolled, "styles", "Estilos")
        self.app.main_stack.add_titled(help_notebook, "help", "Ayuda")

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
<p style="color:#999;text-align:center;margin-top:4em;">Vista previa del contenido Markdown</p>
</body></html>"""
        self.app.webview.load_html(self.app.default_html, self._get_base_uri())

        self.app.text_view.get_buffer().connect("changed", self._on_text_changed)

    def _init_syntax_help(self, buf):
        lines = [
            "Sintaxis Markdown",
            "",
            "— Texto —",
            "",
            "  *cursiva*                _cursiva_",
            "  **negrita**              __negrita__",
            "  ~~tachado~~              `codigo`",
            "  > cita                   > cita anidada",
            "",
            "— Encabezados —",
            "",
            "  # Titulo                 ## Seccion",
            "  ### Subseccion           #### Sub-sub",
            "",
            "— Enlaces e imagenes —",
            "",
            "  [Texto](url)             [Texto](url \"Titulo\")",
            "  ![Alt](ruta/imagen.jpg)",
            "",
            "— Listas —",
            "",
            "  - item                   * item",
            "    - subitem",
            "  1. numerada              1) numerada",
            "",
            "— Separador —",
            "",
            "  ---                      ***",
            "",
            "Extensiones activas",
            "",
            "— Tablas —  (tables)",
            "",
            "  | Col A | Col B | Col C |",
            "  |-------|-------|-------|",
            "  | a     | b     | c     |",
            "",
            "  * Alineacion con :   |:---|:---:|---:|",
            "",
            "— Bloque de codigo —  (fenced_code + codehilite)",
            "",
            "  ```python",
            "  def hola():",
            "      print(\"Hola\")",
            "  ```",
            "",
            "  * Lenguajes: python, js, html, css, bash, json, yaml...",
            "  * Resaltado con Pygments en el EPUB exportado.",
            "",
            "— Listas de definicion —  (def_list)",
            "",
            "  Termino",
            "  : Definicion del termino.",
            "  : Parrafo adicional de la definicion.",
            "",
            "— Atributos CSS —  (attr_list)",
            "",
            "  {.clase}                 → <elemento class=\"clase\">",
            "  {.c1 .c2}                → varias clases",
            "  {#id-unico}              → ancla con id",
            "",
            "  * Se coloca en la linea siguiente al elemento.",
            "  * Clases disponibles segun el tema activo.",
            "",
            "— Notas al pie —  (footnotes)",
            "",
            "  Texto con nota[^1] y otra nota[^2].",
            "",
            "  [^1]: Contenido de la primera nota.",
            "  [^2]: Contenido de la segunda nota.",
            "",
            "  * Se numeran automaticamente por componente.",
            "  * Se recogen al final en el componente Notas al pie.",
            "",
            "— Tabla de contenidos —  (toc)",
            "",
            "  [TOC]",
            "",
            "  * Genera un indice local dentro del propio componente.",
            "",
            "— Saltos de linea —  (estandar CommonMark)",
            "",
            "  * Una linea en blanco entre bloques de texto",
            "    crea un nuevo parrafo.",
            "  * Un salto de linea simple une el texto en",
            "    el mismo parrafo (soft break).",
            "  * Dos espacios al final de una linea + salto",
            "    de linea crea un <br> explicito (hard break).",
            "  * Barra invertida al final de una linea +",
            "    salto de linea tambien crea un hard break.",
            "",
            "Sintaxis personalizada",
            "",
            "— Tablas con titulo —",
            "",
            "  <!-- Table: Mi tabla de datos -->",
            "  | A | B |",
            "  |---|---|",
            "  | 1 | 2 |",
            "",
            "  * Aparecen en la Lista de Tablas si se activa",
            "    la numeracion en Configuracion del proyecto.",
            "  * Tablas sin comentario no se numeran ni listan.",
            "",
            "— Figuras numerables —",
            "",
            "  ![Pie de figura](images/illustrations/foto.jpg)",
            "",
            "  * Las imagenes en images/illustrations/ se numeran",
            "    automaticamente y aparecen en la Lista de Figuras.",
            "",
            "— Imagenes decorativas —",
            "",
            "  ![Alt](images/decorative/ornamento.jpg)",
            "",
            "  * Quedan fuera de la numeracion y de la LOF.",
            "  * Aun asi obtienen <figure> con alt como caption.",
            "",
            "— Idioma del corrector —",
            "",
            "  {lang=en}This text is in English.{lang=es}",
            "",
            "  * Cambia el idioma del corrector ortografico.",
            "  * Los marcadores se eliminan del EPUB.",
            "",
            "— Metadatos del componente —  (frontmatter)",
            "",
            "  ---",
            "  show_title: false",
            "  toc_deep: 2",
            "  ---",
            "",
            "  * En YAML, entre --- al inicio del archivo.",
            "  * Variables comunes: show_title, toc_deep,",
            "    toc_include, split_title.",
            "",
            "— Variables del proyecto —  (interpolacion)",
            "",
            "  {{title}}       {{subtitle}}",
            "  {{author}}      {{publisher}}",
            "  {{isbn}}        {{edition}}",
            "  {{publication_date}}",
            "  {{publication_date:year}}",
            "",
            "  * Se sustituyen por los valores de la configuracion",
            "    del proyecto (Archivo → Configuracion).",
            "  * {{publication_date:year}} extrae solo el año",
            "    (ej: 2025-01-15 → 2025).",
            "  * Los campos no definidos quedan como {{clave}}.",
        ]
        buf.set_text("\n".join(lines))

    def _update_spell_lang(self):
        if self.app.project:
            self.app.spell_service.default_lang = self.app.project.spell_lang
        self._run_spell_check()

    def _run_spell_check(self):
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

    def _on_spell_popup(self, textview, popup):
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

                    item = Gtk.MenuItem(label="Sugerencias ortográficas")
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
                    self._run_spell_check()

                item_ignore = Gtk.MenuItem(label="Ignorar palabra")
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
                    self._update_preview()

                item_book = Gtk.MenuItem(label="Añadir al diccionario del libro")
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
                    self._update_preview()

                item_global = Gtk.MenuItem(label="Añadir al diccionario global")
                item_global.connect("activate", _add_global_word)
                item_global.show()
                popup.append(item_global)
                break

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

        item = Gtk.MenuItem(label="Insertar imagen...")
        item.connect("activate", self._on_insert_image_dialog)
        item.show()
        popup.append(item)

    def _on_insert_image_dialog(self, menu_item):
        if not self.app.project:
            return

        images_dir = Path(self.app.project.path) / "images"

        dialog = Gtk.Dialog(
            title="Insertar imagen",
            transient_for=self.app.window,
            modal=True,
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Insertar", Gtk.ResponseType.ACCEPT)
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
        col_name = Gtk.TreeViewColumn("Nombre", r_name, text=IMG_COL_NAME)
        col_name.set_resizable(True)
        col_name.set_expand(True)
        tree_view.append_column(col_name)

        r_cat = Gtk.CellRendererText()
        col_cat = Gtk.TreeViewColumn("Categoria", r_cat, text=IMG_COL_CAT)
        col_cat.set_resizable(True)
        tree_view.append_column(col_cat)

        for cat_name, cat_label in [("illustrations", "Ilustrativa"), ("decorative", "Decorativa")]:
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
        preview_frame = Gtk.Frame(label="Vista previa")
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
                cat_name = "illustrations" if cat_label == "Ilustrativa" else "decorative"
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

    def _get_base_uri(self) -> str:
        if self.app.project and self.app.project.path:
            return f"file://{self.app.project.path}/"
        return "file:///"

    def _build_preview_html(self, html_content: str, component_type=None, component=None) -> str:
        css = self.app._styles_panel._load_theme_css(component_type)
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

    def _focus_editor(self):
        self.app.main_stack.set_visible_child(self.app.content_notebook)
        self.app.content_notebook.set_current_page(0)

    def _focus_preview(self):
        self.app.main_stack.set_visible_child(self.app.content_notebook)
        self.app.content_notebook.set_current_page(1)

    def _update_preview(self):
        if not self.app.webview:
            return

        text = self._get_editor_text()
        component = self.app.current_component
        if not text.strip():
            if (self.app.project and component
                    and component.type
                    in (ComponentType.FOOTNOTES, ComponentType.TOC, ComponentType.LOF)):
                text = '\u200b'
            else:
                self.app.webview.load_html(self.app.default_html, self._get_base_uri())
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
                from ..services.epub_service import EpubService as _EpubService
                epub_svc = _EpubService(self.app.project)
                _, config_file = self.app._get_config_path()
                global_config = YamlService.load(config_file)
                epub_svc._resolve_labels(global_config)

                if (component.type == ComponentType.COVER
                        and _EpubService._is_cover_only_image(md_text)):
                    img_info = _EpubService._extract_cover_image(md_text)
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
                        self.app.webview.load_html(preview_html, self._get_base_uri())
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
                    num_part, title_part, _ = epub_svc._get_part_header(
                        component, part_number
                    )
                    replaces = self.app.project.auto_part_title in ("part_number", "number")
                else:
                    num_part, title_part, _ = epub_svc._get_component_header(
                        component, chapter_number
                    )
                    replaces = self.app.project.auto_chapter_title in ("chapter_number", "number")
                if show_title:
                    if default_title and not title_part and not replaces:
                        title_part = default_title
                    if default_title and title_part and default_title != component.title:
                        title_part = default_title

                subtitle_part = ""
                if title_part:
                    subtitle_part, title_part = _EpubService._split_title(
                        title_part, editor_fm
                    )

                header_html = epub_svc._build_header_html(num_part, subtitle_part, title_part)
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
                    display = component.title or epub_svc._labels.get(component.type.value, component.get_display_name())
                    md_text = f"# {display}\n\n{md_text}"

                html = self.app.md_service.render(md_text, component_type, component_id,
                                                  variables=variables,
                                                  labels=epub_svc._labels)

                if (self.app.project.drop_cap_enabled
                        and component_type.value in self.app.project.drop_cap_types):
                    html = epub_svc._apply_drop_cap(html)
            else:
                html = self.app.md_service.render(md_text, component_type, component_id,
                                                  variables=variables)

            if self.app.project and component:
                if component.type == ComponentType.FOOTNOTES:
                    html = html.replace(
                        '</section>',
                        '<div class="auto-notice">'
                        '<p>Aquí aparecerán automáticamente todas '
                        'las notas al pie del libro.</p>'
                        '</div>\n</section>',
                        1
                    )
                elif component.type == ComponentType.TOC:
                    html = html.replace(
                        '</section>',
                        '<div class="auto-notice">'
                        '<p>Aquí aparecerá automáticamente la '
                        'tabla de contenidos.</p>'
                        '</div>\n</section>',
                        1
                    )
                elif component.type == ComponentType.LOF:
                    html = html.replace(
                        '</section>',
                        '<div class="auto-notice">'
                        '<p>Aquí aparecerá automáticamente la '
                        'lista de figuras.</p>'
                        '</div>\n</section>',
                        1
                    )
                elif component.type == ComponentType.LOT:
                    html = html.replace(
                        '</section>',
                        '<div class="auto-notice">'
                        '<p>Aquí aparecerá automáticamente la '
                        'lista de tablas.</p>'
                        '</div>\n</section>',
                        1
                    )

            full_html = self._build_preview_html(html, component_type, component)
            self.app.webview.load_html(full_html, self._get_base_uri())
        else:
            self.app.webview.load_html(self.app.default_html, self._get_base_uri())

    def _get_editor_text(self) -> str:
        buffer = self.app.text_view.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        return buffer.get_text(start, end, True)

    def _on_text_changed(self, buffer):
        self._update_preview()

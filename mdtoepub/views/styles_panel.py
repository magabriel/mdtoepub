import os

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkSource", "4")
from gi.repository import Gtk, Pango, GtkSource

from ..models.component import ComponentType, COMPONENT_TYPE_LABELS
from ..services.file_service import FileService
from ..services.theme_service import ThemeService
from ..services.yaml_service import YamlService
from ..services.style_doc_service import StyleDocService

FRONTMATTER_DOCS = {
    "toc": [
        ("toc_include", "Lista de tipos de componente a incluir en el índice (ej: ['chapter', 'appendix'])"),
        ("toc_deep", "Profundidad maxima de encabezados en el índice (1-6, por defecto 2)"),
    ],
    "chapter": [
        ("show_title", "false para ocultar el titulo del capitulo"),
    ],
}

FRONTMATTER_COMMON = [
    ("show_title", "false para ocultar el titulo del componente (por defecto true)"),
    ("split_title", "false para desactivar la particion automatica del titulo en subtitulo + titulo al encontrar ' - ', ' -- ' o ' --- ' (por defecto true)"),
]


class StylesPanel:
    def __init__(self, app):
        self.app = app
        self._style_doc_svc = None
        self._styles_current_component = None
        self._styles_current_comp_type = None
        self._styles_scrolled = None
        self._theme_frame = None
        self._theme_frame_label = None
        self._theme_box = None
        self._project_frame = None
        self._project_frame_label = None
        self._project_box = None
        self._comp_frame = None
        self._comp_frame_label = None
        self._comp_box = None
        self._css_store = None
        self._css_tree = None

    def build(self):
        self._styles_scrolled = Gtk.ScrolledWindow()
        self._styles_scrolled.set_vexpand(True)

        styles_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        styles_vbox.set_margin_top(8)
        styles_vbox.set_margin_bottom(8)
        styles_vbox.set_margin_start(8)
        styles_vbox.set_margin_end(8)

        header = Gtk.Label()
        header.set_xalign(0)
        header.get_style_context().add_class("heading")
        styles_vbox.pack_start(header, False, False, 0)

        hierarchy_label = Gtk.Label(label="Jerarquia de estilos — los de abajo sobreescriben")
        hierarchy_label.set_xalign(0)
        styles_vbox.pack_start(hierarchy_label, False, False, 0)

        self._theme_frame = Gtk.Frame()
        self._theme_frame_label = Gtk.Label()
        self._theme_frame_label.set_use_markup(True)
        self._theme_frame.set_label_widget(self._theme_frame_label)
        theme_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        theme_inner.set_margin_top(6)
        theme_inner.set_margin_bottom(6)
        theme_inner.set_margin_start(8)
        theme_inner.set_margin_end(8)
        self._theme_box = theme_inner
        self._theme_frame.add(theme_inner)
        styles_vbox.pack_start(self._theme_frame, False, False, 0)

        self._project_frame = Gtk.Frame()
        self._project_frame_label = Gtk.Label()
        self._project_frame_label.set_use_markup(True)
        self._project_frame.set_label_widget(self._project_frame_label)
        project_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        project_inner.set_margin_top(6)
        project_inner.set_margin_bottom(6)
        project_inner.set_margin_start(8)
        project_inner.set_margin_end(8)
        self._project_box = project_inner
        self._project_frame.add(project_inner)
        styles_vbox.pack_start(self._project_frame, False, False, 0)

        self._comp_frame = Gtk.Frame()
        self._comp_frame_label = Gtk.Label()
        self._comp_frame_label.set_use_markup(True)
        self._comp_frame.set_label_widget(self._comp_frame_label)
        comp_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        comp_inner.set_margin_top(6)
        comp_inner.set_margin_bottom(6)
        comp_inner.set_margin_start(8)
        comp_inner.set_margin_end(8)
        self._comp_box = comp_inner
        self._comp_frame.add(comp_inner)
        styles_vbox.pack_start(self._comp_frame, False, False, 0)

        css_header = Gtk.Label(label="Clases CSS disponibles")
        css_header.set_xalign(0)
        css_header.get_style_context().add_class("heading")
        styles_vbox.pack_start(css_header, False, False, 0)

        self._css_store = Gtk.ListStore(str, str, str)
        self._css_tree = Gtk.TreeView(model=self._css_store)
        self._css_tree.set_headers_visible(True)

        r_sel = Gtk.CellRendererText()
        r_sel.set_property("family", "Monospace")
        col_sel = Gtk.TreeViewColumn("Selector", r_sel, text=0)
        col_sel.set_resizable(True)
        col_sel.set_expand(True)
        self._css_tree.append_column(col_sel)

        r_desc = Gtk.CellRendererText()
        r_desc.set_property("wrap-mode", Pango.WrapMode.WORD_CHAR)
        r_desc.set_property("wrap-width", 250)
        col_desc = Gtk.TreeViewColumn("Descripcion", r_desc, text=1)
        col_desc.set_resizable(True)
        col_desc.set_expand(True)
        self._css_tree.append_column(col_desc)

        r_origin = Gtk.CellRendererText()
        col_origin = Gtk.TreeViewColumn("Origen", r_origin, text=2)
        col_origin.set_resizable(True)
        self._css_tree.append_column(col_origin)

        css_scrolled = Gtk.ScrolledWindow()
        css_scrolled.set_vexpand(True)
        css_scrolled.set_min_content_height(130)
        css_scrolled.add(self._css_tree)
        styles_vbox.pack_start(css_scrolled, True, True, 0)

        btn_box = Gtk.Box(spacing=6)
        btn_box.set_margin_top(6)

        theme_mgr_btn = Gtk.Button(label="Gestor de temas...")
        theme_mgr_btn.connect("clicked", self.app._on_theme_manager)
        btn_box.pack_start(theme_mgr_btn, False, False, 0)

        manage_btn = Gtk.Button(label="Gestionar todos los tipos...")
        manage_btn.connect("clicked", self._on_manage_type_css)
        btn_box.pack_start(manage_btn, False, False, 0)

        styles_vbox.pack_start(btn_box, False, False, 0)

        self._styles_scrolled.add(styles_vbox)
        self.app._styles_scrolled = self._styles_scrolled
        return self._styles_scrolled

    def _get_theme_dir(self) -> str:
        return ThemeService.get_theme_path(self.app.project.theme_id) or ""

    def _load_theme_config(self) -> dict:
        theme_dir = self._get_theme_dir()
        if not theme_dir:
            return {}
        theme_yaml = os.path.join(theme_dir, "theme.yaml")
        if os.path.exists(theme_yaml):
            return YamlService.load(theme_yaml)
        return {}

    def _load_theme_css(self, component_type=None) -> str:
        css = ""
        if not self.app.project or not self.app.project.theme_id:
            return css

        theme_dir = self._get_theme_dir()
        if not theme_dir:
            return css

        style_path = os.path.join(theme_dir, "style.css")
        if os.path.exists(style_path):
            with open(style_path, "r") as f:
                css = f.read()

        if component_type is not None:
            theme_config = self._load_theme_config()
            component_styles = theme_config.get("styles", {})
            comp_style_file = component_styles.get(component_type.value)
            if comp_style_file:
                comp_style_path = os.path.join(theme_dir, comp_style_file)
                if os.path.exists(comp_style_path):
                    with open(comp_style_path, "r") as f:
                        css += "\n" + f.read()

        if self.app.project.custom_css:
            css += "\n" + self.app.project.custom_css

        if component_type is not None:
            type_css = self.app.project.type_css_overrides.get(component_type.value)
            if type_css:
                css += "\n" + type_css

        return css

    def _ensure_style_doc_svc(self):
        if not hasattr(self, "_style_doc_svc") or self._style_doc_svc is None:
            theme_dir = self._get_theme_dir()
            if not theme_dir:
                theme_dir = str(ThemeService.BUILTIN_DIR / "classic")
            self._style_doc_svc = StyleDocService(theme_dir)
        return self._style_doc_svc

    def update(self, component_type=None):
        front_buf = self.app.front_textview.get_buffer()
        if not self.app.project or component_type is None:
            front_buf.set_text(
                "Selecciona un componente para ver los metadatos.\n\n"
                "Consejos de sintaxis Markdown:\n"
                "  — Usa {.clase} para aplicar una clase CSS.\n"
                "  — Usa <!-- Table: titulo --> antes de una tabla para\n"
                "    asignarle un titulo y que aparezca en la Lista de Tablas.\n"
                "  — Usa ![alt](ruta) para imagenes. Las imagenes en\n"
                "    images/illustrations/ se numeran automaticamente.\n"
                "  — Usa {lang=en} para cambiar idioma del corrector."
            )
        else:
            comp_label = self.app.project_manager.resolve_labels().get(component_type.value, COMPONENT_TYPE_LABELS.get(component_type, component_type.value))
            type_key = component_type.value
            fm_lines = [
                f"Metadatos para {comp_label}:",
                "",
            ]
            type_vars = FRONTMATTER_DOCS.get(type_key, [])
            type_names = {v[0] for v in type_vars}
            common_vars = [v for v in FRONTMATTER_COMMON if v[0] not in type_names]
            vars_list = type_vars + common_vars
            for var_name, description in vars_list:
                fm_lines.append(f"  {var_name}")
                fm_lines.append(f"    {description}")
                fm_lines.append("")
            fm_lines.append("Los metadatos se añaden al principio del componente")
            fm_lines.append("(entre las lineas --- al inicio del archivo).")
            front_buf.set_text("\n".join(fm_lines))

        self._styles_current_comp_type = component_type
        theme_config = self._load_theme_config()
        svc = self._ensure_style_doc_svc()

        for child in self._theme_box.get_children():
            self._theme_box.remove(child)
        for child in self._project_box.get_children():
            self._project_box.remove(child)
        for child in self._comp_box.get_children():
            self._comp_box.remove(child)

        project_opened = self.app.project is not None
        theme_name = ""
        theme_dir = ""
        theme_is_builtin = True
        if project_opened:
            theme_dir = self._get_theme_dir()
            theme = ThemeService.get_theme(self.app.project.theme_id)
            if theme:
                theme_name = theme.name
                theme_is_builtin = theme.is_builtin

        if project_opened and theme_dir:
            theme_scope = "compartido entre todos los libros con este tema"
            self._theme_frame_label.set_markup(
                f"<b>Tema: {theme_name}</b>  <small>({theme_scope})</small>"
            )
            self._theme_frame.set_visible(True)

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            row.pack_start(Gtk.Label(label="Base: style.css", xalign=0), True, True, 0)
            if theme_is_builtin:
                btn = Gtk.Button(label="Ver")
                btn.set_tooltip_text("Solo lectura — los temas integrados no se editan")
            else:
                btn = Gtk.Button(label="Editar")
                btn.set_tooltip_text("Atencion: los cambios afectaran a TODOS los libros que usen este tema")
            btn.connect("clicked", lambda b: self._on_view_theme_css_by_file("style.css", theme_name))
            row.pack_start(btn, False, False, 0)
            self._theme_box.pack_start(row, False, False, 0)

            if component_type is not None:
                type_value = component_type.value
                type_file = theme_config.get("styles", {}).get(type_value, "")
                type_label = self.app.project_manager.resolve_labels().get(component_type.value, COMPONENT_TYPE_LABELS.get(component_type, type_value))
                if type_file:
                    row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                    row2.pack_start(Gtk.Label(label=f"Tipo {type_label}: {type_file}", xalign=0), True, True, 0)
                    btn2 = Gtk.Button(label="Ver" if theme_is_builtin else "Editar")
                    if theme_is_builtin:
                        btn2.set_tooltip_text("Solo lectura — los temas integrados no se editan")
                    else:
                        btn2.set_tooltip_text("Atencion: los cambios afectaran a TODOS los libros que usen este tema")
                    btn2.connect("clicked", lambda b, f=type_file: self._on_view_theme_css_by_file(f, theme_name))
                    row2.pack_start(btn2, False, False, 0)
                    self._theme_box.pack_start(row2, False, False, 0)
        else:
            self._theme_frame.set_visible(False)

        if project_opened:
            self._project_frame_label.set_markup(
                f"<b>Proyecto: {self.app.project.title}</b>  <small>(solo este libro)</small>"
            )
            self._project_frame.set_visible(True)

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            status = "Editado" if self.app.project.custom_css.strip() else "Sin cambios"
            row.pack_start(Gtk.Label(label="Estilos globales", xalign=0), True, True, 0)
            status_lbl = Gtk.Label(label=status, xalign=0)
            row.pack_start(status_lbl, False, False, 0)
            btn = Gtk.Button(label="Editar")
            btn.connect("clicked", self._on_edit_book_css)
            row.pack_start(btn, False, False, 0)
            self._project_box.pack_start(row, False, False, 0)

            if component_type is not None:
                type_value = component_type.value
                type_label = self.app.project_manager.resolve_labels().get(component_type.value, COMPONENT_TYPE_LABELS.get(component_type, type_value))
                has_override = type_value in self.app.project.type_css_overrides
                row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                row2.pack_start(Gtk.Label(label=f"Tipo: {type_label}", xalign=0), True, True, 0)
                status2 = Gtk.Label(label="Editado" if has_override else "Sin cambios", xalign=0)
                row2.pack_start(status2, False, False, 0)
                btn2 = Gtk.Button(label="Editar")
                btn2.connect("clicked", lambda b, ct=component_type: self._on_styles_edit_type_css(ct))
                row2.pack_start(btn2, False, False, 0)
                if has_override:
                    reset_btn = Gtk.Button(label="Restablecer")
                    reset_btn.connect("clicked", lambda b, ct=component_type: self._on_styles_reset_type_css(ct))
                    row2.pack_start(reset_btn, False, False, 0)
                self._project_box.pack_start(row2, False, False, 0)
        else:
            self._project_frame.set_visible(False)

        if self._styles_current_component and component_type is not None:
            comp = self._styles_current_component
            self._comp_frame_label.set_markup(
                f"<b>Componente: {comp.get_display_name(self.app.project_manager.resolve_labels())}</b>  <small>(solo este componente)</small>"
            )
            self._comp_frame.set_visible(True)

            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            has_comp_css = bool(comp.custom_css.strip())
            row.pack_start(Gtk.Label(label="Estilos del componente", xalign=0), True, True, 0)
            status = Gtk.Label(label="Editado" if has_comp_css else "Sin cambios", xalign=0)
            row.pack_start(status, False, False, 0)
            btn = Gtk.Button(label="Editar")
            btn.connect("clicked", self._on_styles_edit_comp_css)
            row.pack_start(btn, False, False, 0)
            self._comp_box.pack_start(row, False, False, 0)
        else:
            self._comp_frame.set_visible(False)

        self._css_store.clear()
        if project_opened and svc:
            all_docs = []

            theme_global = svc.get_docs("style.css")
            for d in theme_global:
                all_docs.append((d["markdown_hint"], d["description"], f"Tema ({theme_name or 'desconocido'})"))

            if component_type is not None:
                theme_type_docs = svc.get_docs_for_type(component_type, theme_config)
                for d in theme_type_docs:
                    all_docs.append((d["markdown_hint"], d["description"], f"Tema ({theme_name or 'desconocido'}) — tipo"))

            if self.app.project.custom_css:
                book_docs = svc.get_docs_from_css(self.app.project.custom_css)
                for d in book_docs:
                    all_docs.append((d["markdown_hint"], d["description"], "Proyecto (libro)"))

            if component_type is not None:
                type_css = self.app.project.type_css_overrides.get(component_type.value, "")
                if type_css:
                    type_docs = svc.get_docs_from_css(type_css)
                    for d in type_docs:
                        all_docs.append((d["markdown_hint"], d["description"], f"Proyecto (tipo)"))

            if self._styles_current_component and self._styles_current_component.custom_css:
                comp_docs = svc.get_docs_from_css(self._styles_current_component.custom_css)
                for d in comp_docs:
                    all_docs.append((d["markdown_hint"], d["description"], "Componente"))

            for selector, desc, origin in all_docs:
                self._css_store.append([selector, desc, origin])

        self._styles_scrolled.show_all()

    def _on_styles_edit_type_css(self, component_type):
        ct = component_type
        type_key = ct.value
        current = self.app.project.type_css_overrides.get(type_key, "")
        label = self.app.project_manager.resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct])
        css = self._edit_css_dialog(f"Estilos del tipo: {label}", current, scope_type="type", scope_type_value=ct.value)
        if css is None:
            return
        if css.strip():
            self.app.project.type_css_overrides[type_key] = css
        else:
            self.app.project.type_css_overrides.pop(type_key, None)
        FileService.save_project(self.app.project)
        self.app.editor_view._update_preview()
        self.update(ct)
        self.app._update_status(f"Estilos del tipo '{label}' actualizados")

    def _on_styles_reset_type_css(self, component_type):
        ct = component_type
        type_key = ct.value
        label = self.app.project_manager.resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct])
        if type_key not in self.app.project.type_css_overrides:
            return
        if not confirm(self.app.window, f"Restablecer estilos del tipo «{label}»?\nSe perderan los cambios personalizados."):
            return
        del self.app.project.type_css_overrides[type_key]
        FileService.save_project(self.app.project)
        self.app.editor_view._update_preview()
        self.update(ct)
        self.app._update_status(f"Estilos del tipo '{label}' restablecidos al tema")

    def _on_styles_edit_comp_css(self, btn):
        if not self._styles_current_component:
            return
        self._on_edit_component_css(btn, self._styles_current_component)

    def _on_view_theme_css_by_file(self, filename, theme_name=None):
        if not self.app.project:
            return
        theme_id = self.app.project.theme_id
        theme = ThemeService.get_theme(theme_id)
        if not theme:
            return
        theme_dir = theme.path
        fpath = os.path.join(theme_dir, filename)
        if not os.path.exists(fpath):
            show_info(self.app.window, f"El archivo {filename} no existe en el tema.")
            return

        with open(fpath, "r") as f:
            text = f.read()

        display_name = theme_name or theme.name
        is_read_only = theme.is_builtin
        mode_title = "Visualizar" if is_read_only else "Editar"

        editor_dialog = Gtk.Dialog(
            title=f"{mode_title} CSS: {display_name} — {filename}",
            transient_for=self.app.window,
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

        if not is_read_only:
            warning = Gtk.Label()
            warning.set_markup(
                "<b>Los cambios en este tema afectaran a TODOS los libros que lo usen.</b>"
            )
            warning.set_xalign(0)
            editor_content.pack_start(warning, False, False, 0)

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
        buf.set_text(text)
        scrolled.add(text_view)
        editor_content.pack_start(scrolled, True, True, 0)

        def on_editor_response(d, response):
            if response == Gtk.ResponseType.ACCEPT and not is_read_only:
                new_text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
                with open(fpath, "w") as f:
                    f.write(new_text)
                self.update(self._styles_current_comp_type)
                self.app.editor_view._update_preview()
            d.destroy()

        editor_dialog.connect("response", on_editor_response)
        editor_dialog.show_all()

    def _edit_css_dialog(self, title: str, initial_css: str, scope_type: str = "", scope_type_value: str = "") -> str:
        dialog = Gtk.Dialog(
            title=title,
            transient_for=self.app.window,
            flags=0,
        )
        dialog.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        dialog.add_button("Guardar", Gtk.ResponseType.OK)
        dialog.set_default_size(600, 500)

        box = dialog.get_content_area()

        if scope_type:
            hints = []
            if scope_type == "book":
                hints.append("Editando estilos globales del libro (afectan a TODOS los componentes).")
            elif scope_type == "type" and scope_type_value:
                hints.append(
                    f"Selector principal: <b>.component-{scope_type_value}</b>"
                )
                hints.append(
                    f"Sub-elementos: <b>.component-{scope_type_value}</b> h1, h2, p, ul, li, img, blockquote, etc."
                )
                hints.append("Usa prefijos de clase (p.ej. <b>.toc-entry</b>) para elementos auto-generados.")
            elif scope_type == "component" and scope_type_value:
                hints.append(
                    f"Selector principal: <b>.component-{scope_type_value}</b>"
                )
                hints.append("Estos estilos solo afectan a este componente.")
            elif scope_type == "theme":
                hints.append("Editando estilos del tema (afectan a TODOS los libros que usen este tema).")

            if hints:
                hint_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                hint_bar.set_margin_bottom(8)
                for h in hints:
                    lbl = Gtk.Label()
                    lbl.set_markup(f'<span size="small" foreground="#444">{h}</span>')
                    lbl.set_xalign(0)
                    lbl.set_line_wrap(True)
                    hint_bar.pack_start(lbl, False, False, 0)
                box.pack_start(hint_bar, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        buffer = GtkSource.Buffer.new_with_language(
            GtkSource.LanguageManager.get_default().get_language("css")
        )
        if not initial_css.strip() and scope_type_value:
            if scope_type == "type":
                initial_css = (
                    f"/* Estilos para el tipo «{scope_type_value}»\n"
                    f" * Selector principal: .component-{scope_type_value}\n"
                    f" * Ejemplos:\n"
                    f" *   .component-{scope_type_value} p {{ }}\n"
                    f" *   .component-{scope_type_value} h1 {{ }}\n"
                    f" *   .component-{scope_type_value} blockquote {{ }}\n"
                    f" */\n\n"
                )
            elif scope_type == "component":
                initial_css = (
                    f"/* Estilos para este componente (tipo «{scope_type_value}»)\n"
                    f" * Selector principal: .component-{scope_type_value}\n"
                    f" * Ejemplos:\n"
                    f" *   .component-{scope_type_value} p {{ }}\n"
                    f" *   .component-{scope_type_value} img {{ }}\n"
                    f" */\n\n"
                )
            elif scope_type == "book":
                initial_css = (
                    "/* Estilos globales del libro\n"
                    " * Afectan a todos los componentes.\n"
                    " * Selectores principales:\n"
                    " *   body { }  p { }  h1, h2, h3 { }\n"
                    " *   .component-chapter { }  .component-title { }  etc.\n"
                    " */\n\n"
                )
        buffer.set_text(initial_css)
        textview = GtkSource.View.new_with_buffer(buffer)
        textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        textview.set_monospace(True)
        scrolled.add(textview)

        box.pack_start(scrolled, True, True, 0)
        dialog.show_all()

        result = dialog.run()
        css = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        dialog.destroy()
        if result == Gtk.ResponseType.OK:
            return css
        return None

    def _on_edit_book_css(self, widget):
        if not self.app.project:
            show_info(self.app.window, "Abre un proyecto primero")
            return
        css = self._edit_css_dialog("Estilos del libro", self.app.project.custom_css, scope_type="book")
        if css is None:
            return
        self.app.project.custom_css = css
        FileService.save_project(self.app.project)
        self.app.editor_view._update_preview()
        self.update(
            self.app.current_component.type if self.app.current_component else None
        )
        self.app._update_status("Estilos del libro actualizados")

    def _on_edit_type_css(self, widget, component):
        if not self.app.project:
            return
        type_key = component.type.value
        current = self.app.project.type_css_overrides.get(type_key, "")
        label = self.app.project_manager.resolve_labels().get(component.type.value, COMPONENT_TYPE_LABELS.get(component.type, type_key))
        css = self._edit_css_dialog(f"Estilos del tipo: {label}", current, scope_type="type", scope_type_value=component.type.value)
        if css is None:
            return
        if css.strip():
            self.app.project.type_css_overrides[type_key] = css
        else:
            self.app.project.type_css_overrides.pop(type_key, None)
        FileService.save_project(self.app.project)
        self.app.editor_view._update_preview()
        self.update(component.type)
        self.app._update_status(f"Estilos del tipo '{label}' actualizados")

    def _on_edit_component_css(self, widget, component):
        if not self.app.project:
            return
        css = self._edit_css_dialog(
            f"Estilos del componente: {component.get_display_name(self.app.project_manager.resolve_labels())}",
            component.custom_css,
            scope_type="component",
            scope_type_value=component.type.value,
        )
        if css is None:
            return
        component.custom_css = css
        FileService.save_project(self.app.project)
        self.app.editor_view._update_preview()
        self.update(component.type)
        self.app._update_status(f"Estilos del componente '{component.get_display_name(self.app.project_manager.resolve_labels())}' actualizados")

    def _on_manage_type_css(self, widget):
        if not self.app.project:
            show_info(self.app.window, "Abre un proyecto primero")
            return

        dialog = Gtk.Dialog(
            title="Gestionar estilos por tipo",
            transient_for=self.app.window,
            flags=0,
        )
        dialog.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(450, 400)

        store = Gtk.ListStore(str, str, str)
        for ct in ComponentType:
            label = self.app.project_manager.resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct])
            has_css = ct.value in self.app.project.type_css_overrides
            status = "Editado" if has_css else "Por defecto del tema"
            store.append([label, status, ct.value])

        tree = Gtk.TreeView(model=store)
        tree.set_headers_visible(True)
        renderer_label = Gtk.CellRendererText()
        col_label = Gtk.TreeViewColumn("Tipo", renderer_label, text=0)
        col_label.set_resizable(True)
        col_label.set_expand(True)
        tree.append_column(col_label)
        renderer_status = Gtk.CellRendererText()
        col_status = Gtk.TreeViewColumn("Estado", renderer_status, text=1)
        col_status.set_resizable(True)
        tree.append_column(col_status)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.add(tree)
        box = dialog.get_content_area()
        box.pack_start(scrolled, True, True, 0)

        btn_box = Gtk.Box(spacing=6)
        btn_edit = Gtk.Button(label="Editar")
        btn_reset = Gtk.Button(label="Restablecer")
        btn_box.pack_start(btn_edit, False, False, 0)
        btn_box.pack_start(btn_reset, False, False, 0)
        box.pack_start(btn_box, False, False, 0)

        def _selected_type():
            sel = tree.get_selection()
            model, it = sel.get_selected()
            if it is None:
                return None
            return model.get_value(it, 2)

        def _on_edit(btn):
            type_key = _selected_type()
            if not type_key:
                return
            ct = ComponentType(type_key)
            label = self.app.project_manager.resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct])
            current = self.app.project.type_css_overrides.get(type_key, "")
            css = self._edit_css_dialog(f"Estilos del tipo: {label}", current, scope_type="type", scope_type_value=ct.value)
            if css is None:
                return
            if css.strip():
                self.app.project.type_css_overrides[type_key] = css
            else:
                self.app.project.type_css_overrides.pop(type_key, None)
            FileService.save_project(self.app.project)
            self.app.editor_view._update_preview()
            if self.app.current_component:
                self.update(self.app.current_component.type)
            self.app._update_status(f"Estilos del tipo '{label}' actualizados")
            _refresh_list()

        def _on_reset(btn):
            type_key = _selected_type()
            if not type_key:
                return
            ct = ComponentType(type_key)
            label = self.app.project_manager.resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct])
            if type_key not in self.app.project.type_css_overrides:
                return
            if not confirm(self.app.window, f"Restablecer estilos del tipo «{label}»?\nSe perderán los cambios personalizados."):
                return
            del self.app.project.type_css_overrides[type_key]
            FileService.save_project(self.app.project)
            self.app.editor_view._update_preview()
            if self.app.current_component:
                self.update(self.app.current_component.type)
            self.app._update_status(f"Estilos del tipo '{label}' restablecidos al tema")
            _refresh_list()

        def _refresh_list():
            store.clear()
            for ct in ComponentType:
                label = self.app.project_manager.resolve_labels().get(ct.value, COMPONENT_TYPE_LABELS[ct])
                has_css = ct.value in self.app.project.type_css_overrides
                status = "Editado" if has_css else "Por defecto del tema"
                store.append([label, status, ct.value])

        tree.connect("row-activated", lambda t, path, col: _on_edit(None))
        btn_edit.connect("clicked", _on_edit)
        btn_reset.connect("clicked", _on_reset)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

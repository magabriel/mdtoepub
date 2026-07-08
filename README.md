# MDToEPUB

A desktop application for writing and publishing EPUB ebooks from Markdown. Built with GTK3 and Python.

## Features

- **Project-based workflow**: Organize your book into components (chapters, preface, appendix, etc.) with drag-and-drop reordering.
- **Live preview**: Real-time Markdown-to-HTML preview via WebKit, updated as you type.
- **EPUB export**: Generate standards-compliant EPUB 2/3 files with embedded images and CSS.
- **Theme system**: Fully customizable CSS themes with per-component-type styles and a drop-cap system.
- **Spell-check**: Multi-language spell-check with `{lang=xx}` inline markers, per-project dictionaries, and code-block exclusion.
- **Syntax highlighting**: Code blocks are highlighted with Pygments in both the preview and exported EPUB.
- **Image management**: Import and manage illustrations and decorative images.
- **Import from Markdown**: Parse a single large Markdown file into separate components.
- **Part grouping**: Group chapters into parts with auto-generated part pages.

## Requirements

### Runtime

- Python >= 3.10
- GTK 3 (with introspection)
- WebKit2GTK 4.1
- GtkSourceView 4
- GtkSpell 3

Python packages (installed automatically via pip):

| Package | Purpose |
|---------|---------|
| PyYAML | YAML configuration parsing |
| Markdown | Markdown to HTML conversion |
| ebooklib | EPUB file generation |
| Pillow | Image processing |
| PyGObject | Python GTK bindings |

### Development

- pytest (for running tests)

## Installation

### From source

```bash
git clone <repository-url> mdtoepub
cd mdtoepub
pip install .
mdtoepub
```

### Development install

```bash
pip install -e ".[dev]"
./run.sh
```

## Usage

1. **Create a project**: File → New Project (or toolbar button).
2. **Add components**: Component → Add Component, choose a type and title.
3. **Write content**: Edit the Markdown content in the editor panel.
4. **Preview**: Switch to the Preview tab to see the rendered output.
5. **Export**: Click Export EPUB or File → Export → Export EPUB.

### Writing Markdown

The editor supports standard Markdown with these extensions:

- Tables
- Fenced code blocks (with syntax highlighting)
- TOC generation
- Frontmatter (YAML metadata per component)
- Attribute lists (`{.class}` for CSS styling)
- Code highlighting with language specifier: ```` ```python ````

### Spell-check

Spell-check is enabled by default. Right-click a misspelled word for suggestions and dictionary options.

Use `{lang=en}` inline to switch the spell-check language mid-text:

```markdown
Este texto está en español. {lang=en}This text is in English.
```

Language markers are automatically stripped from the EPUB output.

### Images

Place images in the `images/illustrations/` or `images/decorative/` directories and reference them in Markdown:

```markdown
![Alt text](images/illustrations/photo.jpg)
```

## Configuration

### Per-project

Most settings are configured per project via File → Project Configuration:

- Title, author, language
- EPUB version (2 or 3)
- Auto-chapter title mode
- Theme
- Drop cap settings
- Spell-check language
- Export filename

### Global

User-level settings via Configuration → Global:

- Editor font size and tab size
- Auto-save interval
- Preview zoom
- EPUB reader path

## Themes

Themes are CSS-based and control the visual appearance of the generated EPUB.

### Theme types

- **Built-in themes** — shipped with the application in `mdtoepub/themes/`. Read-only.
- **Custom themes** — user-created, stored in `~/.config/mdtoepub/themes/`. Fully manageable.

### Theme manager

Use **Configuración → Temas** to open the theme manager, where you can:

- **Activar tema** — apply a built-in or custom theme to the current project
- **Crear tema en blanco** — create a new empty custom theme
- **Clonar tema** — duplicate any existing theme (built-in or custom) as a new custom theme
- **Editar CSS** — modify the CSS files of a custom theme
- **Renombrar / Eliminar** — manage your custom themes

### Theme structure

Each theme provides:

- `style.css` — global element styles and utility classes
- Per-component CSS files (e.g., `chapter.css`, `cover.css`, `toc.css`)
- `theme.yaml` — metadata and component-to-CSS mapping

Utility classes (usable via `{.class}` attribute lists):

| Class | Purpose |
|-------|---------|
| `.center` | Centered text |
| `.right` | Right-aligned text |
| `.tiny`, `.small`, `.big`, `.huge` | Font size scales |
| `.no-indent` | Remove paragraph indent |
| `.compact` | Tight line-height |
| `.sans` | Sans-serif font |
| `.small-caps` | Small caps variant |
| `.muted` | Grayed text |
| `.page-break` | Force page break before |
| `.avoid-break` | Prevent page break inside |
| `.epigraph` | Epigraph block (right, italic, small) |
| `.ornament` | Decorative centered image |
| `.chapter-ornament` | Chapter separator |
| `.paragraph-separator` | Paragraph divider |
| `.drop-cap` | Drop cap (first letter) |

## Project structure

```
project/
├── project.yaml          # Project metadata and component list
├── components/           # Markdown files for each component
├── images/
│   ├── illustrations/    # Inline images referenced in Markdown
│   └── decorative/       # Decorative images (ornaments, etc.)
├── styles/
│   ├── book.css          # Book-level custom CSS
│   ├── types/            # Per-component-type CSS overrides
│   └── components/       # Per-component CSS overrides
└── output/               # Generated EPUB files
```

## License

GNU General Public License v3.0 or later.

# Architecture

## Overview

MDToEPUB is a GTK3 desktop application with a modular architecture. The UI is split across view classes in `views/`, dialog functions in `views/dialogs/`, and controllers in `controllers/`. The `MDToEPUBApp` class in `main.py` (~500 lines) serves as a thin coordinator that wires everything together, holds shared state, and delegates to subordinate modules.

```
┌──────────────────────────────────────────────────────────┐
│                       main.py                             │
│  MDToEPUBApp (Gtk.Application) — thin coordinator         │
│    ├── Project lifecycle (new/open/save/close)           │
│    ├── Global config & recent projects                   │
│    └── Delegation to views/controllers                   │
├──────────────────────────────────────────────────────────┤
│                       views/                              │
│  main_window.py   EditorView + preview                    │
│  editor_view.py   GtkSource editor + WebKit2 preview      │
│  styles_panel.py  CSS cascade hierarchy panel             │
│  project_tree.py  Tree navigator + component CRUD         │
│  dialogs/                                                │
│    project_config.py  Project settings (book/apariencia)  │
│    theme_manager.py   Theme CRUD (create/clone/delete)   │
│    image_manager.py   Image import/categorize widgets     │
├──────────────────────────────────────────────────────────┤
│                    controllers/                            │
│  export_import.py  EPUB export, Markdown/EPUB import      │
├──────────────────────────────────────────────────────────┤
│                      services/                             │
│  MarkdownService   EpubService   FileService              │
│  YamlService       ImageService  SpellCheckService        │
│  StyleDocService   ThemeService  LabelsService            │
├──────────────────────────────────────────────────────────┤
│                      models/                               │
│  Project    Component    ComponentType    Theme            │
└──────────────────────────────────────────────────────────┘
```

## Directory layout

```
mdtoepub/
├── main.py                      # Entry point, thin app coordinator
├── views/
│   ├── main_window.py           # Menubar, toolbar, statusbar, paned layout
│   ├── editor_view.py           # GtkSource editor + WebKit2 preview
│   ├── styles_panel.py          # CSS 4-level cascade panel
│   ├── project_tree.py          # Project navigator tree + component CRUD
│   └── dialogs/
│       ├── project_config.py    # Project configuration dialog
│       ├── theme_manager.py     # Theme lifecycle manager
│       └── image_manager.py     # Image import & categorization
├── controllers/
│   └── export_import.py         # EPUB export/import operations
├── models/
│   ├── component.py             # Component dataclass, ComponentType enum
│   ├── project.py               # Project dataclass (aggregate root)
│   └── theme.py                 # Theme dataclass
├── services/
│   ├── markdown_service.py      # Markdown → HTML rendering
│   ├── epub_service.py          # EPUB generation pipeline
│   ├── file_service.py          # File I/O, project structure management
│   ├── yaml_service.py          # YAML load/save/frontmatter parsing
│   ├── image_service.py         # Image validation and optimization
│   ├── spell_service.py         # Multi-language spell-check
│   ├── style_doc_service.py     # CSS @doc comment extraction
│   ├── theme_service.py         # Theme discovery, CRUD, clone
│   └── labels_service.py        # Multi-language component labels
├── themes/
│   └── classic/                 # Built-in CSS theme
├── data/
│   └── sample_book/             # Demo project
├── lang-specs/
│   └── mdtoepub-help.lang       # GtkSource language for help panels
└── tests/                       # pytest test suite
```

## Data models

### Project (aggregate root)

`models/project.py:7`

The `Project` dataclass holds all book-level configuration and owns the component list.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | str | `""` | Directory name |
| `title` | str | `""` | Book title |
| `author` | str | `""` | Book author |
| `language` | str | `"es"` | Language code |
| `theme_id` | str | `"classic"` | Active theme |
| `epub_version` | str | `"epub3"` | `"epub2"` or `"epub3"` |
| `auto_chapter_title` | str | `"none"` | Auto-numbering mode |
| `components` | List[Component] | `[]` | Book components |
| `custom_css` | str | `""` | Book-level CSS overrides |
| `type_css_overrides` | Dict[str, str] | `{}` | Per-type CSS overrides |
| `drop_cap_enabled` | bool | `True` | Enable drop caps |
| `drop_cap_types` | List[str] | `["chapter"]` | Types with drop caps |
| `path` | str | `""` | Filesystem path |
| `export_filename` | str | `""` | Custom EPUB filename |
| `spell_lang` | str | `"es_ES"` | Default spell-check language |
| `spell_words` | List[str] | `[]` | Project dictionary |

### Component

`models/component.py:50`

Each component represents a section of the book.

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | UUID |
| `type` | ComponentType | Enum (chapter, preface, etc.) |
| `title` | str | Display title |
| `filename` | str | Markdown file in `components/` |
| `order` | int | Sort position |
| `part_id` | Optional[str] | Parent part component ID |
| `frontmatter` | Dict | Per-component YAML frontmatter |
| `custom_css` | str | Per-component CSS overrides |

### ComponentType enum

`models/component.py:10`

20 component types organized in three groups: **Front** (cover, title, license, etc.), **Preliminary** (toc, foreword, preface, etc.), **Body** (part, chapter, conclusion, etc.), and **Back** (appendix, glossary).

## Service layer

### MarkdownService

`services/markdown_service.py:7`

Converts Markdown to HTML using Python-Markdown with extensions:
- `tables`, `fenced_code`, `codehilite`, `toc`, `meta`, `attr_list`

Key methods:
- `render(text, component_type, component_id)` — strips `{lang=xx}` markers, renders Markdown, wraps in `<section class="component-{type}">`.
- `get_code_css()` — static, returns Pygments-friendly CSS for code syntax highlighting.

### EpubService

`services/epub_service.py:56`

Full EPUB generation pipeline using `ebooklib`.

```
EpubService.generate(output_path, epub_version)
  ├── Create EpubBook
  ├── Set metadata (title, author, language, etc.)
  ├── Load stylesheet (_load_stylesheet)
  │   ├── Theme base CSS (style.css)
  │   ├── Theme per-component CSS
  │   ├── Book-level custom CSS
  │   └── Pygments code CSS
  ├── Create style items
  ├── Create part chapters (_create_part_chapter)
  ├── Create component chapters (_create_chapter)
  │   ├── Load Markdown, parse frontmatter
  │   ├── Split title on ` - ` → subtitle
  │   ├── Build header HTML (h1.component-header)
  │   ├── Render Markdown via MarkdownService
  │   ├── Apply drop cap
  │   └── Attach styles
  ├── Build TOC (groups chapters under parts)
  ├── Build spine
  └── Write EPUB file
```

Key implementation details:
- Title auto-splitting: `re.split(r' +[—–-]+ +', title, maxsplit=1)` produces `(subtitle, title)`.
- Drop cap: replaces the first alphanumeric character(s) with `<span class="drop-cap">`.
- Chapter numbering: counted sequentially through CHAPTER-type components.
- `toc_include` / `toc_deep`: read from the TOC component's frontmatter to filter heading depth.
- Images: embedded by scanning HTML for `<img src="...">`, skipping URLs.

### FileService

`services/file_service.py:79`

Manages the filesystem representation of a project:

- `create_project_structure(path, name)` — creates directory tree.
- `load_project(path)` — reads `project.yaml`, loads CSS from `styles/`.
- `save_project(project)` — writes CSS to files, saves `project.yaml`.
- `import_book()` — parses a single large Markdown file into components.

Project data is split across files:
- `project.yaml` — metadata and component list.
- `styles/book.css` — `project.custom_css`
- `styles/types/<type>.css` — `project.type_css_overrides`
- `styles/components/<id>.css` — `component.custom_css`

### SpellCheckService

`services/spell_service.py:14`

Multi-language spell-check with inline `{lang=xx}` markers.

```
                            text
                              │
                              ▼
                    get_excluded_ranges()
                    (fenced blocks + inline code)
                              │
                              ▼
                    parse_regions(text, excluded)
                    ({lang=xx} markers → language regions)
                              │
                              ▼
                    For each region:
                      tokenize words
                      skip if in code range
                      skip if in ignore_words set
                      skip if in global dictionary
                      check with GtkSpell.Checker for region's language
                              │
                              ▼
                    [(start, end, word, lang), ...]
```

- Fenced code blocks and inline backtick code are excluded from both spell-check and `{lang=xx}` parsing.
- `GtkSpell.Checker` instances are cached per language.
- `add_global_word()` persists to the system enchant/aspell personal dictionary.
- `ignore_words` includes project words (persisted) + session words (transient).

### YamlService

`services/yaml_service.py:6`

Utility for YAML operations:
- `load(path)` / `save(data, path)` — read/write YAML files.
- `parse_frontmatter(content)` — extracts `---` delimited frontmatter from Markdown.
- `join_content(frontmatter, markdown)` — re-attaches frontmatter.

### StyleDocService

`services/style_doc_service.py:15`

Extracts documentation from CSS `@doc` comments:

```css
/* @doc Description of the class */
.selector { ... }
```

Parsed by regex: `/\*\s*@doc\s+(.+?)\s*\*/\s*([^{]+?)\s*\{`

Returns `{description, selector, label, markdown_hint}` tuples used by the help panels.

## UI architecture

The UI is built programmatically (no Glade files) in `main.py`.

### Layout

```
┌──────────────────────────────────────────────────────┐
│ Menu Bar                                             │
├──────────────────────────────────────────────────────┤
│ Tool Bar                                             │
├───────────────────┬──────────────────────────────────┤
│ StackSidebar      │ Gtk.Stack                        │
│ [Contenido]       │   ├── Contenido (Notebook)       │
│ [Tema]            │   │   ├── Editor                  │
│ [Ayuda]           │   │   └── Preview                 │
│                   │   ├── Tema (Notebook)             │
│                   │   │   ├── Tipo de componente      │
│                   │   │   └── Global                  │
│                   │   └── Ayuda (direct)              │
├───────────────────┴──────────────────────────────────┤
│ Status Bar                                           │
└──────────────────────────────────────────────────────┘
```

### Editor

- `GtkSource.View` with the `markdown` language for syntax highlighting.
- Monospace font, word-wrap enabled.
- Spell-check integration: `Pango.Underline.ERROR` tag for misspelled words.
- Debounced (600 ms) spell-check on buffer changes.
- Right-click context menu with suggestions, ignore, and dictionary options.

### Preview

- `WebKit2.WebView` renders live HTML.
- Updates on every keystroke (no debounce for preview).
- CSS is loaded from the theme, book styles, type overrides, component styles, and Pygments in that order.
- Base URI set to the project directory for image resolution.

### Project tree

- `Gtk.TreeView` with `Gtk.TreeStore`.
- Icons via `CellRendererPixbuf`.
- Drag-and-drop for reordering and reparenting (moving components into/out of parts).
- Right-click context menu (context-sensitive).
- Multiple selection support.

## CSS system

Styles are applied in cascading layers (increasing priority):

| Layer | Source | File |
|-------|--------|------|
| 1. Theme base | `style.css` | Theme directory |
| 2. Theme per-type | `chapter.css`, etc. | Theme directory |
| 3. Book custom | `project.custom_css` | `styles/book.css` |
| 4. Type override | `project.type_css_overrides` | `styles/types/<type>.css` |
| 5. Component custom | `component.custom_css` | `styles/components/<id>.css` |
| 6. Code syntax | Pygments highlight CSS | Generated |

Component HTML is wrapped in `<section class="component-{type}">`, scoping all per-type CSS.

The auto-header uses `<h1 class="component-header">` with inner spans:
- `.header-number` — auto-numbering (e.g., "Capítulo 1")
- `.header-subtitle` — split subtitle
- `.header-title` — main title

All per-type CSS files use `:not(.component-header)` to avoid styling auto-headers with element `h1` rules.

## Theme system

### Theme types

There are two types of themes:

| Type | Location | Editable |
|------|----------|----------|
| Built-in (integrados) | `mdtoepub/themes/<id>/` | Read-only |
| Custom (personalizados) | `~/.config/mdtoepub/themes/<id>/` | Full CRUD |

### Theme directory structure

Each theme consists of:

```
theme.yaml         — metadata + component-to-CSS mapping
style.css          — base styles (body, headings, paragraphs, utility classes)
<type>.css         — one file per ComponentType
```

The `theme.yaml` maps each component type to its CSS file:

```yaml
id: "classic"
name: "Clásico"
description: "Tema clásico para libros de narrativa"
author: ""
version: "1.0"
source_theme_id: null        # set when cloned from another theme
base_style: style.css
styles:
  chapter: chapter.css
  cover: cover.css
  ...
fonts:
  serif: "Georgia, serif"
  sans: "Helvetica, sans-serif"
```

CSS files can contain `@doc` comments for auto-documentation in the help panels.

### Theme model

`models/theme.py:7`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | str | `""` | Unique identifier (slug) |
| `name` | str | `""` | Display name |
| `description` | str | `""` | Short description |
| `is_builtin` | bool | `True` | Whether it ships with the app |
| `source_theme_id` | Optional[str] | `None` | Original theme if cloned |
| `author` | str | `""` | Theme author |
| `version` | str | `"1.0"` | Theme version |
| `base_style` | str | `"style.css"` | Default CSS file |
| `styles` | Dict[str, str] | `{}` | Per-component-type CSS mapping |
| `path` | Optional[str] | `None` | Absolute filesystem path |

### ThemeService

`services/theme_service.py:37`

Manages theme discovery and lifecycle:

- **Discovery**: scans both built-in and custom directories, merges results
- **Create blank**: generates a minimal `theme.yaml` + `style.css` with all component types mapped
- **Clone**: copies entire theme directory, updates metadata with `source_theme_id`
- **Delete**: removes custom theme directory (built-in protected)
- **Rename**: updates `name` in `theme.yaml` (built-in protected)

Key methods:
- `list_themes()` — returns all available themes
- `get_theme(theme_id)` — single theme lookup
- `get_theme_path(theme_id)` — resolve filesystem path
- `create_blank(name, ...)` — new empty theme
- `clone_theme(source_id, new_name, ...)` — copy existing theme
- `delete_theme(theme_id)` — remove custom theme
- `rename_theme(theme_id, new_name)` — rename custom theme

### Theme manager UI

The theme manager dialog (`_on_theme_manager` in `main.py`) provides:
- List of all themes with type indicator (Integrado / Personalizado)
- **Activar tema**: applies the selected theme to the current project
- **Crear tema en blanco**: creates a new empty custom theme
- **Clonar tema**: clones any theme (built-in or custom) to a new custom theme
- **Editar CSS**: opens CSS editor (only for custom themes)
- **Renombrar**: renames a custom theme
- **Eliminar**: removes a custom theme (protected if currently active)

## Spell-check system

### Inline language markers

`{lang=xx}` markers switch the spell-check language mid-document:

```markdown
{lang=en}Hello{lang=es}Mundo
```

When no marker is present, the project's default `spell_lang` is used.

### Exclusion zones

- Fenced code blocks (``` `` ` `` ```) — entire block is excluded from checking and marker parsing.
- Inline code (`` ` ``) — backtick-delimited spans are excluded.

### Dictionary sources

| Source | Scope | Persistence |
|--------|-------|-------------|
| System dictionary | Global | OS enchant/aspell dictionaries |
| Global user words | Per-user | `GtkSpell.Checker.add_to_dictionary()` |
| Project words | Per-project | `project.spell_words` in `project.yaml` |
| Session words | Current session | In-memory set |

## EPUB generation pipeline

```
EpubService.generate()
  │
  ├── 1. Create EpubBook
  │
  ├── 2. Set metadata (title, author, language, etc.)
  │
  ├── 3. Load & create stylesheet
  │
  ├── 4. Create component chapters
  │   ├── Parse frontmatter
  │   ├── Auto-number (if enabled)
  │   ├── Split title (subtitle on ` - `)
  │   ├── Build header HTML
  │   ├── Render Markdown → HTML (with code highlighting)
  │   ├── Apply drop cap
  │   └── Attach CSS
  │
  ├── 5. Create part chapters
  │
  ├── 6. Generate TOC (heading hierarchy, toc_deep)
  │
  ├── 7. Build navigation (NCX for epub2, Nav for epub3)
  │
  └── 8. Write EPUB
```

## Extension points

- **Themes**: Add a new directory under `mdtoepub/themes/` with `theme.yaml` and CSS files (built-in). Users can also create custom themes via the theme manager UI, stored in `~/.config/mdtoepub/themes/`.
- **CSS classes**: Document utility classes with `/* @doc */` comments for automatic help panel inclusion.
- **Component types**: Extend `ComponentType` enum and add corresponding CSS and labels.
- **Markdown extensions**: Add extensions to `MarkdownService.extensions`.

## Testing

Tests are in `tests/` and use pytest:

```bash
pytest
```

Test coverage includes models, services, and specific edge cases for EPUB generation, CSS parsing, spell-check, and file operations.

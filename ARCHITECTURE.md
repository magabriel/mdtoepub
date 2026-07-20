# Architecture

## Overview

MDToEPUB is a GTK3 desktop application with a modular architecture. The UI is split across view classes in `views/`, dialog functions in `views/dialogs/`, and controllers in `controllers/`. The `MDToEPUBApp` class in `main.py` (~100 lines) serves as a thin coordinator that wires everything together, holds shared state, and delegates to subordinate modules.

```
┌──────────────────────────────────────────────────────────┐
│                       main.py                            │
│  MDToEPUBApp (Gtk.Application) — thin coordinator        │
│    ├── Shared state (project, current_component, ...)    │
│    ├── do_activate: wiring and build order               │
│    └── Shared utils (_update_status, _get_config_path)   │
├──────────────────────────────────────────────────────────┤
│                       views/                             │
│  main_window.py   Menubar, toolbar, statusbar, paned     │
│  editor_view.py   GtkSource editor + WebKit2 preview     │
│  styles_panel.py  CSS cascade hierarchy panel            │
│  project_tree.py  Tree navigator + component CRUD        │
│  dialogs/                                                │
│    project_config.py  Project settings dialog            │
│    theme_manager.py   Theme lifecycle manager            │
│    image_manager.py   Image import & categorization      │
├──────────────────────────────────────────────────────────┤
│                    controllers/                          │
│  project_manager.py  Component save/load, labels         │
│  export_import.py    EPUB export, Markdown/EPUB import   │
├──────────────────────────────────────────────────────────┤
│                       utils/                             │
│  dialogs.py   show_error / show_info / confirm helpers   │
├──────────────────────────────────────────────────────────┤
│                      services/                           │
│  MarkdownService   EpubService   HeaderBuilder            │
│  TocBuilder        FootnotesProcessor                     │
│  FigureTableProcessor  StyleManager                      │
│  FootnoteProcessor CaptionProcessor                      │
│  VariableInterpolator                                    │
│  ProjectService    ComponentService  ImportService        │
│  FileService (facade)                                    │
│  YamlService       ImageService    SpellCheckService      │
│  StyleDocService   ThemeService    LabelsService          │
├──────────────────────────────────────────────────────────┤
│                      models/                             │
│  Project    Component    ComponentType    Theme          │
└──────────────────────────────────────────────────────────┘
```

## Directory layout

```
mdtoepub/
├── main.py                          # Entry point, thin app coordinator
├── utils/
│   └── dialogs.py                   # show_error / show_info / confirm
├── views/
│   ├── main_window.py               # Menubar, toolbar, statusbar, paned layout
│   ├── editor_view.py               # GtkSource editor + WebKit2 preview
│   ├── styles_panel.py              # CSS 4-level cascade panel
│   ├── project_tree.py              # Project navigator tree + component CRUD
│   └── dialogs/
│       ├── project_config.py        # Project configuration dialog
│       ├── theme_manager.py         # Theme lifecycle manager
│       └── image_manager.py         # Image import & categorization
├── controllers/
│   ├── project_manager.py           # Component save/load, label resolution
│   └── export_import.py             # EPUB export/import operations
├── models/
│   ├── component.py             # Component dataclass, ComponentType enum
│   ├── project.py               # Project dataclass (aggregate root)
│   └── theme.py                 # Theme dataclass
├── services/
│   ├── markdown_service.py      # Markdown → HTML rendering
│   ├── epub_service.py          # EPUB generation pipeline (orchestrator)
│   ├── header_builder.py        # Component/part header building with auto-numbering
│   ├── toc_builder.py           # TOC HTML + reader navigation generation
│   ├── footnotes_processor.py   # Footnotes extraction + chapter building
│   ├── footnote_processor.py    # Footnote renumbering + counting
│   ├── caption_processor.py     # Figure/table caption generation
│   ├── variable_interpolator.py # {{key}} placeholder replacement
│   ├── figure_table_processor.py # Figure/table scanning + LOF/LOT generation
│   ├── style_manager.py         # CSS loading + style item management
│   ├── project_service.py       # Project creation, loading, saving
│   ├── component_service.py     # Component file I/O + filename generation
│   ├── import_service.py        # Markdown/EPUB import
│   ├── file_service.py          # Facade for Project/Component/ImportService
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

`services/markdown_service.py:1`

Converts Markdown to HTML using Python-Markdown with extensions:
- `tables`, `fenced_code`, `codehilite`, `toc`, `meta`, `attr_list`

Key methods:
- `render(text, component_type, component_id)` — full rendering pipeline.
- `to_roman(num)` — static, convert integer to Roman numerals.
- `to_word(num, language)` — static, convert integer to ordinal word.
- `get_code_css()` — static, returns Pygments CSS for code highlighting.

Delegates to:
- `FootnoteProcessor` — footnote renumbering and counting.
- `CaptionProcessor` — figure/table caption generation.
- `VariableInterpolator` — `{{key}}` placeholder replacement.

### FootnoteProcessor

`services/footnote_processor.py:1`

Handles footnote renumbering, counting, and display fixing.

```
FootnoteProcessor
  ├── count_footnote_refs(text) — count unique footnote refs with definitions
  ├── renumber_footnotes(text, start_number) — renumber footnotes sequentially
  └── fix_footnote_display_numbers(html) — fix display numbers in rendered HTML
```

### CaptionProcessor

`services/caption_processor.py:1`

Handles figure and table caption generation in HTML.

```
CaptionProcessor
  ├── add_image_captions(html, ...) — wrap <img> in <figure>/<figcaption>
  ├── add_table_captions(html, ...) — wrap tables in <figure>/<figcaption>
  ├── extract_figure_alts(md_text) — extract alt text from markdown images
  └── extract_table_captions(md_text) — extract <!-- Table: --> captions
```

### VariableInterpolator

`services/variable_interpolator.py:1`

Replaces `{{key}}` and `{{key:format}}` placeholders with values.

```
VariableInterpolator
  └── interpolate(text, variables) — replace placeholders with values
```

### HeaderBuilder

`services/header_builder.py:1`

Builds component and part headers with auto-numbering support. Extracted from EpubService to follow the single responsibility principle.

```
HeaderBuilder(project, labels)
  ├── get_component_header(component, chapter_number)
  │     Returns (number_part, title_part, display_title) for chapters/appendices
  ├── get_part_header(component, part_number)
  │     Returns (number_part, title_part, display_title) for parts
  ├── build_header_html(number_part, subtitle_part, title_part)
  │     Builds <h1 class="component-header"> HTML
  └── split_title(title, frontmatter)
        Static. Splits title into (subtitle, title) on ` - `
```

Key implementation details:
- Title auto-splitting: `re.split(r' +[—–-]+ +', title, maxsplit=1)` produces `(subtitle, title)`.
- Chapter numbering: counted sequentially through CHAPTER-type components.
- Supports multiple numbering styles: arabic, roman, word (ordinal).

### EpubService

`services/epub_service.py:1`

Orchestrates the EPUB generation pipeline using `ebooklib`. Delegates specific responsibilities to specialized classes.

```
EpubService.generate(output_path, epub_version)
  ├── resolve_labels() — creates HeaderBuilder, TocBuilder, FootnotesProcessor, FigureTableProcessor, StyleManager
  ├── _create_book() + _build_variables()
  ├── StyleManager.create_style_items(book)
  ├── StyleManager.create_css_override_items(book)
  ├── _prescan_footnote_numbers()
  ├── FigureTableProcessor.prescan_figures()
  ├── FigureTableProcessor.prescan_tables()
  ├── _create_part_chapters(book, style_items)
  │     └── HeaderBuilder.get_part_header → build header HTML
  ├── _create_component_chapters(book, ...)
  │     └── _create_chapter(component, ...) — dispatcher
  │           ├── _create_cover_image_chapter()  (cover with single image)
  │           ├── _generate_toc_component_html() → TocBuilder
  │           ├── _generate_lof_component_html() → FigureTableProcessor
  │           ├── _generate_lot_component_html() → FigureTableProcessor
  │           └── _generate_standard_chapter_html() → HeaderBuilder
  ├── _create_footnotes_chapter_if_needed() → FootnotesProcessor
  ├── _build_ordered_chapters(chapter_map, part_chapters)
  ├── TocBuilder.build_reader_toc(book, chapter_map, part_chapters)
  ├── _build_spine(book, ordered_chapters, epub_version)
  └── _write_epub(book, output_path)
```

Public methods:
- `generate(output_path, epub_version, global_config)` — full EPUB generation pipeline.
- `resolve_labels(global_config)` — resolve labels and create all helper instances.
- `is_cover_only_image(md_content)` — static, check if content is a single image.
- `extract_cover_image(md_content)` — static, extract alt/src from image markdown.
- `apply_drop_cap(html)` — wrap first alphanumeric chars in `<span class="drop-cap">`.
- `embed_images(book, html_content, comp_id, embedded)` — embed local images into EPUB.

Key implementation details:
- Drop cap: replaces the first alphanumeric character(s) with `<span class="drop-cap">`.
- Images: embedded by scanning HTML for `<img src="...">`, skipping URLs.
- Delegates to: `HeaderBuilder`, `TocBuilder`, `FootnotesProcessor`, `FigureTableProcessor`, `StyleManager`.

### TocBuilder

`services/toc_builder.py:1`

Generates TOC structures: in-book HTML and reader navigation.

```
TocBuilder(project, labels, header_builder)
  ├── generate_toc_html(toc_include, toc_deep) — in-book TOC HTML
  ├── build_reader_toc(book, chapter_map, part_chapters, toc_filter) — EPUB navigation
  ├── get_toc_include_filter() — read toc_include from TOC component frontmatter
  ├── toc_class_for_type(comp_type) — CSS class for TOC entries
  ├── normalize_toc_deep(value, default) — static, clamp toc_deep to [1, 6]
  ├── slugify(text) — static, match markdown's toc extension slugify
  ├── parse_headings_from_md(md_text, max_depth) — parse headings from markdown
  └── get_heading_toc_entries(comp, toc_deep) — TOC lines for sub-headings
```

### FootnotesProcessor

`services/footnotes_processor.py:1`

Extracts, collects, and renders footnotes for EPUB generation.

```
FootnotesProcessor(project, labels, header_builder, markdown_service)
  ├── get_footnotes_component() — find the FOOTNOTES component
  ├── strip_footnotes_from_html(html, component) — extract footnotes from rendered HTML
  └── build_footnotes_chapter(component, collected, style_items, variables)
        — build the footnotes chapter with user content + collected footnotes
```

Key implementation details:
- Regex-based extraction of footnote divs and list items.
- Namespaces footnote IDs to avoid collisions across chapters.
- Rewrites backlinks and references for cross-chapter navigation.

### FigureTableProcessor

`services/figure_table_processor.py:1`

Scans components for figures/tables and generates LOF/LOT HTML.

```
FigureTableProcessor(project, labels)
  ├── prescan_figures() — scan figure info + numbering
  ├── prescan_tables() — scan table info + numbering
  ├── generate_lof_html(figure_info) — List of Figures HTML
  └── generate_lot_html(table_info) — List of Tables HTML
```

### StyleManager

`services/style_manager.py:1`

Manages CSS loading, theme stylesheets, and style item creation.

```
StyleManager(project)
  ├── load_stylesheet() — combine all CSS layers (theme + book + Pygments)
  ├── create_css_item(uid, filename, css_text) — static, create CSS EpubItem
  ├── create_style_items(book) — create main stylesheet item
  ├── create_css_override_items(book) — create type-level + component-level CSS items
  └── build_chapter_styles(style_items, type_css_items, comp_css_items, component)
        — static, combine base + type + component style items
```

### FileService (facade)

`services/file_service.py:1`

Thin facade that re-exports from `ProjectService`, `ComponentService`, and `ImportService` for backward compatibility. New code should import from the specific service classes directly.

### ProjectService

`services/project_service.py:1`

Manages project creation, loading, and saving.

- `create_project_structure(path, name)` — creates directory tree with default config.
- `load_project(path)` — reads `project.yaml`, loads CSS from `styles/`.
- `save_project(project)` — writes CSS to files, saves `project.yaml`.

Project data is split across files:
- `project.yaml` — metadata and component list.
- `styles/book.css` — `project.custom_css`
- `styles/types/<type>.css` — `project.type_css_overrides`
- `styles/components/<id>.css` — `component.custom_css`

### ComponentService

`services/component_service.py:1`

Manages component file I/O and filename generation.

- `save_component(project_path, component, content)` — save markdown to file.
- `load_component(project_path, component)` — load markdown from file.
- `generate_filename(component_type, title)` — generate slug-based filename.
- `rename_image_references(project_path, old_path, new_path, project)` — update image paths in components.

### ImportService

`services/import_service.py:1`

Handles importing Markdown and EPUB files into a project.

- `parse_imported_markdown(content)` — split a book into components by H1/H2 headings.
- `import_book(project_path, project, content, source_md_path)` — import parsed components.
- `parse_imported_epub(epub_path)` — parse EPUB into components and images.
- `import_epub(project_path, project, epub_path)` — import EPUB into project.
- `html_to_markdown(html_content)` — convert basic HTML to markdown.

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
│ [Tema]            │   │   ├── Editor                 │
│ [Ayuda]           │   │   └── Preview                │
│                   │   ├── Tema (Notebook)            │
│                   │   │   ├── Tipo de componente     │
│                   │   │   └── Global                 │
│                   │   └── Ayuda (direct)             │
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
  ├── 1. Resolve labels → creates all helper instances
  │
  ├── 2. Create EpubBook + metadata
  │
  ├── 3. StyleManager: load stylesheet + CSS overrides
  │
  ├── 4. Pre-scan numbering (_prescan_footnote_numbers)
  │     FigureTableProcessor: prescan_figures, prescan_tables
  │
  ├── 5. Create part chapters
  │     └── HeaderBuilder.get_part_header → build header HTML
  │
  ├── 6. Create component chapters
  │     └── _create_chapter (dispatcher)
  │           ├── _create_cover_image_chapter (cover with single image)
  │           ├── TocBuilder.generate_toc_html (TOC)
  │           ├── FigureTableProcessor.generate_lof_html (List of Figures)
  │           ├── FigureTableProcessor.generate_lot_html (List of Tables)
  │           └── _generate_standard_chapter_html → HeaderBuilder
  │
  ├── 7. FootnotesProcessor.build_footnotes_chapter (if FOOTNOTES component)
  │
  ├── 8. TocBuilder.build_reader_toc (EPUB navigation)
  │
  ├── 9. Build spine + navigation
  │
  └── 10. Write EPUB
```

## Extension points

- **Themes**: Add a new directory under `mdtoepub/themes/` with `theme.yaml` and CSS files (built-in). Users can also create custom themes via the theme manager UI, stored in `~/.config/mdtoepub/themes/`.
- **CSS classes**: Document utility classes with `/* @doc */` comments for automatic help panel inclusion.
- **Component types**: Extend `ComponentType` enum and add corresponding CSS and labels.
- **Markdown extensions**: Add extensions to `MarkdownService.extensions`.

## Coding conventions

These rules are derived from the refactoring of `main.py` from a 4905-line monolith into a modular architecture.
All new code must follow them.

### 1. Thin coordinator — `main.py`

`MDToEPUBApp` must be minimal. Only these are allowed:

| What | Example |
|------|---------|
| `__init__` | Initialize shared state and services |
| `do_activate` | Create all objects, wire them, call `build()` |
| Shared state (`self.project`, `self.current_component`, ...) | No business logic, just data holders |
| Shared utilities (`_update_status`, `_get_config_path`) | One-liners that don't fit elsewhere |

Never add dialog creation, widget building, or business logic to `main.py`.

### 2. View classes — `views/`

Each GTK widget tree goes in its own file. Conventions:
- Constructor takes `app` and stores as `self.app`
- Public method `build(parent)` or `build()` creates widgets, returns the root widget
- Widget references needed by other modules are stored on `self.app` (e.g. `self.app.text_view`)
- Signals connect to local methods, which access shared state via `self.app.xxx`

```python
class EditorView:
    def __init__(self, app):
        self.app = app

    def build(self, right_box):
        self.app.text_view = GtkSource.View(...)
        self.app.text_view.connect("populate-popup", self._on_popup)
        ...

    def _on_popup(self, textview, popup):
        if self.app.project:  # shared state
            ...
```

### 3. Controllers — `controllers/`

Business logic shared across views. Conventions:
- Constructor takes `app` and stores as `self.app`
- Public methods named as actions: `export_epub()`, `save_component_content()`
- Access shared state via `self.app.xxx`
- Never create GTK widgets directly — delegate to views or dialogs

```python
class ExportImportController:
    def __init__(self, app):
        self.app = app

    def export_epub(self, button):
        if not self.app.project:
            return
        ...
```

### 4. Dialog functions — `views/dialogs/`

Standalone functions, not classes. Conventions:
- Take `app` as first parameter
- Create and show a modal `Gtk.Dialog`
- Are self-contained (all widget creation inline)
- Call `show_info`, `show_error`, `confirm` from `utils/dialogs.py`
- Return nothing (side-effect only) or return a result

```python
def show_theme_manager(app):
    dialog = Gtk.Dialog(transient_for=app.window, ...)
    ...
    dialog.show_all()
```

### 5. Utilities — `utils/`

Pure functions with no `app` dependency. Conventions:
- Module-level functions, never classes
- Take explicit parameters (e.g. `parent_window`, not `app`)
- Imported with `from ..utils.dialogs import show_error`

```python
def show_error(parent, message):
    dialog = Gtk.MessageDialog(transient_for=parent, ...)
    ...
```

### 6. No delegation wrappers

Never add wrapper methods on `MDToEPUBApp` that just forward to a delegate:

```python
# ❌ Wrong — wrapper on app
def _update_preview(self):
    self.editor_view._update_preview()

# ✅ Right — caller uses delegate directly
self.app.editor_view._update_preview()
```

Callers must reference the delegate object directly. The only exception is methods called from GTK signal connections in `MainWindow._setup_menubar()`, which may use `self._on_xxx` directly on MainWindow.

### 7. GTK signal connections

Menu items and toolbar buttons connect to methods on the owning class, not on `app`:

```python
# ❌ Wrong
item.connect("activate", self.app._on_new_project)

# ✅ Right
item.connect("activate", self._on_new_project)
```

If the handler belongs to another class (e.g. `project_tree_view`), connect directly:

```python
item.connect("activate", self.app.project_tree_view._on_add_component)
```

### 8. Object creation order in `do_activate`

All delegate objects must be instantiated BEFORE `MainWindow.build()`, because the menubar and toolbar reference them:

```python
# 1. Create all delegates first
self.project_manager = ProjectManager(self)
self.project_tree_view = ProjectTree(self)
self._styles_panel = StylesPanel(self)
self.editor_view = EditorView(self)
self.export_import_ctrl = ExportImportController(self)

# 2. Build UI (menubar references delegates via self.app.xxx)
self.main_window = MainWindow(self)
left_box, right_box = self.main_window.build(main_box)

# 3. Fill panes
self._styles_scrolled = self._styles_panel.build()
self.editor_view.build(right_box)
self.project_tree_view.build(left_box)
```

## Testing

Tests are in `tests/` and use pytest:

```bash
pytest
```

Test coverage includes models, services, and specific edge cases for EPUB generation, CSS parsing, spell-check, and file operations.

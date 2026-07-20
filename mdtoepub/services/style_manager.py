from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ebooklib import epub

from ..models.project import Project
from ..models.component import Component
from .theme_service import ThemeService
from .markdown_service import MarkdownService


class StyleManager:
    """Manages CSS loading, theme stylesheets, and style item creation for EPUB generation."""

    def __init__(self, project: Project):
        """Initialize with a project.

        Args:
            project: The project containing theme and CSS configuration.
        """
        self.project = project

    def load_stylesheet(self) -> Optional[str]:
        """Load and combine all CSS layers for the project theme.

        Combines theme base CSS, theme per-type CSS, book-level custom CSS,
        and Pygments code syntax CSS.

        Returns:
            Combined CSS text, or None if no CSS found.
        """
        theme_path = ThemeService.get_theme_path(self.project.theme_id)
        if not theme_path:
            return None

        theme_dir = Path(theme_path)

        theme_yaml_path = theme_dir / "theme.yaml"
        theme_config = {}
        if theme_yaml_path.exists():
            import yaml
            with open(theme_yaml_path) as f:
                theme_config = yaml.safe_load(f) or {}

        css_parts = []

        # Level 1: Theme base
        style_path = theme_dir / "style.css"
        if style_path.exists():
            css_parts.append(style_path.read_text(encoding="utf-8"))

        # Level 1: Theme component CSS
        for css_file in theme_config.get("styles", {}).values():
            comp_style_path = theme_dir / css_file
            if comp_style_path.exists():
                css_parts.append(comp_style_path.read_text(encoding="utf-8"))

        # Level 2: Book-level custom CSS
        if self.project.custom_css:
            css_parts.append(self.project.custom_css)

        # Level 3: Pygments code syntax CSS
        css_parts.append(MarkdownService.get_code_css())

        return "\n".join(css_parts) if css_parts else None

    @staticmethod
    def create_css_item(uid: str, filename: str, css_text: str) -> epub.EpubItem:
        """Create a CSS EpubItem.

        Args:
            uid: Unique identifier for the item.
            filename: Path within the EPUB archive.
            css_text: CSS content string.

        Returns:
            An EpubItem containing the CSS.
        """
        return epub.EpubItem(
            uid=uid,
            file_name=filename,
            media_type="text/css",
            content=css_text.encode("utf-8"),
        )

    def create_style_items(self, book: epub.EpubBook) -> List[epub.EpubItem]:
        """Load stylesheet and create the main CSS item.

        Args:
            book: The EPUB book to add the style item to.

        Returns:
            List containing the style item (or empty if no stylesheet).
        """
        stylesheet = self.load_stylesheet()
        style_items = []
        if stylesheet:
            style_item = self.create_css_item("style", "style/default.css", stylesheet)
            book.add_item(style_item)
            style_items.append(style_item)
        return style_items

    def create_css_override_items(
        self, book: epub.EpubBook
    ) -> Tuple[Dict[str, epub.EpubItem], Dict[str, epub.EpubItem]]:
        """Create CSS items for type-level and component-level overrides.

        Args:
            book: The EPUB book to add items to.

        Returns:
            Tuple of (type_css_items, comp_css_items) dictionaries.
        """
        type_css_items: Dict[str, epub.EpubItem] = {}
        for type_name, css in self.project.type_css_overrides.items():
            if css.strip():
                item = self.create_css_item(
                    f"type_{type_name}",
                    f"style/type_{type_name}.css",
                    css,
                )
                book.add_item(item)
                type_css_items[type_name] = item

        comp_css_items: Dict[str, epub.EpubItem] = {}
        for component in self.project.components:
            if component.custom_css.strip():
                item = self.create_css_item(
                    f"comp_{component.id}",
                    f"style/comp_{component.id}.css",
                    component.custom_css,
                )
                book.add_item(item)
                comp_css_items[component.id] = item

        return type_css_items, comp_css_items

    @staticmethod
    def build_chapter_styles(
        style_items: List[epub.EpubItem],
        type_css_items: Dict[str, epub.EpubItem],
        comp_css_items: Dict[str, epub.EpubItem],
        component: Component,
    ) -> List[epub.EpubItem]:
        """Combine base, type-level, and component-level style items.

        Args:
            style_items: Base CSS style items.
            type_css_items: Per-type CSS items.
            comp_css_items: Per-component CSS items.
            component: The component to get styles for.

        Returns:
            Combined list of style items.
        """
        styles = list(style_items)
        type_item = type_css_items.get(component.type.value)
        if type_item:
            styles.append(type_item)
        comp_item = comp_css_items.get(component.id)
        if comp_item:
            styles.append(comp_item)
        return styles

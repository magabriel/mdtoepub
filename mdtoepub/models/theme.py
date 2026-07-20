from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Theme:
    """Represents a visual theme for EPUB styling.

    Themes can be built-in (read-only) or custom (user-created).
    """

    id: str = ""
    name: str = ""
    description: str = ""
    is_builtin: bool = True
    source_theme_id: Optional[str] = None
    author: str = ""
    version: str = "1.0"
    base_style: str = "style.css"
    styles: Dict[str, str] = field(default_factory=dict)
    path: Optional[str] = None

    def get_style_for_component(self, component_type: str) -> str:
        """Get the CSS filename for a given component type.

        Falls back to the base style if no type-specific style is defined.

        Args:
            component_type: Component type value (e.g. "chapter").

        Returns:
            CSS filename string.
        """
        return self.styles.get(component_type, self.base_style)

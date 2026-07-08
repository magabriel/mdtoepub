from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Theme:
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
        return self.styles.get(component_type, self.base_style)

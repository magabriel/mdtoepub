from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from .component import Component, ComponentType


@dataclass
class Project:
    name: str = ""
    title: str = ""
    author: str = ""
    language: str = "es"
    theme_id: str = "classic"
    epub_version: str = "epub3"
    auto_chapter_title: str = "none"
    components: List[Component] = field(default_factory=list)
    global_config: Dict[str, Any] = field(default_factory=dict)
    custom_css: str = ""
    type_css_overrides: Dict[str, str] = field(default_factory=dict)
    drop_cap_enabled: bool = True
    drop_cap_types: List[str] = field(default_factory=lambda: ["chapter"])
    path: str = ""
    export_filename: str = ""
    spell_lang: str = "es_ES"
    spell_words: List[str] = field(default_factory=list)
    edicion: str = ""
    fecha_publicacion: str = ""
    isbn: str = ""
    editorial: str = ""

    def add_component(self, component: Component) -> None:
        component.order = len(self.components)
        self.components.append(component)

    def remove_component(self, component_id: str) -> None:
        self.components = [c for c in self.components if c.id != component_id]

    def get_component(self, component_id: str) -> Optional[Component]:
        for component in self.components:
            if component.id == component_id:
                return component
        return None

    def get_ordered_components(self) -> List[Component]:
        return sorted(self.components, key=lambda c: c.order)

    def get_parent_part(self, component: Component) -> Optional[Component]:
        if not component.part_id:
            return None
        for c in self.components:
            if c.id == component.part_id and c.type == ComponentType.PART:
                return c
        return None

    def get_part(self, part_id: str) -> Optional[Component]:
        for c in self.components:
            if c.id == part_id and c.type == ComponentType.PART:
                return c
        return None

    def get_parts(self) -> List[Component]:
        return sorted(
            [c for c in self.components if c.type == ComponentType.PART],
            key=lambda c: c.order,
        )

    def get_part_children(self, part_id: str) -> List[Component]:
        return sorted(
            [c for c in self.components if c.part_id == part_id],
            key=lambda c: c.order,
        )




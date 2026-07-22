from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from .component import Component, ComponentType


@dataclass
class Project:
    """Aggregate root representing a book project.

    Holds all book-level configuration and owns the component list.
    """

    name: str = ""
    title: str = ""
    author: str = ""
    language: str = "en"
    theme_id: str = "classic"
    epub_version: str = "epub3"
    auto_chapter_title: str = "none"
    chapter_numbering_style: str = "arabic"
    auto_appendix_title: str = "none"
    appendix_numbering_style: str = "arabic"
    components: List[Component] = field(default_factory=list)
    global_config: Dict[str, Any] = field(default_factory=dict)
    custom_css: str = ""
    type_css_overrides: Dict[str, str] = field(default_factory=dict)
    drop_cap_enabled: bool = True
    drop_cap_types: List[str] = field(default_factory=lambda: ["chapter"])
    path: str = ""
    export_filename: str = ""
    spell_lang: str = "en_US"
    spell_words: List[str] = field(default_factory=list)
    edition: str = ""
    publication_date: str = ""
    isbn: str = ""
    publisher: str = ""
    subtitle: str = ""
    auto_part_title: str = "none"
    part_numbering_style: str = "arabic"
    figure_numbering: bool = False
    figure_numbering_style: str = "arabic"
    table_numbering: bool = False
    table_numbering_style: str = "arabic"
    labels: Dict[str, str] = field(default_factory=dict)

    def add_component(self, component: Component) -> None:
        """Add a component to the project with auto-assigned order.

        Args:
            component: Component to add.
        """
        component.order = len(self.components)
        self.components.append(component)

    def remove_component(self, component_id: str) -> None:
        """Remove a component by its ID.

        Args:
            component_id: UUID of the component to remove.
        """
        self.components = [c for c in self.components if c.id != component_id]

    def get_component(self, component_id: str) -> Optional[Component]:
        """Find a component by its ID.

        Args:
            component_id: UUID to search for.

        Returns:
            Component if found, None otherwise.
        """
        for component in self.components:
            if component.id == component_id:
                return component
        return None

    def get_ordered_components(self) -> List[Component]:
        """Return all components sorted by their order field.

        Returns:
            Sorted list of components.
        """
        return sorted(self.components, key=lambda c: c.order)

    def get_parent_part(self, component: Component) -> Optional[Component]:
        """Get the parent PART component for a given component.

        Args:
            component: Component whose parent to find.

        Returns:
            Parent PART component, or None if not in a part.
        """
        if not component.part_id:
            return None
        for c in self.components:
            if c.id == component.part_id and c.type == ComponentType.PART:
                return c
        return None

    def get_part(self, part_id: str) -> Optional[Component]:
        """Get a PART component by its ID.

        Args:
            part_id: UUID of the part.

        Returns:
            PART component if found, None otherwise.
        """
        for c in self.components:
            if c.id == part_id and c.type == ComponentType.PART:
                return c
        return None

    def get_parts(self) -> List[Component]:
        """Return all PART components sorted by order.

        Returns:
            Sorted list of PART components.
        """
        return sorted(
            [c for c in self.components if c.type == ComponentType.PART],
            key=lambda c: c.order,
        )

    def get_part_children(self, part_id: str) -> List[Component]:
        """Return all components belonging to a part, sorted by order.

        Args:
            part_id: UUID of the parent part.

        Returns:
            Sorted list of child components.
        """
        return sorted(
            [c for c in self.components if c.part_id == part_id],
            key=lambda c: c.order,
        )

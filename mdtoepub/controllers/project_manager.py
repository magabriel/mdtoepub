import re
from ..models.component import Component
from ..services.file_service import FileService
from ..services.yaml_service import YamlService
from ..services.labels_service import resolve_labels


class ProjectManager:
    """Manages component content save/load and label resolution."""

    def __init__(self, app):
        self.app = app

    def resolve_labels(self) -> dict:
        """Resolve component labels for the current project language.

        Returns:
            Dict of label key to localized label string.
        """
        if self.app.project:
            return resolve_labels(self.app.project.language)
        return resolve_labels("es")

    def save_component_content(self) -> bool:
        """Save the current editor content to the active component's file.

        Updates the component title if an H1 heading is found.

        Returns:
            True if the title was updated, False otherwise.
        """
        if self.app.read_only:
            return False
        text = self.app.editor_view.get_editor_text()
        frontmatter, markdown_content = YamlService.parse_frontmatter(text)

        component = self.app.current_part or self.app.current_component
        if component is None or component not in self.app.project.components:
            return False

        component.frontmatter = frontmatter
        FileService.save_component(self.app.project.path, component, text)

        h1_match = re.search(r'^#\s+(.+)$', markdown_content, re.MULTILINE)
        new_title = h1_match.group(1).strip() if h1_match else ""
        if new_title and new_title != component.title:
            component.title = new_title
            FileService.save_project(self.app.project)
            return True

        return False

    def load_component_content(self, component: Component) -> str:
        """Load component content, prepending frontmatter if present.

        Args:
            component: Component to load.

        Returns:
            Markdown content string with frontmatter.
        """
        content = FileService.load_component(self.app.project.path, component)
        if component.frontmatter and not content.startswith("---"):
            content = YamlService.join_content(component.frontmatter, content)
        return content

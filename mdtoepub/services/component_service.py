import re
from pathlib import Path
from typing import Optional

from ..models.component import Component


class ComponentService:
    """Manages component file I/O and filename generation."""

    @staticmethod
    def save_component(project_path: str, component: Component, content: str) -> bool:
        """Save component content to its markdown file.

        Args:
            project_path: Root path of the project.
            component: Component to save.
            content: Markdown content to write.

        Returns:
            True on success, False on error.
        """
        try:
            components_dir = Path(project_path) / "components"
            components_dir.mkdir(exist_ok=True)

            file_path = components_dir / component.filename
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception:
            return False

    @staticmethod
    def load_component(project_path: str, component: Component) -> str:
        """Load component content from its markdown file.

        Args:
            project_path: Root path of the project.
            component: Component to load.

        Returns:
            Markdown content string, or empty string if file doesn't exist.
        """
        file_path = Path(project_path) / "components" / component.filename
        if not file_path.exists():
            return ""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def generate_filename(component_type: str, title: str) -> str:
        """Generate a filename for a component based on its type and title.

        Uses a slugified title if available, otherwise generates a UUID-based name.

        Args:
            component_type: Component type value (e.g. "chapter").
            title: Component title.

        Returns:
            Filename string ending in .md.
        """
        import uuid

        if title:
            slug = title.lower()
            slug = re.sub(r"[^\w\s-]", "", slug)
            slug = re.sub(r"[-\s]+", "_", slug)
            slug = slug.strip("_")
            if slug:
                return f"{slug}.md"

        short_id = uuid.uuid4().hex[:8]
        return f"{component_type}_{short_id}.md"

    @staticmethod
    def rename_image_references(project_path: str, old_path: str, new_path: str, project) -> int:
        """Rename image references in all component markdown files.

        Args:
            project_path: Root path of the project.
            old_path: Old project-relative image path (e.g. 'images/illustrations/foto.jpg').
            new_path: New project-relative image path.
            project: Project containing components.

        Returns:
            Number of files modified.
        """
        count = 0
        old_escaped = re.escape(old_path)
        for comp in project.components:
            content = ComponentService.load_component(project_path, comp)
            if not content:
                continue
            new_content, n = re.subn(r'!\[([^\]]*)\]\((' + old_escaped + r')\)',
                                     lambda m: f'![{m.group(1)}]({new_path})',
                                     content)
            if n > 0:
                ComponentService.save_component(project_path, comp, new_content)
                count += 1
        return count

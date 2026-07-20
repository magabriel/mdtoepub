from typing import Tuple, Dict, Any
import yaml
from pathlib import Path


class YamlService:
    """Utility for YAML file I/O and frontmatter parsing."""

    @staticmethod
    def load(file_path: str) -> Dict[str, Any]:
        """Load a YAML file and return its contents as a dict.

        Args:
            file_path: Path to the YAML file.

        Returns:
            Dict with parsed YAML data, or empty dict if file doesn't exist or is empty.
        """
        path = Path(file_path)
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if data else {}

    @staticmethod
    def save(data: Dict[str, Any], file_path: str) -> bool:
        """Save a dict to a YAML file.

        Args:
            data: Data to serialize.
            file_path: Destination file path.

        Returns:
            True on success, False on error.
        """
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
            return True
        except Exception:
            return False

    @staticmethod
    def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from a markdown string.

        Frontmatter is delimited by ``---`` at the start of the content.

        Args:
            content: Markdown text potentially containing frontmatter.

        Returns:
            Tuple of (frontmatter_dict, markdown_content_without_frontmatter).
            Returns ({}, original_content) if no valid frontmatter is found.
        """
        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        frontmatter_yaml = parts[1].strip()
        markdown_content = parts[2].strip()

        try:
            frontmatter = yaml.safe_load(frontmatter_yaml)
            return frontmatter if isinstance(frontmatter, dict) else {}, markdown_content
        except yaml.YAMLError:
            return {}, content

    @staticmethod
    def extract_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
        """Alias for parse_frontmatter.

        Args:
            content: Markdown text potentially containing frontmatter.

        Returns:
            Tuple of (frontmatter_dict, markdown_content).
        """
        return YamlService.parse_frontmatter(content)

    @staticmethod
    def join_content(frontmatter: Dict[str, Any], markdown_content: str) -> str:
        """Join frontmatter dict and markdown content into a single string.

        Args:
            frontmatter: Dict to serialize as YAML frontmatter.
            markdown_content: Markdown text.

        Returns:
            Combined string with frontmatter and markdown.
        """
        if not frontmatter:
            return markdown_content
        import yaml
        fm_yaml = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)
        return f"---\n{fm_yaml}---\n\n{markdown_content}"

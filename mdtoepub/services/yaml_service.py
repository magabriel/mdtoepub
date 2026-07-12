from typing import Tuple, Dict, Any
import yaml
from pathlib import Path


class YamlService:
    @staticmethod
    def load(file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if data else {}

    @staticmethod
    def save(data: Dict[str, Any], file_path: str) -> bool:
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
        return YamlService.parse_frontmatter(content)

    @staticmethod
    def join_content(frontmatter: Dict[str, Any], markdown_content: str) -> str:
        if not frontmatter:
            return markdown_content
        import yaml
        fm_yaml = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)
        return f"---\n{fm_yaml}---\n\n{markdown_content}"

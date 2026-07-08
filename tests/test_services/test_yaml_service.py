import pytest
import tempfile
import os
from mdtoepub.services.yaml_service import YamlService


class TestYamlService:
    def test_parse_frontmatter_with_frontmatter(self):
        content = """---
title: Test Title
author: Test Author
---
# Content here"""
        frontmatter, markdown = YamlService.parse_frontmatter(content)
        assert frontmatter["title"] == "Test Title"
        assert frontmatter["author"] == "Test Author"
        assert markdown == "# Content here"

    def test_parse_frontmatter_without_frontmatter(self):
        content = "# Just markdown content"
        frontmatter, markdown = YamlService.parse_frontmatter(content)
        assert frontmatter == {}
        assert markdown == content

    def test_parse_frontmatter_empty(self):
        content = "---\n---\n# Content"
        frontmatter, markdown = YamlService.parse_frontmatter(content)
        assert markdown == "# Content"

    def test_save_and_load(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            data = {"name": "test", "value": 42}
            result = YamlService.save(data, temp_path)
            assert result is True

            loaded = YamlService.load(temp_path)
            assert loaded["name"] == "test"
            assert loaded["value"] == 42
        finally:
            os.unlink(temp_path)

    def test_load_nonexistent_file(self):
        result = YamlService.load("/nonexistent/file.yaml")
        assert result == {}

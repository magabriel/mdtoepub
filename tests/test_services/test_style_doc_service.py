import pytest
from pathlib import Path
import tempfile
import os

from mdtoepub.services.style_doc_service import StyleDocService
from mdtoepub.models.component import ComponentType


THEMES_DIR = Path(__file__).resolve().parent.parent.parent / "mdtoepub" / "themes" / "classic"
THEME_YAML_PATH = THEMES_DIR / "theme.yaml"


def load_theme_config():
    import yaml
    with open(THEME_YAML_PATH) as f:
        return yaml.safe_load(f) or {}


class TestStyleDocService:
    def setup_method(self):
        self.svc = StyleDocService(str(THEMES_DIR))
        self.theme_config = load_theme_config()

    def test_parse_license_docs(self):
        docs = self.svc.get_docs_for_type(ComponentType.LICENSE, self.theme_config)
        labels = {d["markdown_hint"] for d in docs}
        assert "{.publisher}" in labels, "should find .publisher"
        assert "{.isbn}" in labels, "should find .isbn"
        assert "{.year}" in labels, "should find .year"

    def test_parse_foreword_docs(self):
        docs = self.svc.get_docs_for_type(ComponentType.FOREWORD, self.theme_config)
        labels = {d["markdown_hint"] for d in docs}
        assert "{.author}" in labels
        assert "{.location-date}" in labels

    def test_parse_acknowledgement_docs(self):
        docs = self.svc.get_docs_for_type(ComponentType.ACKNOWLEDGEMENT, self.theme_config)
        labels = {d["markdown_hint"] for d in docs}
        assert "{.dedicatee}" in labels

    def test_parse_title_docs(self):
        docs = self.svc.get_docs_for_type(ComponentType.TITLE, self.theme_config)
        labels = {d["markdown_hint"] for d in docs}
        assert "# h1" in labels or "# h2" in labels or "# h3" in labels

    def test_chapter_type_no_specific_docs(self):
        docs = self.svc.get_docs_for_type(ComponentType.CHAPTER, self.theme_config)
        assert docs == []

    def test_cache_hits(self):
        docs1 = self.svc.get_docs_for_type(ComponentType.LICENSE, self.theme_config)
        docs2 = self.svc.get_docs_for_type(ComponentType.LICENSE, self.theme_config)
        assert len(docs1) == len(docs2)

    def test_invalidate_cache(self):
        self.svc.get_docs("license.css")
        assert "license.css" in self.svc._cache
        self.svc.invalidate_cache()
        assert "license.css" not in self.svc._cache

    def test_unknown_type_no_docs(self):
        docs = self.svc.get_docs_for_type(ComponentType.CHAPTER, {})
        assert docs == []

    def test_parse_css_doc_format(self):
        css = """
/* @doc Nombre del editor — usar {.publisher} en markdown */
.component-license .publisher { color: red; }

/* @doc ISBN del libro — usar {.isbn} en markdown */
.component-license .isbn { color: blue; }
"""
        entries = self.svc._parse(css)
        assert len(entries) == 2
        assert entries[0]["label"] == "publisher"
        assert entries[0]["markdown_hint"] == "{.publisher}"
        assert entries[1]["description"] == "ISBN del libro — usar {.isbn} en markdown"

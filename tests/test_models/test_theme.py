import pytest
from mdtoepub.models.theme import Theme


class TestTheme:
    def test_create_theme_defaults(self):
        theme = Theme()
        assert theme.id == ""
        assert theme.name == ""
        assert theme.description == ""
        assert theme.base_style == "style.css"
        assert theme.styles == {}

    def test_get_style_for_component_specific(self):
        theme = Theme(
            styles={"chapter": "chapter.css", "introduction": "intro.css"}
        )
        assert theme.get_style_for_component("chapter") == "chapter.css"

    def test_get_style_for_component_fallback(self):
        theme = Theme(base_style="base.css")
        assert theme.get_style_for_component("unknown") == "base.css"

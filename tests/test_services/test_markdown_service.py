import pytest
from mdtoepub.services.markdown_service import MarkdownService
from mdtoepub.models.component import ComponentType


class TestMarkdownService:
    def setup_method(self):
        self.service = MarkdownService()

    def test_render_simple_markdown(self):
        result = self.service.render("# Hello World")
        assert "<h1" in result
        assert "Hello World" in result

    def test_render_with_paragraphs(self):
        content = "First paragraph.\n\nSecond paragraph."
        result = self.service.render(content)
        assert "<p>" in result
        assert "First paragraph." in result
        assert "Second paragraph." in result

    def test_render_wraps_in_section(self):
        result = self.service.render("Content", ComponentType.CHAPTER)
        assert '<section class="component-chapter">' in result

    def test_extract_title(self):
        content = "# My Title\n\nSome content"
        title = self.service.extract_title(content)
        assert title == "My Title"

    def test_extract_title_no_title(self):
        content = "Just some content without title"
        title = self.service.extract_title(content)
        assert title is None

    def test_render_bold(self):
        result = self.service.render("**bold text**")
        assert "<strong>" in result

    def test_render_italic(self):
        result = self.service.render("*italic text*")
        assert "<em>" in result

    def test_image_caption_with_alt(self):
        html = '<p><img alt="Mi Foto" src="foto.jpg" /></p>'
        result = MarkdownService._add_image_captions(html)
        assert '<figure>' in result
        assert '<figcaption>Mi Foto</figcaption>' in result
        assert '<img alt="Mi Foto" src="foto.jpg" />' in result
        # figure should be unwrapped from p
        assert not result.startswith('<p><figure>')

    def test_image_caption_multiline(self):
        html = '<p><figure>\n<img alt="Multi" src="x.jpg" />\n<figcaption>Multi</figcaption>\n</figure></p>'
        result = MarkdownService._add_image_captions(html)
        assert '<figure>' in result
        assert not result.startswith('<p>')

    def test_image_caption_empty_alt(self):
        html = '<p><img alt="" src="foto.jpg" /></p>'
        result = MarkdownService._add_image_captions(html)
        assert '<figure>' not in result
        assert '<figcaption>' not in result

    def test_image_caption_no_alt(self):
        html = '<p><img src="foto.jpg" /></p>'
        result = MarkdownService._add_image_captions(html)
        assert '<figure>' not in result
        assert '<figcaption>' not in result

    def test_image_caption_in_markdown_render(self):
        md = "![Descripción](img.png)"
        html = self.service.render(md)
        assert '<figure>' in html
        assert '<figcaption>Descripción</figcaption>' in html

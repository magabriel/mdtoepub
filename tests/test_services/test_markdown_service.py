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

    def test_footnote_renumbering_sequential(self):
        md = "First[^204]. Second[^1].\n\n[^204]: Note A.\n[^1]: Note B."
        html = self.service.render(md)
        assert 'id="fnref:1"' in html
        assert 'id="fnref:2"' in html
        assert 'id="fn:1"' in html
        assert 'id="fn:2"' in html
        assert 'value="1"' in html
        assert 'value="2"' in html
        assert "Note A" in html
        assert "Note B" in html

    def test_footnote_renumbering_within_definition(self):
        md = "Ref[^1].\n\n[^1]: See also [^2].\n\n[^2]: Target."
        html = self.service.render(md)
        assert 'id="fnref:1"' in html
        assert 'id="fnref:2"' in html
        assert "See also" in html
        assert "Target" in html

    def test_footnote_missing_definition_error(self):
        md = "Text[^99].\n\n[^1]: Note."
        html = self.service.render(md)
        assert 'fn-error' in html
        assert 'background:yellow' in html
        assert '[99?]' in html
        assert 'Nota [99] no definida' in html

    def test_footnote_code_block_ignored(self):
        md = "Text[^1].\n\n```\nNot a ref[^2].\n```\n\n[^1]: Note."
        html = self.service.render(md)
        assert 'id="fnref:1"' in html
        assert 'Nota [2] no definida' not in html

    def test_footnote_ordering_preserved(self):
        md = "Third[^3]. First[^1]. Second[^2].\n\n[^3]: C.\n[^1]: A.\n[^2]: B."
        html = self.service.render(md)
        fn_div = html[html.index('<div class="footnote">'):]
        c_pos = fn_div.index("C.")
        a_pos = fn_div.index("A.")
        b_pos = fn_div.index("B.")
        assert c_pos < a_pos < b_pos, "footnotes in text order: C, A, B"

    def test_footnote_no_footnotes(self):
        md = "Just text."
        html = self.service.render(md)
        assert "footnote" not in html
        assert "fn-error" not in html

    def test_count_footnote_refs(self):
        md = "First[^204]. Second[^1].\n\n[^204]: A.\n[^1]: B."
        assert MarkdownService._count_footnote_refs(md) == 2

    def test_count_footnote_refs_empty(self):
        assert MarkdownService._count_footnote_refs("No notes.") == 0

    def test_count_footnote_refs_code_block_ignored(self):
        md = "Ref[^1].\n\n```\n[^2]\n```\n\n[^1]: A.\n[^2]: B.\n"
        assert MarkdownService._count_footnote_refs(md) == 1

    def test_count_footnote_refs_undefined_ignored(self):
        md = "Ref[^99].\n\n[^1]: A.\n"
        assert MarkdownService._count_footnote_refs(md) == 0

    def test_footnote_global_renumbering_offset(self):
        md = "Third[^5]. Fourth[^3].\n\n[^5]: C.\n[^3]: D."
        html = self.service.render(md, start_number=3)
        assert 'id="fnref:3"' in html
        assert 'id="fnref:4"' in html
        assert 'id="fn:3"' in html
        assert 'id="fn:4"' in html
        assert 'value="3"' in html
        assert 'value="4"' in html
        assert "C." in html
        assert "D." in html

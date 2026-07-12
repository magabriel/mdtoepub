import pytest
import tempfile
import os
from pathlib import Path
from mdtoepub.services.file_service import FileService
from mdtoepub.models.project import Project


class TestParseImportedMarkdown:
    def test_no_h1(self):
        result = FileService.parse_imported_markdown("Just a paragraph.\n\nMore text.")
        assert len(result) == 1
        assert result[0][0] == "chapter"
        assert result[0][2] == "Just a paragraph.\n\nMore text."

    def test_single_h1_no_h2(self):
        result = FileService.parse_imported_markdown("# Title\n\nContent.")
        assert len(result) == 1
        assert result[0][0] == "chapter"
        assert result[0][1] == "Title"

    def test_single_h1_with_h2(self):
        content = "# Book\n\nIntro.\n\n## Ch1\n\nBody.\n\n### Sub\n\nDetail.\n\n## Ch2\n\nEnd."
        result = FileService.parse_imported_markdown(content)
        assert len(result) == 3
        assert result[0][0] == "introduction"
        assert result[0][1] == "Book"
        assert result[1][0] == "chapter"
        assert result[1][1] == "Ch1"
        assert "# Ch1" in result[1][2]
        assert "## Sub" in result[1][2]
        assert result[2][0] == "chapter"
        assert result[2][1] == "Ch2"

    def test_multiple_h1(self):
        content = "# One\n\nA.\n\n# Two\n\nB."
        result = FileService.parse_imported_markdown(content)
        assert len(result) == 2
        assert result[0][0] == "chapter"
        assert result[0][1] == "One"
        assert result[1][0] == "chapter"
        assert result[1][1] == "Two"

    def test_content_before_first_h1(self):
        content = "Prologue text.\n\n# Ch1\n\nBody.\n\n# Ch2\n\nEnd."
        result = FileService.parse_imported_markdown(content)
        assert len(result) == 3
        assert result[0][0] == "prologue"
        assert result[0][2] == "Prologue text."
        assert result[1][0] == "chapter"
        assert result[1][1] == "Ch1"
        assert result[2][0] == "chapter"
        assert result[2][1] == "Ch2"

    def test_empty_content(self):
        result = FileService.parse_imported_markdown("")
        assert len(result) == 1
        assert result[0][0] == "chapter"

    def test_bump_headings(self):
        text = "## H2\n\nContent.\n\n### H3\n\nMore."
        bumped = FileService._bump_headings(text, -1)
        assert bumped == "# H2\n\nContent.\n\n## H3\n\nMore."


class TestImportBook:
    def test_import_adds_to_existing(self):
        tmpdir = tempfile.mkdtemp()
        proj = Project(name="test", path=tmpdir)
        FileService.save_project(proj)

        # Import first book
        count1 = FileService.import_book(tmpdir, proj, "# Ch1\n\nA.")
        assert count1 == 1
        assert len(proj.components) == 1
        assert proj.components[0].order == 0

        # Import second book
        count2 = FileService.import_book(tmpdir, proj, "# Ch2\n\nB.")
        assert count2 == 1
        assert len(proj.components) == 2
        assert proj.components[1].order == 1

        import shutil
        shutil.rmtree(tmpdir)

    def test_import_saves_files(self):
        tmpdir = tempfile.mkdtemp()
        proj = Project(name="test", path=tmpdir)
        FileService.save_project(proj)

        count = FileService.import_book(tmpdir, proj, "# Title\n\n## Ch1\n\nBody.")
        assert count == 2

        # Check files exist
        for c in proj.components:
            content = FileService.load_component(tmpdir, c)
            assert content, f"Missing content for {c.filename}"

        import shutil
        shutil.rmtree(tmpdir)


class TestProcessMarkdownImages:
    def test_no_images_unchanged(self):
        md = "# Hello\n\nJust text.\n\nNo images here."
        with tempfile.TemporaryDirectory() as tmp:
            result, imported = FileService._process_markdown_images(md, tmp, tmp)
            assert result == md
            assert imported == []

    def test_skips_url_images(self):
        md = "![alt](https://example.com/img.png)"
        with tempfile.TemporaryDirectory() as tmp:
            result, imported = FileService._process_markdown_images(md, tmp, tmp)
            assert result == md
            assert imported == []

    def test_skips_missing_images(self):
        md = "![alt](missing.png)"
        with tempfile.TemporaryDirectory() as tmp:
            result, imported = FileService._process_markdown_images(md, tmp, tmp)
            assert result == md
            assert imported == []

    def test_imports_relative_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "source"
            src_dir.mkdir()
            img = src_dir / "photo.jpg"
            img.write_bytes(b"fake-jpg-data")

            md = "![Photo](photo.jpg)"
            result, imported = FileService._process_markdown_images(md, str(src_dir), tmp)
            assert "photo.jpg" in result
            assert "images/illustrations/photo.jpg" in result
            assert imported == ["photo.jpg"]
            assert (Path(tmp) / "images" / "illustrations" / "photo.jpg").exists()

    def test_imports_absolute_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "source"
            src_dir.mkdir()
            img = src_dir / "photo.jpg"
            img.write_bytes(b"fake-jpg-data")

            md = f"![Photo]({img})"
            result, imported = FileService._process_markdown_images(md, str(src_dir), tmp)
            assert "images/illustrations/photo.jpg" in result
            assert imported == ["photo.jpg"]

    def test_skips_unsupported_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "source"
            src_dir.mkdir()
            img = src_dir / "image.webp"
            img.write_bytes(b"fake-webp-data")

            md = "![Image](image.webp)"
            result, imported = FileService._process_markdown_images(md, str(src_dir), tmp)
            assert result == md
            assert imported == []

    def test_handles_duplicate_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "source"
            src_dir.mkdir()
            img1 = src_dir / "photo.jpg"
            img1.write_bytes(b"fake-jpg-1")
            img2 = src_dir / "sub" / "photo.jpg"
            img2.parent.mkdir()
            img2.write_bytes(b"fake-jpg-2")

            md = "![A](photo.jpg) ![B](sub/photo.jpg)"
            result, imported = FileService._process_markdown_images(md, str(src_dir), tmp)
            assert "images/illustrations/photo.jpg" in result
            assert "images/illustrations/photo_1.jpg" in result
            assert len(imported) == 2
            assert "photo.jpg" in imported
            assert "photo_1.jpg" in imported

    def test_multiple_images_in_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "source"
            src_dir.mkdir()
            (src_dir / "a.png").write_bytes(b"png-a")
            (src_dir / "b.png").write_bytes(b"png-b")

            md = "# Chapter\n\n![A](a.png) and ![B](b.png)."
            result, imported = FileService._process_markdown_images(md, str(src_dir), tmp)
            assert result == "# Chapter\n\n![A](images/illustrations/a.png) and ![B](images/illustrations/b.png)."
            assert imported == ["a.png", "b.png"]

    def test_image_import_via_import_book(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "source"
            src_dir.mkdir()
            (src_dir / "fig.png").write_bytes(b"png-data")

            md_content = "# Chapter 1\n\n![Fig](fig.png)"
            md_file = src_dir / "book.md"
            md_file.write_text(md_content)

            proj = Project(name="test", path=tmp)
            FileService.save_project(proj)

            count = FileService.import_book(tmp, proj, md_content, str(md_file))
            assert count == 1

            saved = FileService.load_component(tmp, proj.components[0])
            assert "images/illustrations/fig.png" in saved
            assert (Path(tmp) / "images" / "illustrations" / "fig.png").exists()

    def test_rename_image_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            from mdtoepub.models.component import Component, ComponentType
            import uuid
            proj = Project(name="test", path=tmp)
            comp = Component(id=str(uuid.uuid4()), type=ComponentType.CHAPTER,
                             title="Test", filename="test.md", order=0)
            proj.add_component(comp)
            content = "# Test\n\n![Foto](images/illustrations/vieja.jpg)"
            FileService.save_component(tmp, comp, content)
            FileService.save_project(proj)

            count = FileService.rename_image_references(
                tmp, "images/illustrations/vieja.jpg", "images/illustrations/nueva.jpg", proj
            )
            assert count == 1
            saved = FileService.load_component(tmp, comp)
            assert "images/illustrations/nueva.jpg" in saved
            assert "images/illustrations/vieja.jpg" not in saved


class TestParseImportedEpub:
    def test_parse_simple_epub(self):
        """Parse an EPUB with a single chapter."""
        from ebooklib import epub

        with tempfile.TemporaryDirectory() as tmp:
            epub_path = Path(tmp) / "test.epub"

            book = epub.EpubBook()
            book.set_identifier("test-id")
            book.set_title("Test Book")
            book.set_language("en")

            c1 = epub.EpubHtml(
                title="Chapter 1", file_name="chap1.xhtml", lang="en"
            )
            c1.content = (
                "<html><body>"
                "<h1>Chapter 1</h1>"
                "<p>Hello world.</p>"
                "</body></html>"
            )
            book.add_item(c1)
            book.spine = [c1]
            book.toc = []
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            epub.write_epub(str(epub_path), book, {})

            # Re-read directly
            components, images = FileService.parse_imported_epub(str(epub_path))
            assert len(components) >= 1
            titles = [t for _, t, _ in components if t]
            assert any("Chapter 1" in t for t in titles)
            assert len(images) == 0

    def test_parse_epub_with_images(self):
        """Parse an EPUB containing embedded images."""
        from ebooklib import epub

        with tempfile.TemporaryDirectory() as tmp:
            epub_path = Path(tmp) / "test_img.epub"

            book = epub.EpubBook()
            book.set_identifier("test-img")
            book.set_title("Test with Images")
            book.set_language("en")

            c1 = epub.EpubHtml(
                title="Chapter", file_name="chap1.xhtml", lang="en"
            )
            c1.content = (
                "<html><body>"
                "<h1>Images</h1>"
                '<p><img src="img/photo.jpg" alt="Photo"/></p>'
                "</body></html>"
            )
            book.add_item(c1)

            img_data = b"\xff\xd8\xff\xe0\x00\x10JFIF"
            img_item = epub.EpubItem(
                uid="img1",
                file_name="img/photo.jpg",
                media_type="image/jpeg",
                content=img_data,
            )
            book.add_item(img_item)

            book.spine = []
            book.toc = []
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            epub.write_epub(str(epub_path), book, {})

            components, images = FileService.parse_imported_epub(str(epub_path))
            assert len(images) >= 1
            assert images[0][0] == "photo.jpg"
            assert images[0][1] == img_data

    def test_parse_multiple_chapters(self):
        """Parse an EPUB with multiple chapters."""
        from ebooklib import epub

        with tempfile.TemporaryDirectory() as tmp:
            epub_path = Path(tmp) / "test_multi.epub"

            book = epub.EpubBook()
            book.set_identifier("test-multi")
            book.set_title("Multi Chapter")
            book.set_language("en")

            chapters = []
            for i in range(3):
                ch = epub.EpubHtml(
                    title=f"Chapter {i+1}",
                    file_name=f"chap{i+1}.xhtml",
                    lang="en",
                )
                ch.content = (
                    "<html><body>"
                    f"<h1>Chapter {i+1}</h1>"
                    f"<p>Content {i+1}.</p>"
                    "</body></html>"
                )
                book.add_item(ch)
                chapters.append(ch)

            book.spine = chapters
            book.toc = []
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            epub.write_epub(str(epub_path), book, {})

            components, images = FileService.parse_imported_epub(str(epub_path))
            assert len(components) >= 3

    def test_html_to_markdown_headings(self):
        html = "<html><body><h1>Title</h1><h2>Sub</h2><p>Text.</p></body></html>"
        md = FileService._html_to_markdown(html)
        assert "# Title" in md
        assert "## Sub" in md
        assert "Text." in md

    def test_html_to_markdown_formatting(self):
        html = "<body><p><strong>Bold</strong> and <em>italic</em>.</p></body>"
        md = FileService._html_to_markdown(html)
        assert "**Bold**" in md
        assert "*italic*" in md

    def test_html_to_markdown_image(self):
        html = '<body><img src="photo.jpg" alt="Photo"/></body>'
        md = FileService._html_to_markdown(html)
        assert "![Photo](images/illustrations/photo.jpg)" in md

    def test_html_to_markdown_links(self):
        html = '<body><a href="http://example.com">Link</a></body>'
        md = FileService._html_to_markdown(html)
        assert "[Link](http://example.com)" in md

    def test_html_to_markdown_lists(self):
        html = "<body><ul><li>A</li><li>B</li></ul></body>"
        md = FileService._html_to_markdown(html)
        assert "- A" in md
        assert "- B" in md

    def test_html_entity_decoding(self):
        html = "<body><p>Hello &amp; welcome &lt;3</p></body>"
        md = FileService._html_to_markdown(html)
        assert "Hello & welcome <3" in md

    def test_import_epub_to_project(self):
        """End-to-end EPUB import into a project."""
        from ebooklib import epub

        with tempfile.TemporaryDirectory() as tmp:
            epub_path = Path(tmp) / "test_import.epub"

            book = epub.EpubBook()
            book.set_identifier("test-import")
            book.set_title("Imported")
            book.set_language("en")

            c1 = epub.EpubHtml(
                title="Intro", file_name="intro.xhtml", lang="en"
            )
            c1.content = (
                "<html><body>"
                "<h1>Introduction</h1>"
                "<p>Welcome.</p>"
                "</body></html>"
            )
            book.add_item(c1)

            img_data = b"\x89PNG\r\n\x1a\n"
            img_item = epub.EpubItem(
                uid="img1",
                file_name="img/cover.png",
                media_type="image/png",
                content=img_data,
            )
            book.add_item(img_item)

            book.spine = [c1]
            book.toc = []
            book.add_item(epub.EpubNcx())
            book.add_item(epub.EpubNav())

            epub.write_epub(str(epub_path), book, {})

            proj = Project(name="test", path=tmp)
            FileService.save_project(proj)

            count = FileService.import_epub(tmp, proj, str(epub_path))
            assert count >= 1
            assert len(proj.components) == count

            for c in proj.components:
                content = FileService.load_component(tmp, c)
                assert content, f"Missing content for {c.filename}"

            images_dir = Path(tmp) / "images" / "illustrations"
            assert images_dir.exists()
            cover_path = images_dir / "cover.png"
            assert cover_path.exists()
            assert cover_path.read_bytes() == img_data

            import shutil
            shutil.rmtree(tmp)

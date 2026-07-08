import pytest
from pathlib import Path
from ebooklib import epub
from mdtoepub.services.epub_service import EpubService
from mdtoepub.models.project import Project
from mdtoepub.models.component import Component, ComponentType


class TestChapterAutoTitle:
    def test_disabled_none(self):
        p = Project(auto_chapter_title="none")
        svc = EpubService(p)
        c = Component(type=ComponentType.CHAPTER, title="")
        num, title_part, display = svc._get_component_header(c, 1)
        assert num == ""
        assert title_part == "Capitulo"

    def test_applies_even_with_title(self):
        p = Project(auto_chapter_title="chapter_number")
        svc = EpubService(p)
        c = Component(type=ComponentType.CHAPTER, title="Mi Capitulo")
        num, title_part, display = svc._get_component_header(c, 1)
        assert num == "Capítulo 1"
        assert title_part == ""

    def test_chapter_number_format(self):
        p = Project(auto_chapter_title="chapter_number")
        svc = EpubService(p)
        c = Component(type=ComponentType.CHAPTER, title="")
        num1, _, _ = svc._get_component_header(c, 1)
        assert num1 == "Capítulo 1"
        num5, _, _ = svc._get_component_header(c, 5)
        assert num5 == "Capítulo 5"

    def test_number_format(self):
        p = Project(auto_chapter_title="number")
        svc = EpubService(p)
        c = Component(type=ComponentType.CHAPTER, title="")
        num1, _, _ = svc._get_component_header(c, 1)
        assert num1 == "1"
        num42, _, _ = svc._get_component_header(c, 42)
        assert num42 == "42"

    def test_non_chapter_type_ignored(self):
        p = Project(auto_chapter_title="chapter_number")
        svc = EpubService(p)
        for ctype in (ComponentType.FOREWORD, ComponentType.APPENDIX, ComponentType.TOC):
            c = Component(type=ctype, title="")
            num, _, _ = svc._get_component_header(c, 1)
            assert num == "", f"should not auto-title {ctype}"

    def test_with_title_mode(self):
        p = Project(auto_chapter_title="chapter_number_with_title")
        svc = EpubService(p)
        c = Component(type=ComponentType.CHAPTER, title="Mi Titulo")
        num, title_part, _ = svc._get_component_header(c, 1)
        assert num == "Capítulo 1"
        assert title_part == "Mi Titulo"

    def test_number_with_title_mode(self):
        p = Project(auto_chapter_title="number_with_title")
        svc = EpubService(p)
        c = Component(type=ComponentType.CHAPTER, title="Mi Titulo")
        num, title_part, _ = svc._get_component_header(c, 1)
        assert num == "1"
        assert title_part == "Mi Titulo"

    def test_show_title_false(self):
        p = Project(auto_chapter_title="chapter_number_with_title")
        svc = EpubService(p)
        c = Component(type=ComponentType.CHAPTER, title="Mi Titulo")
        c.frontmatter = {"show_title": False}
        num, title_part, _ = svc._get_component_header(c, 1)
        assert num == ""  # show_title=false disables auto-title too
        assert title_part == ""

    def test_show_title_false_no_auto(self):
        p = Project(auto_chapter_title="none")
        svc = EpubService(p)
        c = Component(type=ComponentType.CHAPTER, title="Mi Titulo")
        c.frontmatter = {"show_title": False}
        num, title_part, _ = svc._get_component_header(c, 1)
        assert num == ""
        assert title_part == ""


class TestTocClassForType:
    def test_all_types_return_toc_entry(self):
        p = Project()
        svc = EpubService(p)
        all_types = list(ComponentType)
        for ct in all_types:
            assert svc._toc_class_for_type(ct) == "toc-entry", f"{ct} should be toc-entry"


class TestEmbedImages:
    def test_embed_images_from_chapter(self):
        import tempfile, uuid
        with tempfile.TemporaryDirectory() as tmp:
            # Create project structure
            from mdtoepub.services.file_service import FileService
            proj = FileService.create_project_structure(tmp, "testimg")
            proj.path = str(Path(proj.path))

            # Create an image file
            img_dir = Path(proj.path) / "images" / "illustrations"
            img_dir.mkdir(parents=True, exist_ok=True)
            (img_dir / "foto.png").write_bytes(b"fake-png-data")

            # Add component with image reference
            comp = Component(
                id=str(uuid.uuid4()),
                type=ComponentType.CHAPTER,
                title="Test",
                filename="test.md",
                order=0,
            )
            proj.add_component(comp)
            md = "# Test\n\n![Foto](images/illustrations/foto.png)"
            FileService.save_component(proj.path, comp, md)
            FileService.save_project(proj)

            # Generate EPUB
            svc = EpubService(proj)
            with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
                output = f.name
            svc.generate(output, "epub3")

            # Verify image is inside EPUB
            import zipfile
            with zipfile.ZipFile(output) as z:
                namelist = z.namelist()
                assert any("foto.png" in n for n in namelist)
            Path(output).unlink()

    def test_embed_skips_url_images(self):
        import tempfile, uuid
        with tempfile.TemporaryDirectory() as tmp:
            from mdtoepub.services.file_service import FileService
            proj = FileService.create_project_structure(tmp, "testurl")
            proj.path = str(Path(proj.path))

            comp = Component(
                id=str(uuid.uuid4()),
                type=ComponentType.CHAPTER,
                title="Test",
                filename="test.md",
                order=0,
            )
            proj.add_component(comp)
            md = "# Test\n\n![Web](https://example.com/img.png)"
            FileService.save_component(proj.path, comp, md)
            FileService.save_project(proj)

            svc = EpubService(proj)
            embedded: set = set()
            html = '<img alt="Web" src="https://example.com/img.png"/>'
            svc._embed_images(epub.EpubBook(), html, comp.id, embedded)
            assert len(embedded) == 0
            Path(proj.path)

    def test_embed_skips_missing_images(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            from mdtoepub.services.file_service import FileService
            proj = FileService.create_project_structure(tmp, "testmiss")
            proj.path = str(Path(proj.path))

            svc = EpubService(proj)
            embedded: set = set()
            html = '<img alt="Missing" src="images/illustrations/noexist.png"/>'
            svc._embed_images(epub.EpubBook(), html, "comp1", embedded)
            assert len(embedded) == 0

    def test_embed_deduplicates_images(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            from mdtoepub.services.file_service import FileService
            proj = FileService.create_project_structure(tmp, "testdedup")
            proj.path = str(Path(proj.path))

            img_dir = Path(proj.path) / "images" / "illustrations"
            img_dir.mkdir(parents=True, exist_ok=True)
            (img_dir / "same.png").write_bytes(b"fake-png-data")

            svc = EpubService(proj)
            embedded: set = set()
            html1 = '<img src="images/illustrations/same.png"/>'
            html2 = '<img src="images/illustrations/same.png"/>'
            svc._embed_images(epub.EpubBook(), html1, "c1", embedded)
            assert len(embedded) == 1
            svc._embed_images(epub.EpubBook(), html2, "c2", embedded)
            assert len(embedded) == 1

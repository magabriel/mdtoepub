import pytest
from pathlib import Path
from ebooklib import epub
from mdtoepub.services.epub_service import EpubService
from mdtoepub.services.header_builder import HeaderBuilder
from mdtoepub.services.markdown_service import MarkdownService
from mdtoepub.models.project import Project
from mdtoepub.models.component import Component, ComponentType


class TestChapterAutoTitle:
    def _make_header_builder(self, project):
        svc = EpubService(project)
        labels = svc.resolve_labels()
        return HeaderBuilder(project, labels)

    def test_disabled_none(self):
        p = Project(auto_chapter_title="none")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.CHAPTER, title="")
        num, title_part, display = hb.get_component_header(c, 1)
        assert num == ""
        assert title_part == "Capitulo"

    def test_applies_even_with_title(self):
        p = Project(auto_chapter_title="chapter_number")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.CHAPTER, title="Mi Capitulo")
        num, title_part, display = hb.get_component_header(c, 1)
        assert num == "Capitulo 1"
        assert title_part == ""

    def test_chapter_number_format(self):
        p = Project(auto_chapter_title="chapter_number")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.CHAPTER, title="")
        num1, _, _ = hb.get_component_header(c, 1)
        assert num1 == "Capitulo 1"
        num5, _, _ = hb.get_component_header(c, 5)
        assert num5 == "Capitulo 5"

    def test_number_format(self):
        p = Project(auto_chapter_title="number")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.CHAPTER, title="")
        num1, _, _ = hb.get_component_header(c, 1)
        assert num1 == "1"
        num42, _, _ = hb.get_component_header(c, 42)
        assert num42 == "42"

    def test_non_chapter_type_ignored(self):
        p = Project(auto_chapter_title="chapter_number")
        hb = self._make_header_builder(p)
        for ctype in (ComponentType.FOREWORD, ComponentType.TOC):
            c = Component(type=ctype, title="")
            num, _, _ = hb.get_component_header(c, 1)
            assert num == "", f"should not auto-title {ctype}"

    def test_with_title_mode(self):
        p = Project(auto_chapter_title="chapter_number_with_title")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.CHAPTER, title="Mi Titulo")
        num, title_part, _ = hb.get_component_header(c, 1)
        assert num == "Capitulo 1"
        assert title_part == "Mi Titulo"

    def test_number_with_title_mode(self):
        p = Project(auto_chapter_title="number_with_title")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.CHAPTER, title="Mi Titulo")
        num, title_part, _ = hb.get_component_header(c, 1)
        assert num == "1"
        assert title_part == "Mi Titulo"

    def test_show_title_false(self):
        p = Project(auto_chapter_title="chapter_number_with_title")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.CHAPTER, title="Mi Titulo")
        c.frontmatter = {"show_title": False}
        num, title_part, _ = hb.get_component_header(c, 1)
        assert num == ""  # show_title=false disables auto-title too
        assert title_part == ""

    def test_show_title_false_no_auto(self):
        p = Project(auto_chapter_title="none")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.CHAPTER, title="Mi Titulo")
        c.frontmatter = {"show_title": False}
        num, title_part, _ = hb.get_component_header(c, 1)
        assert num == ""
        assert title_part == ""


class TestTocClassForType:
    def test_all_types_return_toc_entry(self):
        p = Project()
        svc = EpubService(p)
        all_types = list(ComponentType)
        for ct in all_types:
            assert svc.toc_class_for_type(ct) == "toc-entry", f"{ct} should be toc-entry"


class TestEmbedImages:
    def test_embed_images_from_chapter(self):
        import tempfile, uuid
        with tempfile.TemporaryDirectory() as tmp:
            from mdtoepub.services.file_service import FileService
            proj = FileService.create_project_structure(tmp, "testimg")
            proj.path = str(Path(proj.path))

            img_dir = Path(proj.path) / "images" / "illustrations"
            img_dir.mkdir(parents=True, exist_ok=True)
            (img_dir / "foto.png").write_bytes(b"fake-png-data")

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

            svc = EpubService(proj)
            with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
                output = f.name
            svc.generate(output, "epub3")

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
            svc.embed_images(epub.EpubBook(), html, comp.id, embedded)
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
            svc.embed_images(epub.EpubBook(), html, "comp1", embedded)
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
            svc.embed_images(epub.EpubBook(), html1, "c1", embedded)
            assert len(embedded) == 1
            svc.embed_images(epub.EpubBook(), html2, "c2", embedded)
            assert len(embedded) == 1


class TestFootnotes:
    def test_strip_footnotes_none(self):
        """No footnotes in HTML returns unchanged."""
        svc = EpubService(Project())
        html = '<section class="component-chapter"><p>Hello world.</p></section>'
        comp = Component(type=ComponentType.CHAPTER, filename="test.md")
        cleaned, fn_data = svc.strip_footnotes_from_html(html, comp)
        assert cleaned == html
        assert fn_data == []

    def test_strip_footnotes_single(self):
        """Extracts a single footnote from rendered HTML."""
        svc = EpubService(Project())
        comp = Component(type=ComponentType.CHAPTER, filename="test.md")
        svc.get_footnotes_component = lambda: Component(
            type=ComponentType.FOOTNOTES, filename="notas.md"
        )
        html = (
            '<section class="component-chapter">'
            '<p>Some text<sup id="fnref:1"><a href="#fn:1" role="doc-noteref">1</a></sup>.</p>'
            '<div class="footnote">'
            '<hr>'
            '<ol>'
            '<li id="fn:1" role="doc-endnote">'
            '<p>Footnote text. <a href="#fnref:1" class="footnote-backref" role="doc-backlink">\u21a9</a></p>'
            '</li>'
            '</ol>'
            '</div>'
            '</section>'
        )

        cleaned, fn_data = svc.strip_footnotes_from_html(html, comp)

        assert len(fn_data) == 1
        fn_id, fn_inner = fn_data[0]
        assert fn_id == "fn:test-1"
        assert '<div class="footnote">' not in cleaned
        assert 'href="notas.xhtml#fn:test-1"' in cleaned

    def test_strip_footnotes_multiple(self):
        """Extracts multiple footnotes from one chapter."""
        svc = EpubService(Project())
        svc.get_footnotes_component = lambda: Component(
            type=ComponentType.FOOTNOTES, filename="notas.md"
        )
        comp = Component(type=ComponentType.CHAPTER, filename="cap1.md")
        html = (
            '<section class="component-chapter">'
            '<p>Foo<sup id="fnref:1"><a href="#fn:1">1</a></sup> '
            'bar<sup id="fnref:2"><a href="#fn:2">2</a></sup></p>'
            '<div class="footnote">'
            '<ol>'
            '<li id="fn:1"><p>First. <a href="#fnref:1">\u21a9</a></p></li>'
            '<li id="fn:2"><p>Second. <a href="#fnref:2">\u21a9</a></p></li>'
            '</ol>'
            '</div>'
            '</section>'
        )
        cleaned, fn_data = svc.strip_footnotes_from_html(html, comp)

        assert len(fn_data) == 2
        assert fn_data[0][0] == "fn:cap1-1"
        assert fn_data[1][0] == "fn:cap1-2"
        assert 'href="notas.xhtml#fn:cap1-1"' in cleaned
        assert 'href="notas.xhtml#fn:cap1-2"' in cleaned
        assert 'href="cap1.xhtml#fnref:1"' in fn_data[0][1]
        assert 'href="cap1.xhtml#fnref:2"' in fn_data[1][1]

    def test_footnotes_default_without_component(self):
        """Without FOOTNOTES component, footnotes remain at chapter end."""
        import tempfile, uuid
        from mdtoepub.services.file_service import FileService

        with tempfile.TemporaryDirectory() as tmp:
            proj = FileService.create_project_structure(tmp, "fndefault")
            proj.path = str(Path(proj.path))

            comp = Component(
                id=str(uuid.uuid4()),
                type=ComponentType.CHAPTER,
                title="Test",
                filename="test.md",
                order=0,
            )
            proj.add_component(comp)
            md = "# Test\n\nSome text with a footnote[^1].\n\n[^1]: The footnote text."
            FileService.save_component(proj.path, comp, md)
            FileService.save_project(proj)

            svc = EpubService(proj)
            with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
                output = f.name
            svc.generate(output, "epub3")

            import zipfile
            with zipfile.ZipFile(output) as z:
                assert "EPUB/test.xhtml" in z.namelist()
                content = z.read("EPUB/test.xhtml").decode("utf-8")
                assert 'class="footnote"' in content
                assert 'id="fn:1"' in content
                assert 'id="fnref:1"' in content
            Path(output).unlink()

    def test_footnotes_collected_with_component(self):
        """With FOOTNOTES component, footnotes are collected and chapter is clean."""
        import tempfile, uuid
        from mdtoepub.services.file_service import FileService

        with tempfile.TemporaryDirectory() as tmp:
            proj = FileService.create_project_structure(tmp, "fncollected")
            proj.path = str(Path(proj.path))

            comp1 = Component(
                id=str(uuid.uuid4()),
                type=ComponentType.CHAPTER,
                title="Chapter 1",
                filename="cap1.md",
                order=0,
            )
            proj.add_component(comp1)
            md1 = "# Chapter 1\n\nText with note[^1].\n\n[^1]: First note."
            FileService.save_component(proj.path, comp1, md1)

            comp2 = Component(
                id=str(uuid.uuid4()),
                type=ComponentType.CHAPTER,
                title="Chapter 2",
                filename="cap2.md",
                order=1,
            )
            proj.add_component(comp2)
            md2 = "# Chapter 2\n\nAnother note[^1].\n\n[^1]: Second note."
            FileService.save_component(proj.path, comp2, md2)

            fn_comp = Component(
                id=str(uuid.uuid4()),
                type=ComponentType.FOOTNOTES,
                title="Notas",
                filename="notas.md",
                order=2,
            )
            proj.add_component(fn_comp)
            FileService.save_component(proj.path, fn_comp,
                                       "# Notas\n\nAqui estan las notas.")
            FileService.save_project(proj)

            svc = EpubService(proj)
            with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
                output = f.name
            svc.generate(output, "epub3")

            import zipfile
            with zipfile.ZipFile(output) as z:
                namelist = z.namelist()
                assert "EPUB/notas.xhtml" in namelist

                cap1_content = z.read("EPUB/cap1.xhtml").decode("utf-8")
                assert 'class="footnote"' not in cap1_content
                assert 'href="notas.xhtml#' in cap1_content

                notas_content = z.read("EPUB/notas.xhtml").decode("utf-8")
                assert 'id="fn:cap1-1"' in notas_content
                assert 'id="fn:cap2-2"' in notas_content
                assert "Aqui estan las notas" in notas_content
                assert "Notas" in notas_content

            Path(output).unlink()

    def test_footnotes_component_no_notes_in_chapters(self):
        """FOOTNOTES component with no footnotes in chapters shows user content only."""
        import tempfile, uuid
        from mdtoepub.services.file_service import FileService

        with tempfile.TemporaryDirectory() as tmp:
            proj = FileService.create_project_structure(tmp, "fnempty")
            proj.path = str(Path(proj.path))

            comp = Component(
                id=str(uuid.uuid4()),
                type=ComponentType.CHAPTER,
                title="Chapter",
                filename="cap.md",
                order=0,
            )
            proj.add_component(comp)
            FileService.save_component(proj.path, comp, "# Chapter\n\nNo footnotes here.")

            fn_comp = Component(
                id=str(uuid.uuid4()),
                type=ComponentType.FOOTNOTES,
                title="Notas",
                filename="notas.md",
                order=1,
            )
            proj.add_component(fn_comp)
            FileService.save_component(proj.path, fn_comp,
                                       "# Notas\n\nNotas vacias.")
            FileService.save_project(proj)

            svc = EpubService(proj)
            with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
                output = f.name
            svc.generate(output, "epub3")

            import zipfile
            with zipfile.ZipFile(output) as z:
                notas_content = z.read("EPUB/notas.xhtml").decode("utf-8")
                assert "Notas vacias" in notas_content
                assert 'footnotes-collection' not in notas_content
            Path(output).unlink()

    def test_footnotes_empty_content_still_included(self):
        """FOOTNOTES component with empty content still generates a chapter."""
        import tempfile, uuid
        from mdtoepub.services.file_service import FileService

        with tempfile.TemporaryDirectory() as tmp:
            proj = FileService.create_project_structure(tmp, "fnempty2")
            proj.path = str(Path(proj.path))

            comp = Component(
                id=str(uuid.uuid4()),
                type=ComponentType.CHAPTER,
                title="Chapter",
                filename="cap.md",
                order=0,
            )
            proj.add_component(comp)
            FileService.save_component(proj.path, comp,
                                       "# Chapter\n\nNote[^1].\n\n[^1]: Text.")

            fn_comp = Component(
                id=str(uuid.uuid4()),
                type=ComponentType.FOOTNOTES,
                title="Mis Notas",
                filename="notas.md",
                order=1,
            )
            proj.add_component(fn_comp)
            FileService.save_component(proj.path, fn_comp, "")
            FileService.save_project(proj)

            svc = EpubService(proj)
            with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
                output = f.name
            svc.generate(output, "epub3")

            import zipfile
            with zipfile.ZipFile(output) as z:
                assert "EPUB/notas.xhtml" in z.namelist(), \
                    "notas.xhtml must exist even with empty content"
                notas_content = z.read("EPUB/notas.xhtml").decode("utf-8")
                assert "Mis Notas" in notas_content
                assert 'id="fn:cap-1"' in notas_content
            Path(output).unlink()


class TestAppendixAutoTitle:
    def _make_header_builder(self, project):
        svc = EpubService(project)
        labels = svc.resolve_labels()
        return HeaderBuilder(project, labels)

    def test_appendix_chapter_number_format(self):
        p = Project(auto_appendix_title="chapter_number")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.APPENDIX, title="")
        num1, _, _ = hb.get_component_header(c, 1)
        assert num1 == "Apendice 1"

    def test_appendix_number_format(self):
        p = Project(auto_appendix_title="number")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.APPENDIX, title="")
        num1, _, _ = hb.get_component_header(c, 42)
        assert num1 == "42"

    def test_appendix_with_title_mode(self):
        p = Project(auto_appendix_title="chapter_number_with_title")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.APPENDIX, title="Datos")
        num, title_part, _ = hb.get_component_header(c, 3)
        assert num == "Apendice 3"
        assert title_part == "Datos"


class TestPartAutoTitle:
    def _make_header_builder(self, project):
        svc = EpubService(project)
        labels = svc.resolve_labels()
        return HeaderBuilder(project, labels)

    def test_disabled_none(self):
        p = Project(auto_part_title="none")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.PART, title="Introduccion")
        num, title_part, display = hb.get_part_header(c, 1)
        assert num == ""
        assert title_part == "Introduccion"

    def test_part_number_format(self):
        p = Project(auto_part_title="part_number")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.PART, title="")
        num1, _, _ = hb.get_part_header(c, 1)
        assert num1 == "Parte 1"
        num5, _, _ = hb.get_part_header(c, 5)
        assert num5 == "Parte 5"

    def test_number_format(self):
        p = Project(auto_part_title="number")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.PART, title="")
        num1, _, _ = hb.get_part_header(c, 1)
        assert num1 == "1"

    def test_with_title_mode(self):
        p = Project(auto_part_title="part_number_with_title")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.PART, title="Mi Parte")
        num, title_part, _ = hb.get_part_header(c, 2)
        assert num == "Parte 2"
        assert title_part == "Mi Parte"

    def test_number_with_title_mode(self):
        p = Project(auto_part_title="number_with_title")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.PART, title="Mi Parte")
        num, title_part, _ = hb.get_part_header(c, 3)
        assert num == "3"
        assert title_part == "Mi Parte"

    def test_show_title_false(self):
        p = Project(auto_part_title="part_number_with_title")
        hb = self._make_header_builder(p)
        c = Component(type=ComponentType.PART, title="Mi Parte")
        c.frontmatter = {"show_title": False}
        num, title_part, _ = hb.get_part_header(c, 1)
        assert num == ""
        assert title_part == ""


class TestLocalizedLabels:
    def test_english_chapter_label(self):
        p = Project(auto_chapter_title="chapter_number", language="en",
                     labels={"chapter": "Chapter"})
        svc = EpubService(p)
        labels = svc.resolve_labels()
        hb = HeaderBuilder(p, labels)
        c = Component(type=ComponentType.CHAPTER, title="")
        num, _, _ = hb.get_component_header(c, 1)
        assert num == "Chapter 1"

    def test_english_figure_label(self):
        html = '<p><img alt="Photo" src="img.jpg" /></p>'
        labels = {"figure": "Figure"}
        result = MarkdownService._add_image_captions(html, figure_num_start=1,
                                                      labels=labels)
        assert '<figcaption>Figure 1 - Photo</figcaption>' in result

    def test_english_table_label(self):
        html = '<!-- Table: My Table --><table><tr><td>Data</td></tr></table>'
        labels = {"table": "Table"}
        result = MarkdownService._add_table_captions(html, table_num_start=1,
                                                      labels=labels)
        assert '<figcaption>Table 1 - My Table</figcaption>' in result

    def test_figure_fallback_spanish(self):
        html = '<p><img alt="Foto" src="img.jpg" /></p>'
        result = MarkdownService._add_image_captions(html, figure_num_start=1)
        assert '<figcaption>Figura 1 - Foto</figcaption>' in result

    def test_table_fallback_spanish(self):
        html = '<!-- Table: Mi Tabla --><table><tr><td>Dato</td></tr></table>'
        result = MarkdownService._add_table_captions(html, table_num_start=1)
        assert '<figcaption>Tabla 1 - Mi Tabla</figcaption>' in result

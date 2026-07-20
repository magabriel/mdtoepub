import re
from typing import Dict, List, Optional

from ebooklib import epub

from ..models.project import Project
from ..models.component import Component, ComponentType
from .markdown_service import MarkdownService
from .footnote_processor import ERROR_BASE_KEY
from .file_service import FileService
from .yaml_service import YamlService
from .header_builder import HeaderBuilder


class FootnotesProcessor:
    """Extracts, collects, and renders footnotes for EPUB generation."""

    FOOTNOTE_DIV_RE = re.compile(
        r'<div class="footnote">.*?<ol>(.*?)</ol>.*?</div>',
        re.DOTALL,
    )
    LI_FN_RE = re.compile(
        r'<li[^>]*\bid="fn:(\d+)"[^>]*>(.*?)</li>',
        re.DOTALL,
    )
    SUP_FN_REF_RE = re.compile(
        r'href="#fn:(\d+)"',
    )
    FN_BACKLINK_RE = re.compile(
        r'href="#fnref:(\d+)"',
    )

    def __init__(
        self,
        project: Project,
        labels: Dict[str, str],
        header_builder: HeaderBuilder,
        markdown_service: MarkdownService,
    ):
        """Initialize with project, labels, and services.

        Args:
            project: The project containing components.
            labels: Resolved label dictionary.
            header_builder: HeaderBuilder for computing display titles.
            markdown_service: MarkdownService for rendering markdown.
        """
        self.project = project
        self.labels = labels
        self.header_builder = header_builder
        self.markdown_service = markdown_service

    def get_footnotes_component(self) -> Optional[Component]:
        """Find the FOOTNOTES component in the project, if any.

        Returns:
            The FOOTNOTES component or None.
        """
        for c in self.project.components:
            if c.type == ComponentType.FOOTNOTES:
                return c
        return None

    def strip_footnotes_from_html(self, html: str, component: Component) -> tuple:
        """Extract footnotes from rendered HTML and remove them.

        Args:
            html: The rendered HTML content.
            component: The component the HTML belongs to.

        Returns:
            A tuple of (cleaned_html, list_of_(namespaced_id, li_inner_html)).
        """
        fn_div_match = self.FOOTNOTE_DIV_RE.search(html)
        if not fn_div_match:
            return html, []

        ol_content = fn_div_match.group(1)
        ch_fn_base = component.filename.replace('.md', '')
        fn_filename = self.get_footnotes_component().filename.replace('.md', '.xhtml')

        footnotes = []
        for li_match in self.LI_FN_RE.finditer(ol_content):
            orig_num = li_match.group(1)
            li_inner = li_match.group(2)
            namespaced_id = f"fn:{ch_fn_base}-{orig_num}"

            # Rewrite backlinks: href="#fnref:X" -> href="{ch_fn_base}.xhtml#fnref:X"
            li_inner = self.FN_BACKLINK_RE.sub(
                f'href="{ch_fn_base}.xhtml#fnref:\\1"', li_inner
            )

            footnotes.append((namespaced_id, li_inner))

        # Remove footnote div from HTML
        html = self.FOOTNOTE_DIV_RE.sub('', html)

        # Rewrite sup references: href="#fn:X" -> href="{fn_filename}#fn:{ch_fn_base}-X"
        html = self.SUP_FN_REF_RE.sub(
            lambda m: f'href="{fn_filename}#fn:{ch_fn_base}-{m.group(1)}"', html
        )

        return html, footnotes

    def build_footnotes_chapter(
        self,
        component: Component,
        collected: Dict[str, dict],
        style_items: List[epub.EpubItem] = None,
        variables: Optional[Dict[str, str]] = None,
    ) -> Optional[epub.EpubHtml]:
        """Build the footnotes chapter with user content + collected footnotes.

        Args:
            component: The FOOTNOTES component.
            collected: Footnotes collected from all components.
            style_items: CSS items to attach.
            variables: Template variables.

        Returns:
            An EpubHtml chapter, or None.
        """
        content = FileService.load_component(self.project.path, component)
        display_title = component.get_display_name(self.labels)

        if content:
            frontmatter, markdown_content = YamlService.parse_frontmatter(content)
        else:
            frontmatter = {}
            markdown_content = f"# {display_title}\n\n"

        # Render user content with header
        h1_match = re.search(r'^# (.+)$', markdown_content, re.MULTILINE)
        default_title = h1_match.group(1).strip() if h1_match else ""
        show_title = frontmatter.get("show_title", True)

        header_html = self.header_builder.build_header_html("", "", display_title if show_title else "")
        if header_html:
            if h1_match:
                markdown_content = (markdown_content[:h1_match.start()]
                                    + markdown_content[h1_match.end():])
                markdown_content = markdown_content.strip()
            markdown_content = header_html + markdown_content
        elif show_title and not default_title:
            markdown_content = f"# {display_title}\n\n{markdown_content}"
        elif not show_title and h1_match:
            markdown_content = (markdown_content[:h1_match.start()]
                                + markdown_content[h1_match.end():])
            markdown_content = markdown_content.strip()

        user_html = self.markdown_service.render(markdown_content, component.type, component.id,
                                                  variables=variables, labels=self.labels)

        # Build flat footnotes collection in document order
        if collected:
            fn_parts = ['<ol class="footnotes-collection">']
            for data in collected.values():
                for namespaced_id, li_inner in data['footnotes']:
                    value_num = namespaced_id.rsplit('-', 1)[1]
                    if int(value_num) >= ERROR_BASE_KEY:
                        fn_parts.append(f'<li id="{namespaced_id}">{li_inner}</li>')
                    else:
                        fn_parts.append(f'<li id="{namespaced_id}" value="{value_num}">{li_inner}</li>')
            fn_parts.append('</ol>')
            fn_collection = '\n'.join(fn_parts)
            sep = '</section>'
            if sep in user_html:
                full_html_content = user_html.replace(sep, fn_collection + '\n' + sep, 1)
            else:
                full_html_content = user_html + '\n' + fn_collection
        else:
            full_html_content = user_html

        chapter = epub.EpubHtml(
            title=display_title,
            file_name=f"{component.filename.replace('.md', '.xhtml')}",
            lang=self.project.language,
        )

        full_html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>{display_title}</title>
</head>
<body>
{full_html_content}
</body>
</html>"""

        chapter.content = full_html.encode("utf-8")

        if style_items:
            for item in style_items:
                chapter.add_item(item)

        return chapter

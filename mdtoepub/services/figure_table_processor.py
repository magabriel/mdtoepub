from typing import Dict, List, Optional, Tuple

from ..models.project import Project
from ..models.component import ComponentType
from .file_service import FileService
from .yaml_service import YamlService
from .markdown_service import MarkdownService


class FigureTableProcessor:
    """Scans components for figures/tables and generates LOF/LOT HTML."""

    EXCLUDED_TYPES = frozenset({
        ComponentType.PART, ComponentType.FOOTNOTES,
        ComponentType.TOC, ComponentType.COVER,
    })

    def __init__(self, project: Project, labels: Dict[str, str]):
        """Initialize with project and resolved labels.

        Args:
            project: The project containing numbering configuration.
            labels: Resolved label dictionary.
        """
        self.project = project
        self.labels = labels

    def prescan_figures(self) -> Tuple[list, Dict[str, int]]:
        """Scan all components for figure info and numbering.

        Returns:
            Tuple of (figure_info list, figure_start dict).
            figure_info is list of (fig_num, alt, filename).
            figure_start maps component ID to its starting figure number.
        """
        figure_info = []
        figure_start: Dict[str, int] = {}
        running_fig_total = 0
        if not self.project.figure_numbering:
            return figure_info, figure_start

        excluded = self.EXCLUDED_TYPES | {ComponentType.LOF}
        for component in self.project.get_ordered_components():
            if component.type in excluded:
                continue
            content = FileService.load_component(self.project.path, component)
            if content:
                _, md_text = YamlService.parse_frontmatter(content)
                alts = MarkdownService.extract_figure_alts(md_text)
                if alts:
                    figure_start[component.id] = running_fig_total + 1
                    for alt, _ in alts:
                        running_fig_total += 1
                        figure_info.append((running_fig_total, alt, component.filename))
        return figure_info, figure_start

    def prescan_tables(self) -> Tuple[list, Dict[str, int]]:
        """Scan all components for table info and numbering.

        Returns:
            Tuple of (table_info list, table_start dict).
            table_info is list of (tab_num, caption, filename).
            table_start maps component ID to its starting table number.
        """
        table_info = []
        table_start: Dict[str, int] = {}
        running_tab_total = 0
        if not self.project.table_numbering:
            return table_info, table_start

        excluded = self.EXCLUDED_TYPES | {ComponentType.LOT}
        for component in self.project.get_ordered_components():
            if component.type in excluded:
                continue
            content = FileService.load_component(self.project.path, component)
            if content:
                _, md_text = YamlService.parse_frontmatter(content)
                captions = MarkdownService.extract_table_captions(md_text)
                if captions:
                    table_start[component.id] = running_tab_total + 1
                    for caption, _ in captions:
                        running_tab_total += 1
                        table_info.append((running_tab_total, caption, component.filename))
        return table_info, table_start

    def generate_lof_html(self, figure_info: list) -> str:
        """Generate the List of Figures HTML from collected figure info.

        Args:
            figure_info: List of (fig_num, caption, filename) tuples.

        Returns:
            HTML string for the LOF, or empty string if no figures.
        """
        if not figure_info:
            return ""
        use_roman = self.project.figure_numbering_style == "roman"
        figure_label = self.labels.get("figure", "Figura")
        lines = ['<div class="lof-list">', '<ul>']
        for fig_num, caption, filename in figure_info:
            href = f"{filename.replace('.md', '.xhtml')}#fig_{fig_num}"
            num_str = MarkdownService.to_roman(fig_num) if use_roman else str(fig_num)
            if caption:
                text = f"{figure_label} {num_str} - {caption}"
            else:
                text = f"{figure_label} {num_str}"
            lines.append(f'<li class="lof-entry"><a href="{href}">{text}</a></li>')
        lines.append('</ul>')
        lines.append('</div>')
        return "\n".join(lines)

    def generate_lot_html(self, table_info: list) -> str:
        """Generate the List of Tables HTML from collected table info.

        Args:
            table_info: List of (tab_num, caption, filename) tuples.

        Returns:
            HTML string for the LOT, or empty string if no tables.
        """
        if not table_info:
            return ""
        use_roman = self.project.table_numbering_style == "roman"
        table_label = self.labels.get("table", "Tabla")
        lines = ['<div class="lot-list">', '<ul>']
        for tab_num, caption, filename in table_info:
            href = f"{filename.replace('.md', '.xhtml')}#tab_{tab_num}"
            num_str = MarkdownService.to_roman(tab_num) if use_roman else str(tab_num)
            if caption:
                text = f"{table_label} {num_str} - {caption}"
            else:
                text = f"{table_label} {num_str}"
            lines.append(f'<li class="lot-entry"><a href="{href}">{text}</a></li>')
        lines.append('</ul>')
        lines.append('</div>')
        return "\n".join(lines)

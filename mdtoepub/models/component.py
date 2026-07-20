from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import uuid


class ComponentType(Enum):
    """Enumeration of all supported component types."""

    ACKNOWLEDGEMENT = "acknowledgement"
    AFTERWORD = "afterword"
    APPENDIX = "appendix"
    AUTHOR = "author"
    CHAPTER = "chapter"
    CONCLUSION = "conclusion"
    COVER = "cover"
    DEDICATION = "dedication"
    EDITION = "edition"
    EPILOGUE = "epilogue"
    FOREWORD = "foreword"
    GLOSSARY = "glossary"
    INTRODUCTION = "introduction"
    LICENSE = "license"
    LOF = "lof"
    LOT = "lot"
    PART = "part"
    PREFACE = "preface"
    PROLOGUE = "prologue"
    TITLE = "title"
    TOC = "toc"
    FOOTNOTES = "footnotes"


COMPONENT_TYPE_LABELS = {
    ComponentType.ACKNOWLEDGEMENT: "Agradecimientos",
    ComponentType.AFTERWORD: "Nota final",
    ComponentType.APPENDIX: "Apendice",
    ComponentType.AUTHOR: "Autor",
    ComponentType.CHAPTER: "Capitulo",
    ComponentType.CONCLUSION: "Conclusion",
    ComponentType.COVER: "Portada",
    ComponentType.DEDICATION: "Dedicatoria",
    ComponentType.EDITION: "Edicion",
    ComponentType.EPILOGUE: "Epilogo",
    ComponentType.FOREWORD: "Prologo",
    ComponentType.GLOSSARY: "Glosario",
    ComponentType.INTRODUCTION: "Introduccion",
    ComponentType.LICENSE: "Licencia",
    ComponentType.LOF: "Lista de figuras",
    ComponentType.LOT: "Lista de tablas",
    ComponentType.PART: "Parte",
    ComponentType.PREFACE: "Prefacio",
    ComponentType.PROLOGUE: "Prologo",
    ComponentType.TITLE: "Pagina de titulo",
    ComponentType.TOC: "Tabla de contenidos",
    ComponentType.FOOTNOTES: "Notas al pie",
}


@dataclass
class Component:
    """Represents a section of the book (chapter, part, cover, etc.).

    Each component has a type, title, filename, and optional metadata.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: ComponentType = ComponentType.CHAPTER
    title: str = ""
    filename: str = ""
    order: int = 0
    part_id: Optional[str] = None
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    custom_css: str = ""

    def get_display_name(self, labels: Optional[Dict[str, str]] = None) -> str:
        """Return the display name for this component.

        Uses the title if set, otherwise falls back to the localized label
        for the component type.

        Args:
            labels: Optional label overrides dict.

        Returns:
            Display name string.
        """
        if self.title:
            return self.title
        if labels:
            return labels.get(self.type.value, COMPONENT_TYPE_LABELS.get(self.type, self.type.value))
        return COMPONENT_TYPE_LABELS.get(self.type, self.type.value)

    def should_use_numbering(self) -> bool:
        """Check if this component type supports auto-numbering.

        Returns:
            True for CHAPTER and APPENDIX types.
        """
        return self.type in (
            ComponentType.CHAPTER,
            ComponentType.APPENDIX,
        )


FRONTMATTER_TYPES: List[ComponentType] = [
    ComponentType.ACKNOWLEDGEMENT,
    ComponentType.AUTHOR,
    ComponentType.COVER,
    ComponentType.DEDICATION,
    ComponentType.FOREWORD,
    ComponentType.INTRODUCTION,
    ComponentType.LICENSE,
    ComponentType.PREFACE,
    ComponentType.PROLOGUE,
    ComponentType.TITLE,
    ComponentType.TOC,
]

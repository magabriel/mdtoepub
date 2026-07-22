from typing import Dict, Optional

DEFAULT_LABELS: Dict[str, Dict[str, str]] = {
    "es": {
        "acknowledgement": "Agradecimientos",
        "afterword": "Nota final",
        "appendix": "Apendice",
        "author": "Autor",
        "chapter": "Capitulo",
        "conclusion": "Conclusion",
        "cover": "Portada",
        "dedication": "Dedicatoria",
        "edition": "Edicion",
        "epilogue": "Epilogo",
        "foreword": "Prologo",
        "glossary": "Glosario",
        "introduction": "Introduccion",
        "license": "Licencia",
        "lof": "Lista de figuras",
        "lot": "Lista de tablas",
        "part": "Parte",
        "preface": "Prefacio",
        "prologue": "Prologo",
        "title": "Pagina de titulo",
        "toc": "Tabla de contenidos",
        "footnotes": "Notas al pie",
        "figure": "Figura",
        "table": "Tabla",
    },
    "en": {
        "acknowledgement": "Acknowledgements",
        "afterword": "Afterword",
        "appendix": "Appendix",
        "author": "Author",
        "chapter": "Chapter",
        "conclusion": "Conclusion",
        "cover": "Cover",
        "dedication": "Dedication",
        "edition": "Edition",
        "epilogue": "Epilogue",
        "foreword": "Foreword",
        "glossary": "Glossary",
        "introduction": "Introduction",
        "license": "License",
        "lof": "List of Figures",
        "lot": "List of Tables",
        "part": "Part",
        "preface": "Preface",
        "prologue": "Prologue",
        "title": "Title Page",
        "toc": "Table of Contents",
        "footnotes": "Footnotes",
        "figure": "Figure",
        "table": "Table",
    },
}


def resolve_labels(
    language: str,
    project_labels: Optional[Dict[str, str]] = None,
    global_config: Optional[Dict] = None,
) -> Dict[str, str]:
    """Resolve localized labels for a book.

    Priority: project > global_config[language] > built-in defaults[language]
    Falls back to English for unknown languages.
    """
    defaults = DEFAULT_LABELS.get(language, DEFAULT_LABELS["en"])

    global_labels: Dict[str, str] = {}
    if global_config and "labels" in global_config:
        global_labels = global_config["labels"].get(language, {})

    project_labels = project_labels or {}

    result = dict(defaults)
    result.update(global_labels)
    result.update(project_labels)

    return result

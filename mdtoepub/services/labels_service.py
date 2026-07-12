from typing import Dict, Optional

DEFAULT_LABELS: Dict[str, Dict[str, str]] = {
    "es": {
        "chapter": "Capítulo",
        "part": "Parte",
        "appendix": "Apéndice",
        "figure": "Figura",
        "table": "Tabla",
    },
    "en": {
        "chapter": "Chapter",
        "part": "Part",
        "appendix": "Appendix",
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
    Falls back to Spanish for unknown languages.
    """
    defaults = DEFAULT_LABELS.get(language, DEFAULT_LABELS["es"])

    global_labels: Dict[str, str] = {}
    if global_config and "labels" in global_config:
        global_labels = global_config["labels"].get(language, {})

    project_labels = project_labels or {}

    result = dict(defaults)
    result.update(global_labels)
    result.update(project_labels)

    return result

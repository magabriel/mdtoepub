import pytest
from mdtoepub.services.labels_service import resolve_labels, DEFAULT_LABELS


class TestResolveLabels:
    def test_default_spanish(self):
        labels = resolve_labels("es")
        assert labels["chapter"] == "Capítulo"
        assert labels["part"] == "Parte"
        assert labels["appendix"] == "Apéndice"
        assert labels["figure"] == "Figura"
        assert labels["table"] == "Tabla"

    def test_default_english(self):
        labels = resolve_labels("en")
        assert labels["chapter"] == "Chapter"
        assert labels["part"] == "Part"
        assert labels["appendix"] == "Appendix"
        assert labels["figure"] == "Figure"
        assert labels["table"] == "Table"

    def test_unknown_language_falls_back_to_spanish(self):
        labels = resolve_labels("fr")
        assert labels["chapter"] == "Capítulo"

    def test_project_overrides(self):
        labels = resolve_labels("es", project_labels={"chapter": "MiCapítulo"})
        assert labels["chapter"] == "MiCapítulo"
        assert labels["figure"] == "Figura"

    def test_global_config_overrides(self):
        global_config = {
            "labels": {
                "es": {"chapter": "GlobalCapítulo"}
            }
        }
        labels = resolve_labels("es", global_config=global_config)
        assert labels["chapter"] == "GlobalCapítulo"
        assert labels["figure"] == "Figura"

    def test_project_overrides_global(self):
        global_config = {
            "labels": {
                "es": {"chapter": "GlobalCapítulo"}
            }
        }
        labels = resolve_labels(
            "es",
            project_labels={"chapter": "ProjectCapítulo"},
            global_config=global_config,
        )
        assert labels["chapter"] == "ProjectCapítulo"

    def test_global_config_for_specific_language(self):
        global_config = {
            "labels": {
                "en": {"chapter": "GlobalChapter"}
            }
        }
        labels = resolve_labels("en", global_config=global_config)
        assert labels["chapter"] == "GlobalChapter"

    def test_default_labels_not_mutated(self):
        original = DEFAULT_LABELS["es"]["chapter"]
        resolve_labels("es", project_labels={"chapter": "Otro"})
        assert DEFAULT_LABELS["es"]["chapter"] == original

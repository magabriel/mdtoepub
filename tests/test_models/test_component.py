import pytest
from mdtoepub.models.component import Component, ComponentType, COMPONENT_TYPE_LABELS


class TestComponentType:
    def test_component_type_values(self):
        assert ComponentType.CHAPTER.value == "chapter"
        assert ComponentType.INTRODUCTION.value == "introduction"
        assert ComponentType.PREFACE.value == "preface"

    def test_all_types_have_labels(self):
        for ct in ComponentType:
            assert ct in COMPONENT_TYPE_LABELS


class TestComponent:
    def test_create_component_defaults(self):
        comp = Component()
        assert comp.type == ComponentType.CHAPTER
        assert comp.title == ""
        assert comp.filename == ""

    def test_get_display_name_with_title(self):
        comp = Component(title="Test Title")
        assert comp.get_display_name() == "Test Title"

    def test_get_display_name_without_title(self):
        comp = Component(type=ComponentType.CHAPTER)
        assert comp.get_display_name() == COMPONENT_TYPE_LABELS[ComponentType.CHAPTER]

    def test_should_use_numbering_chapter(self):
        comp = Component(type=ComponentType.CHAPTER)
        assert comp.should_use_numbering() is True

    def test_should_use_numbering_introduction(self):
        comp = Component(type=ComponentType.INTRODUCTION)
        assert comp.should_use_numbering() is False

    def test_should_use_numbering_appendix(self):
        comp = Component(type=ComponentType.APPENDIX)
        assert comp.should_use_numbering() is True

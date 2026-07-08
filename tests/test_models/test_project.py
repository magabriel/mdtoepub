import pytest
from mdtoepub.models.project import Project
from mdtoepub.models.component import Component, ComponentType


class TestProject:
    def test_create_project_defaults(self):
        project = Project()
        assert project.name == ""
        assert project.title == ""
        assert project.author == ""
        assert project.language == "es"
        assert project.theme_id == "classic"
        assert project.epub_version == "epub3"
        assert project.auto_chapter_title == "none"
        assert project.edicion == ""
        assert project.fecha_publicacion == ""
        assert project.isbn == ""
        assert project.editorial == ""
        assert project.components == []

    def test_add_component(self):
        project = Project()
        comp = Component(title="Test")
        project.add_component(comp)
        assert len(project.components) == 1
        assert project.components[0].order == 0

    def test_add_multiple_components_order(self):
        project = Project()
        comp1 = Component(title="First")
        comp2 = Component(title="Second")
        project.add_component(comp1)
        project.add_component(comp2)
        assert project.components[0].order == 0
        assert project.components[1].order == 1

    def test_remove_component(self):
        project = Project()
        comp = Component(id="test-id", title="Test")
        project.add_component(comp)
        project.remove_component("test-id")
        assert len(project.components) == 0

    def test_get_component(self):
        project = Project()
        comp = Component(id="test-id", title="Test")
        project.add_component(comp)
        found = project.get_component("test-id")
        assert found is not None
        assert found.title == "Test"

    def test_get_component_not_found(self):
        project = Project()
        found = project.get_component("nonexistent")
        assert found is None

    def test_get_ordered_components(self):
        project = Project()
        comp1 = Component(title="Second", order=1)
        comp2 = Component(title="First", order=0)
        project.components = [comp1, comp2]
        ordered = project.get_ordered_components()
        assert ordered[0].title == "First"
        assert ordered[1].title == "Second"

    def test_get_parts(self):
        project = Project()
        part = Component(id="p1", type=ComponentType.PART, title="Part 1")
        chapter = Component(title="Chapter")
        project.add_component(part)
        project.add_component(chapter)
        parts = project.get_parts()
        assert len(parts) == 1
        assert parts[0].id == "p1"

    def test_get_part(self):
        project = Project()
        part = Component(id="p1", type=ComponentType.PART, title="Part 1")
        project.add_component(part)
        found = project.get_part("p1")
        assert found is not None
        assert found.title == "Part 1"

    def test_get_part_not_found(self):
        project = Project()
        assert project.get_part("nonexistent") is None

    def test_get_part_children(self):
        project = Project()
        part = Component(id="p1", type=ComponentType.PART, title="Part 1")
        child = Component(id="c1", title="Child", part_id="p1")
        other = Component(title="Other")
        project.add_component(part)
        project.add_component(child)
        project.add_component(other)
        children = project.get_part_children("p1")
        assert len(children) == 1
        assert children[0].id == "c1"

    def test_get_parent_part(self):
        project = Project()
        part = Component(id="p1", type=ComponentType.PART, title="Part 1")
        child = Component(id="c1", title="Child", part_id="p1")
        project.add_component(part)
        project.add_component(child)
        parent = project.get_parent_part(child)
        assert parent is not None
        assert parent.id == "p1"

"""File service facade.

Re-exports from ProjectService, ComponentService, and ImportService
for backward compatibility. New code should import from the specific
service classes directly.
"""

from .project_service import ProjectService
from .component_service import ComponentService
from .import_service import ImportService, slugify, SUPPORTED_IMAGE_FORMATS


class FileService:
    """Facade for project, component, and import operations.

    Delegates to ProjectService, ComponentService, and ImportService.
    New code should import from the specific service classes directly.
    """

    # ProjectService delegates
    create_project_structure = staticmethod(ProjectService.create_project_structure)
    load_project = staticmethod(ProjectService.load_project)
    save_project = staticmethod(ProjectService.save_project)

    # ComponentService delegates
    save_component = staticmethod(ComponentService.save_component)
    load_component = staticmethod(ComponentService.load_component)
    generate_filename = staticmethod(ComponentService.generate_filename)
    rename_image_references = staticmethod(ComponentService.rename_image_references)

    # ImportService delegates
    parse_imported_markdown = staticmethod(ImportService.parse_imported_markdown)
    import_book = staticmethod(ImportService.import_book)
    parse_imported_epub = staticmethod(ImportService.parse_imported_epub)
    import_epub = staticmethod(ImportService.import_epub)
    _bump_headings = staticmethod(ImportService.bump_headings)
    _process_markdown_images = staticmethod(ImportService.process_markdown_images)
    _html_to_markdown = staticmethod(ImportService.html_to_markdown)

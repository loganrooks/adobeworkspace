"""Helper functions for working with document models.

This module provides utility functions for common document model operations
like searching, traversing, and modifying document structure.
"""

from typing import Any, Callable, Dict, Generator, List, Optional, TypeVar

from pipeline.models.base import (
    Annotation,
    ContentElement,
    DocumentModel,
    Section,
    TextElement
)

T = TypeVar('T')

def find_elements_by_type(model: DocumentModel, element_type: str) -> List[ContentElement]:
    """Find all elements of a specific type in the document.
    
    Args:
        model: Document model to search
        element_type: Type of elements to find
        
    Returns:
        List of matching elements
    """
    elements = []
    
    # Search main content
    for element in model.content:
        if element.element_type == element_type:
            elements.append(element)
            
    # Search sections
    for section in traverse_sections(model):
        for element in section.content_elements:
            if element.element_type == element_type:
                elements.append(element)
                
    return elements

def find_sections_by_level(model: DocumentModel, level: int) -> List[Section]:
    """Find all sections at a specific level.
    
    Args:
        model: Document model to search
        level: Section level to find
        
    Returns:
        List of matching sections
    """
    return [
        section for section in traverse_sections(model)
        if section.level == level
    ]

def find_annotations_by_type(model: DocumentModel, annotation_type: str) -> List[Annotation]:
    """Find all annotations of a specific type.
    
    Args:
        model: Document model to search
        annotation_type: Type of annotations to find
        
    Returns:
        List of matching annotations
    """
    annotations = []
    
    # Document-level annotations
    for annotation in model.annotations:
        if annotation.type == annotation_type:
            annotations.append(annotation)
    
    # Element annotations
    def check_element(element: ContentElement) -> None:
        for annotation in element.annotations:
            if annotation.type == annotation_type:
                annotations.append(annotation)
    
    # Check main content
    for element in model.content:
        check_element(element)
    
    # Check sections
    for section in traverse_sections(model):
        for element in section.content_elements:
            check_element(element)
            
    return annotations

def traverse_sections(model: DocumentModel) -> Generator[Section, None, None]:
    """Traverse all sections in the document in depth-first order.
    
    Args:
        model: Document model to traverse
        
    Yields:
        Each section in depth-first order
    """
    def traverse(section: Section) -> Generator[Section, None, None]:
        yield section
        for subsection in section.subsections:
            yield from traverse(subsection)
            
    for section in model.structure.sections:
        yield from traverse(section)

def traverse_elements(model: DocumentModel) -> Generator[ContentElement, None, None]:
    """Traverse all content elements in the document.
    
    Args:
        model: Document model to traverse
        
    Yields:
        Each content element in document order
    """
    # Main content elements
    for element in model.content:
        yield element
    
    # Elements in sections
    for section in traverse_sections(model):
        for element in section.content_elements:
            yield element

def get_text_content(model: DocumentModel, include_headers: bool = True) -> str:
    """Get all text content from the document.
    
    Args:
        model: Document model to extract text from
        include_headers: Whether to include section headers
        
    Returns:
        Combined text content
    """
    text_parts = []
    
    def add_section_text(section: Section, level: int) -> None:
        if include_headers and section.title:
            text_parts.append("#" * level + " " + section.title + "\n\n")
        
        for element in section.content_elements:
            if isinstance(element, TextElement):
                text_parts.append(element.text + "\n\n")
        
        for subsection in section.subsections:
            add_section_text(subsection, level + 1)
    
    # Add main content
    for element in model.content:
        if isinstance(element, TextElement):
            text_parts.append(element.text + "\n\n")
    
    # Add section content
    for section in model.structure.sections:
        add_section_text(section, 1)
    
    return "".join(text_parts).strip()

def modify_elements(
    model: DocumentModel,
    predicate: Callable[[ContentElement], bool],
    modifier: Callable[[ContentElement], None]
) -> None:
    """Modify elements in the document that match a predicate.
    
    Args:
        model: Document model to modify
        predicate: Function that returns True for elements to modify
        modifier: Function that modifies matching elements
    """
    # Modify main content
    for element in model.content:
        if predicate(element):
            modifier(element)
    
    # Modify elements in sections
    for section in traverse_sections(model):
        for element in section.content_elements:
            if predicate(element):
                modifier(element)

def find_element_by_id(model: DocumentModel, element_id: str) -> Optional[ContentElement]:
    """Find a content element by its ID.
    
    Args:
        model: Document model to search
        element_id: ID of the element to find
        
    Returns:
        Matching element or None if not found
    """
    for element in traverse_elements(model):
        if element.id == element_id:
            return element
    return None

def find_section_by_id(model: DocumentModel, section_id: str) -> Optional[Section]:
    """Find a section by its ID.
    
    Args:
        model: Document model to search
        section_id: ID of the section to find
        
    Returns:
        Matching section or None if not found
    """
    for section in traverse_sections(model):
        if section.id == section_id:
            return section
    return None

def add_section(
    model: DocumentModel,
    title: str,
    level: int,
    parent_id: Optional[str] = None
) -> Section:
    """Add a new section to the document.
    
    Args:
        model: Document model to modify
        title: Section title
        level: Section level
        parent_id: ID of parent section, or None for top-level
        
    Returns:
        Newly created section
    """
    from uuid import uuid4
    
    section = Section(
        id=str(uuid4()),
        title=title,
        level=level
    )
    
    if parent_id:
        parent = find_section_by_id(model, parent_id)
        if parent:
            parent.subsections.append(section)
        else:
            raise ValueError(f"Parent section not found: {parent_id}")
    else:
        model.structure.sections.append(section)
        
    return section

def update_toc(model: DocumentModel) -> None:
    """Update the table of contents based on document structure.
    
    Args:
        model: Document model to update
    """
    def create_toc_entry(section: Section) -> Dict[str, Any]:
        return {
            "title": section.title,
            "section_id": section.id,
            "level": section.level,
            "children": [
                create_toc_entry(subsec)
                for subsec in section.subsections
            ]
        }
    
    model.structure.toc.entries = [
        create_toc_entry(section)
        for section in model.structure.sections
    ]
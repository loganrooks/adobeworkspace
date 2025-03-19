"""Document model validation.

This module provides validation functionality for the document model format,
ensuring schema compliance and data integrity.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set

from pipeline.models.base import (
    Annotation,
    ContentElement,
    DocumentModel,
    Section
)

@dataclass
class ValidationError:
    """Validation error details."""
    path: str
    message: str
    severity: str = "error"

class DocumentModelValidator:
    """Validates document model integrity."""

    def validate(self, document_model: DocumentModel) -> List[ValidationError]:
        """Validate document model and return any errors.
        
        Args:
            document_model: The document model to validate
            
        Returns:
            List of validation errors found
        """
        errors: List[ValidationError] = []
        
        # Validate metadata
        errors.extend(self._validate_metadata(document_model))
        
        # Validate structure
        errors.extend(self._validate_structure(document_model))
        
        # Validate content elements
        errors.extend(self._validate_content_elements(document_model))
        
        # Validate annotations
        errors.extend(self._validate_annotations(document_model))
        
        # Validate references
        errors.extend(self._validate_references(document_model))
        
        return errors

    def _validate_metadata(self, model: DocumentModel) -> List[ValidationError]:
        """Validate document metadata."""
        errors = []
        
        if not model.metadata.title:
            errors.append(ValidationError(
                path="metadata.title",
                message="Document title is required"
            ))
        
        if not model.metadata.source.path:
            errors.append(ValidationError(
                path="metadata.source.path",
                message="Source path is required"
            ))
            
        # Validate processing history timestamps are in order
        prev_time: Optional[datetime] = None
        for i, step in enumerate(model.metadata.processing_history):
            if prev_time and step.timestamp < prev_time:
                errors.append(ValidationError(
                    path=f"metadata.processing_history[{i}].timestamp",
                    message="Processing step timestamps must be in chronological order"
                ))
            prev_time = step.timestamp
            
        return errors

    def _validate_structure(self, model: DocumentModel) -> List[ValidationError]:
        """Validate document structure."""
        errors = []
        
        # Track section IDs to ensure uniqueness
        section_ids: Set[str] = set()
        
        def validate_section(section: Section, level: int, path: str) -> None:
            if section.id in section_ids:
                errors.append(ValidationError(
                    path=f"{path}.id",
                    message=f"Duplicate section ID: {section.id}"
                ))
            section_ids.add(section.id)
            
            if section.level != level:
                errors.append(ValidationError(
                    path=f"{path}.level",
                    message=f"Invalid section level: expected {level}, got {section.level}"
                ))
            
            for i, subsection in enumerate(section.subsections):
                validate_section(subsection, level + 1, f"{path}.subsections[{i}]")
        
        # Validate main sections
        for i, section in enumerate(model.structure.sections):
            validate_section(section, 1, f"structure.sections[{i}]")
            
        # Validate TOC entries reference valid sections
        section_id_set = section_ids  # Reuse collected IDs
        for i, entry in enumerate(model.structure.toc.entries):
            section_id = entry.get("section_id")
            if section_id and section_id not in section_id_set:
                errors.append(ValidationError(
                    path=f"structure.toc.entries[{i}].section_id",
                    message=f"TOC entry references non-existent section: {section_id}"
                ))
        
        return errors

    def _validate_content_elements(self, model: DocumentModel) -> List[ValidationError]:
        """Validate content elements."""
        errors = []
        element_ids: Set[str] = set()
        
        def validate_element(element: ContentElement, path: str) -> None:
            if element.id in element_ids:
                errors.append(ValidationError(
                    path=f"{path}.id",
                    message=f"Duplicate element ID: {element.id}"
                ))
            element_ids.add(element.id)
            
            # Validate required fields based on element type
            if hasattr(element, "validate"):
                element_errors = element.validate()
                for err in element_errors:
                    errors.append(ValidationError(
                        path=f"{path}.{err.path}",
                        message=err.message,
                        severity=err.severity
                    ))
        
        # Validate elements in content list
        for i, element in enumerate(model.content):
            validate_element(element, f"content[{i}]")
        
        # Validate elements in sections
        def validate_section_elements(section: Section, path: str) -> None:
            for i, element in enumerate(section.content_elements):
                validate_element(element, f"{path}.content_elements[{i}]")
            
            for i, subsection in enumerate(section.subsections):
                validate_section_elements(subsection, f"{path}.subsections[{i}]")
        
        for i, section in enumerate(model.structure.sections):
            validate_section_elements(section, f"structure.sections[{i}]")
        
        return errors

    def _validate_annotations(self, model: DocumentModel) -> List[ValidationError]:
        """Validate annotations."""
        errors = []
        
        def validate_annotation(annotation: Annotation, path: str) -> None:
            if annotation.start < 0:
                errors.append(ValidationError(
                    path=f"{path}.start",
                    message="Annotation start position must be non-negative"
                ))
            
            if annotation.end < annotation.start:
                errors.append(ValidationError(
                    path=f"{path}.end",
                    message="Annotation end must be after start position"
                ))
        
        # Validate document-level annotations
        for i, annotation in enumerate(model.annotations):
            validate_annotation(annotation, f"annotations[{i}]")
        
        # Validate element annotations
        def validate_element_annotations(element: ContentElement, path: str) -> None:
            for i, annotation in enumerate(element.annotations):
                validate_annotation(annotation, f"{path}.annotations[{i}]")
        
        # Check annotations on content elements
        for i, element in enumerate(model.content):
            validate_element_annotations(element, f"content[{i}]")
        
        # Check annotations in sections
        def validate_section_annotations(section: Section, path: str) -> None:
            for i, element in enumerate(section.content_elements):
                validate_element_annotations(element, f"{path}.content_elements[{i}]")
            
            for i, subsection in enumerate(section.subsections):
                validate_section_annotations(subsection, f"{path}.subsections[{i}]")
        
        for i, section in enumerate(model.structure.sections):
            validate_section_annotations(section, f"structure.sections[{i}]")
        
        return errors

    def _validate_references(self, model: DocumentModel) -> List[ValidationError]:
        """Validate internal references and relationships."""
        errors = []
        
        # Collect all valid reference targets
        element_ids: Set[str] = set()
        section_ids: Set[str] = set()
        
        def collect_ids(section: Section) -> None:
            section_ids.add(section.id)
            for element in section.content_elements:
                element_ids.add(element.id)
            for subsection in section.subsections:
                collect_ids(subsection)
        
        # Collect IDs from main content
        for element in model.content:
            element_ids.add(element.id)
        
        # Collect IDs from sections
        for section in model.structure.sections:
            collect_ids(section)
        
        # Validate all references point to valid targets
        def validate_reference(ref_id: str, ref_type: str, path: str) -> None:
            valid_ids = element_ids if ref_type == "element" else section_ids
            if ref_id not in valid_ids:
                errors.append(ValidationError(
                    path=path,
                    message=f"Invalid {ref_type} reference: {ref_id}"
                ))
        
        # Check TOC references
        for i, entry in enumerate(model.structure.toc.entries):
            section_id = entry.get("section_id")
            if section_id:
                validate_reference(
                    section_id,
                    "section",
                    f"structure.toc.entries[{i}].section_id"
                )
        
        # Check annotation references if they contain target IDs
        for i, annotation in enumerate(model.annotations):
            target_id = annotation.metadata.get("target_id")
            if target_id:
                validate_reference(
                    target_id,
                    "element",
                    f"annotations[{i}].metadata.target_id"
                )
        
        return errors
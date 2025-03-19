"""Converters for transforming external formats to document model.

This module provides converters that transform various external document formats
into our standardized document model format.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pipeline.models.base import (
    Annotation,
    ContentElement,
    DocumentMetadata,
    DocumentModel,
    DocumentSource,
    DocumentStructure,
    Section,
    SupportedFormats,
    CellElement,
    TableElement,
    TextElement,
    TextStyle
)

class PDFExtractConverter:
    """Converts Adobe PDF Services API extraction results to document model."""
    
    def convert(
        self,
        extract_data: Dict[str, Any],
        file_path: str,
        processor_version: str
    ) -> DocumentModel:
        """Convert PDF extraction data to document model.
        
        Args:
            extract_data: Adobe API extraction result
            file_path: Path to original PDF file
            processor_version: Version of the PDF processor
            
        Returns:
            Document model containing the extracted content
        """
        # Create document metadata
        metadata = self._create_metadata(extract_data, file_path, processor_version)
        
        # Convert structure (sections and TOC)
        structure = self._create_structure(extract_data)
        
        # Convert main content elements
        content = self._create_content_elements(extract_data)
        
        # Process annotations and other metadata
        annotations = self._create_annotations(extract_data)
        
        return DocumentModel(
            metadata=metadata,
            structure=structure,
            content=content,
            annotations=annotations
        )
    
    def _create_metadata(
        self,
        data: Dict[str, Any],
        file_path: str,
        processor_version: str
    ) -> DocumentMetadata:
        """Create document metadata from extraction data."""
        # Get basic metadata from document info
        doc_info = data.get('documentMetadata', {})
        
        metadata = DocumentMetadata(
            title=doc_info.get('title', Path(file_path).stem),
            source=DocumentSource(
                type=SupportedFormats.PDF,
                path=file_path
            ),
            authors=doc_info.get('author', '').split(';'),
            publication_date=None  # Adobe API doesn't provide reliable date
        )
        
        # Add extraction as first processing step
        metadata.processing_history.append({
            'step': 'pdf_extraction',
            'timestamp': datetime.now(),
            'processor': 'adobe_extract_api',
            'version': processor_version
        })
        
        # Store additional PDF metadata
        metadata.custom_metadata.update({
            'pdf_producer': doc_info.get('producer', ''),
            'pdf_creator': doc_info.get('creator', ''),
            'page_count': data.get('pageCount', 0)
        })
        
        return metadata
    
    def _create_structure(self, data: Dict[str, Any]) -> DocumentStructure:
        """Create document structure from extraction data."""
        structure = DocumentStructure()
        
        # Process TOC if available
        toc_items = data.get('toc', [])
        if toc_items:
            structure.toc.entries = self._convert_toc_items(toc_items)
            # Create sections from TOC
            structure.sections = self._create_sections_from_toc(toc_items)
        else:
            # Create sections from detected headings
            structure.sections = self._create_sections_from_headings(data)
            # Update TOC based on created sections
            structure.toc.entries = self._create_toc_from_sections(structure.sections)
            
        return structure
    
    def _convert_toc_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert TOC items to standard format."""
        entries = []
        
        for item in items:
            entry = {
                'title': item.get('title', ''),
                'section_id': str(uuid4()),  # Will be updated when sections are created
                'level': item.get('level', 1),
                'page': item.get('page', 1)
            }
            
            # Convert child items recursively
            children = item.get('children', [])
            if children:
                entry['children'] = self._convert_toc_items(children)
                
            entries.append(entry)
            
        return entries
    
    def _create_sections_from_toc(
        self,
        toc_items: List[Dict[str, Any]]
    ) -> List[Section]:
        """Create sections from TOC structure."""
        sections = []
        
        for item in toc_items:
            section = Section(
                id=str(uuid4()),
                title=item.get('title', ''),
                level=item.get('level', 1)
            )
            
            # Convert child items recursively
            children = item.get('children', [])
            if children:
                section.subsections = self._create_sections_from_toc(children)
                
            sections.append(section)
            
        return sections
    
    def _create_sections_from_headings(
        self,
        data: Dict[str, Any]
    ) -> List[Section]:
        """Create sections by analyzing heading elements."""
        sections = []
        current_section = None
        section_stack = []
        
        for element in data.get('elements', []):
            if element.get('role') == 'heading':
                level = element.get('headingLevel', 1)
                
                # Create new section
                section = Section(
                    id=str(uuid4()),
                    title=element.get('text', ''),
                    level=level
                )
                
                # Find appropriate parent section
                while section_stack and section_stack[-1].level >= level:
                    section_stack.pop()
                    
                if section_stack:
                    section_stack[-1].subsections.append(section)
                else:
                    sections.append(section)
                    
                section_stack.append(section)
                current_section = section
                
            elif current_section and element.get('role') == 'text':
                # Add text content to current section
                text_elem = self._create_text_element(element)
                current_section.content_elements.append(text_elem)
                
        return sections
    
    def _create_content_elements(self, data: Dict[str, Any]) -> List[ContentElement]:
        """Create content elements from extraction data."""
        elements = []
        
        for elem_data in data.get('elements', []):
            elem_type = elem_data.get('role', '')
            
            if elem_type == 'text':
                element = self._create_text_element(elem_data)
            elif elem_type == 'table':
                element = self._create_table_element(elem_data)
            # Add other element types as needed
            else:
                continue
                
            elements.append(element)
            
        return elements
    
    def _create_text_element(self, data: Dict[str, Any]) -> TextElement:
        """Create text element from extraction data."""
        # Extract style information
        style = TextStyle(
            bold=data.get('bold', False),
            italic=data.get('italic', False),
            underline=data.get('underline', False),
            font_size=data.get('fontSize'),
            font_family=data.get('font')
        )
        
        # Create text element
        element = TextElement(
            text=data.get('text', ''),
            style=style
        )
        
        # Add position annotation
        bounds = data.get('bounds', {})
        if bounds:
            position = Annotation(
                type='position',
                start=0,
                end=len(element.text),
                metadata={
                    'page': data.get('page', 1),
                    'bounds': bounds
                }
            )
            element.annotations.append(position)
            
        return element
    
    def _create_table_element(self, data: Dict[str, Any]) -> TableElement:
        """Create table element from extraction data."""
        # Extract table structure
        row_data = data.get('rows', [])
        rows = []
        
        for row in row_data:
            cells = []
            for cell in row:
                cell_element = CellElement(
                    id=str(uuid4()),
                    content=cell.get('text', ''),
                    colspan=cell.get('colspan', 1),
                    rowspan=cell.get('rowspan', 1)
                )
                cells.append(cell_element)
            rows.append(cells)
            
        # Create table element
        element = TableElement(rows=rows)
        
        # Add position annotation
        bounds = data.get('bounds', {})
        if bounds:
            position = Annotation(
                type='position',
                start=0,
                end=0,  # Tables don't have text length
                metadata={
                    'page': data.get('page', 1),
                    'bounds': bounds
                }
            )
            element.annotations.append(position)
            
        return element
    
    def _create_annotations(self, data: Dict[str, Any]) -> List[Annotation]:
        """Create document-level annotations from extraction data."""
        annotations = []
        
        # Add structural annotations
        for elem_data in data.get('elements', []):
            if elem_data.get('role') in ['header', 'footer']:
                annotation = Annotation(
                    type='structure',
                    start=0,
                    end=0,
                    metadata={
                        'role': elem_data['role'],
                        'page': elem_data.get('page', 1),
                        'bounds': elem_data.get('bounds', {})
                    }
                )
                annotations.append(annotation)
                
        return annotations

    def _create_toc_from_sections(self, sections: List[Section]) -> List[Dict[str, Any]]:
        """Create TOC entries from section structure.
        
        Args:
            sections: List of document sections
            
        Returns:
            List of TOC entries
        """
        entries = []
        
        for section in sections:
            entry = {
                'title': section.title,
                'section_id': section.id,
                'level': section.level
            }
            
            if section.subsections:
                entry['children'] = self._create_toc_from_sections(section.subsections)
                
            entries.append(entry)
            
        return entries
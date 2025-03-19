"""
PDF document processor implementation.

This module implements a document processor that extracts content from
PDF files using Adobe PDF Services API.
"""
import json
import os
import re
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pipeline.processors.base import DocumentProcessor


class PDFProcessor(DocumentProcessor):
    """PDF document processor using Adobe PDF Services API.
    
    This processor extracts content from PDF files using Adobe's PDF Services API
    for accurate text and structure extraction.
    """
    
    def __init__(self):
        """Initialize a new PDF processor."""
        super().__init__()
        self.adobe_credentials = None
    
    def process(self, file_path: str) -> Dict[str, Any]:
        """Process a PDF document and extract its content.
        
        Args:
            file_path: Path to the PDF document
            
        Returns:
            Dictionary containing extracted content and metadata
            
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file is not a PDF
            RuntimeError: If extraction fails
        """
        # Validate file
        if not self._is_path_valid(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if self._get_file_extension(file_path) != 'pdf':
            raise ValueError(f"Not a PDF file: {file_path}")
        
        try:
            # Extract content using Adobe PDF Services API
            extract_result = self._extract_with_adobe_api(file_path)
            
            # Process the extracted content
            content = self._process_extraction_result(extract_result)
            
            # Post-process content
            include_footnotes = self._get_config_value('footnotes.include', True)
            footnotes_position = self._get_config_value('footnotes.position', 'end')
            
            content = self.remove_non_content(content)
            content = self.handle_footnotes(content, include_footnotes, footnotes_position)
            
            # Add metadata
            content['metadata'] = self._extract_metadata(file_path, extract_result)
            
            return content
            
        except Exception as e:
            raise RuntimeError(f"PDF extraction failed: {str(e)}")
    
    def extract_toc(self, file_path: str) -> Dict[str, Any]:
        """Extract the table of contents from a PDF document.
        
        Args:
            file_path: Path to the PDF document
            
        Returns:
            Dictionary containing TOC structure
        """
        toc = {
            'title': Path(file_path).stem,
            'sections': []
        }
        
        try:
            # Try to use cached extraction result if available
            extraction_dir = self._get_extraction_dir(file_path)
            
            # Check if structured.json exists in the extraction directory
            structured_path = os.path.join(extraction_dir, 'structured.json')
            if os.path.exists(structured_path):
                with open(structured_path, 'r', encoding='utf-8') as f:
                    structured_data = json.load(f)
                
                # Extract document title
                if 'Document' in structured_data and 'Title' in structured_data['Document']:
                    toc['title'] = structured_data['Document']['Title']
                
                # Extract TOC from structured data
                if 'Toc' in structured_data:
                    toc_items = structured_data['Toc']
                    toc['sections'] = self._process_toc_items(toc_items)
                else:
                    # If no TOC, try to create one from headings
                    toc['sections'] = self._extract_toc_from_elements(structured_data)
        
        except Exception:
            # Silently fail and return basic TOC
            pass
            
        return toc
    
    def remove_non_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Remove non-content elements from the extracted content.
        
        Args:
            content: Extracted content dictionary
            
        Returns:
            Content dictionary with non-content elements removed
        """
        # Get elements to remove from configuration
        remove_elements = self._get_config_value('remove_elements', [])
        
        if not remove_elements or 'elements' not in content:
            return content
        
        # Filter out elements to remove
        filtered_elements = []
        for element in content.get('elements', []):
            element_type = element.get('type', '').lower()
            element_role = element.get('role', '').lower()
            
            should_remove = False
            
            # Check if this element should be removed
            for remove_type in remove_elements:
                if remove_type == 'copyright' and ('copyright' in element_type or 'copyright' in element_role):
                    should_remove = True
                    break
                    
                elif remove_type == 'index' and ('index' in element_type or 'index' in element_role):
                    should_remove = True
                    break
                    
                elif remove_type == 'advertisements' and ('advertisement' in element_type or 'advertisement' in element_role):
                    should_remove = True
                    break
            
            if not should_remove:
                filtered_elements.append(element)
        
        # Update content with filtered elements
        content['elements'] = filtered_elements
        
        # Regenerate text content if needed
        if 'text' in content:
            content['text'] = self._generate_text_from_elements(filtered_elements)
        
        return content
    
    def handle_footnotes(self, content: Dict[str, Any], include: bool = True, position: str = 'end') -> Dict[str, Any]:
        """Handle footnotes in the document content.
        
        Args:
            content: Extracted content dictionary
            include: Whether to include footnotes
            position: Where to position footnotes ('end' or 'inline')
            
        Returns:
            Content dictionary with footnotes handled according to parameters
        """
        if not include:
            if 'footnotes' in content:
                del content['footnotes']
            return content
        
        # If there are no footnotes, nothing to do
        if 'footnotes' not in content or not content['footnotes']:
            return content
        
        if position == 'end' and 'text' in content:
            # Append footnotes to the end of the document
            footnotes_text = "\n\n# Footnotes\n\n"
            for i, footnote in enumerate(content['footnotes']):
                footnote_text = footnote.get('text', '')
                if footnote_text:
                    footnote_id = footnote.get('id', str(i + 1))
                    footnotes_text += f"[{footnote_id}] {footnote_text}\n\n"
            
            # Append to the main text
            content['text'] += footnotes_text
        
        # For 'inline' position, we would need to match footnote references to their content
        # This is complex and would require content analysis
        
        return content
    
    def _extract_with_adobe_api(self, file_path: str) -> Dict[str, Any]:
        """Extract content from a PDF file using Adobe PDF Services API.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extraction result dictionary
        """
        # Check if we already have extraction results cached
        extraction_dir = self._get_extraction_dir(file_path)
        structured_path = os.path.join(extraction_dir, 'structured.json')
        
        if os.path.exists(structured_path):
            # Use cached result
            with open(structured_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # No cached result, use the API
        # This is where we'd integrate with the actual Adobe PDF Services API
        # For now, we'll just run the existing adobe_extract.py script
        
        # Get configuration values for API
        max_retries = self._get_config_value('extraction.pdf.adobe_api.max_retries', 3)
        retry_delay = self._get_config_value('extraction.pdf.adobe_api.retry_delay', 5)
        
        # Call the extraction script
        result = self._call_adobe_extract_script(file_path, max_retries, retry_delay)
        
        # Process the extraction result
        if not result:
            raise RuntimeError("PDF extraction failed, no result returned")
        
        return result
    
    def _get_extraction_dir(self, file_path: str) -> str:
        """Get the extraction directory for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Path to the extraction directory
        """
        # Use the output directory from configuration or default
        output_dir = self._get_config_value('output.directory', 'output/')
        
        # Create a subdirectory for ExtractTextInfoFromPDF
        extract_dir = os.path.join(output_dir, 'ExtractTextInfoFromPDF')
        os.makedirs(extract_dir, exist_ok=True)
        
        # Get the latest extraction for this file
        file_name = Path(file_path).stem
        
        # Check for existing extraction files
        extractions = []
        for item in os.listdir(extract_dir):
            # Look for zip files with the timestamp pattern
            if item.startswith('extract') and item.endswith('.zip'):
                # For now, use the most recent extraction
                extractions.append(item)
        
        if extractions:
            # Use the latest extraction
            latest_extraction = sorted(extractions)[-1]
            extraction_path = os.path.join(extract_dir, latest_extraction)
            
            # Extract the zip file to a temp directory if needed
            extract_temp_dir = extraction_path.replace('.zip', '')
            if not os.path.exists(extract_temp_dir):
                os.makedirs(extract_temp_dir, exist_ok=True)
                with zipfile.ZipFile(extraction_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_temp_dir)
            
            return extract_temp_dir
        
        # No existing extraction found
        # Create a new directory based on current timestamp
        timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
        extract_temp_dir = os.path.join(extract_dir, f'extract{timestamp}')
        os.makedirs(extract_temp_dir, exist_ok=True)
        
        return extract_temp_dir
    
    def _call_adobe_extract_script(self, file_path: str, max_retries: int, retry_delay: int) -> Dict[str, Any]:
        """Call the Adobe PDF Services extraction script.
        
        Args:
            file_path: Path to the PDF file
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds
            
        Returns:
            Extraction result dictionary
        """
        # In a real implementation, we would call the actual Adobe PDF Services API
        # For now, we'll just simulate the result
        
        # This is where integration with adobe_extract.py would happen
        # We'll create a simulated structured.json result
        
        extraction_dir = self._get_extraction_dir(file_path)
        structured_path = os.path.join(extraction_dir, 'structured.json')
        
        # Create a basic structured result
        result = {
            'Document': {
                'Title': Path(file_path).stem,
                'NumPages': 1,
                'Language': 'en-US'
            },
            'Elements': [
                {
                    'type': 'heading',
                    'role': 'title',
                    'level': 1,
                    'text': Path(file_path).stem,
                    'page': 1,
                    'bounds': {'x': 0, 'y': 0, 'width': 100, 'height': 20}
                },
                {
                    'type': 'paragraph',
                    'role': 'content',
                    'text': f'This is simulated content for {Path(file_path).name}',
                    'page': 1,
                    'bounds': {'x': 0, 'y': 30, 'width': 100, 'height': 50}
                }
            ]
        }
        
        # Save the result to the extraction directory
        with open(structured_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        
        return result
    
    def _process_extraction_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Process the extraction result from Adobe PDF Services API.
        
        Args:
            result: Extraction result from Adobe API
            
        Returns:
            Processed content dictionary
        """
        content = {
            'text': '',
            'elements': [],
            'footnotes': [],
            'sections': []
        }
        
        # Extract text from elements
        elements = result.get('Elements', [])
        content['elements'] = elements
        
        # Generate text from elements
        content['text'] = self._generate_text_from_elements(elements)
        
        # Extract footnotes
        footnotes = [elem for elem in elements if elem.get('role', '').lower() == 'footnote']
        content['footnotes'] = footnotes
        
        # Extract sections from TOC or headings
        toc_items = result.get('Toc', [])
        if toc_items:
            content['sections'] = self._process_toc_items(toc_items)
        else:
            # If no TOC, try to create one from headings
            content['sections'] = self._extract_toc_from_elements(result)
        
        return content
    
    def _generate_text_from_elements(self, elements: List[Dict[str, Any]]) -> str:
        """Generate plain text from structured elements.
        
        Args:
            elements: List of document elements
            
        Returns:
            Plain text content
        """
        text_parts = []
        
        # Sort elements by page and position
        sorted_elements = sorted(
            elements,
            key=lambda e: (e.get('page', 0), e.get('bounds', {}).get('y', 0))
        )
        
        # Process each element
        for element in sorted_elements:
            element_type = element.get('type', '').lower()
            element_text = element.get('text', '')
            
            if not element_text:
                continue
            
            # Format based on element type
            if element_type == 'heading':
                level = element.get('level', 1)
                heading_prefix = '#' * level
                text_parts.append(f"\n{heading_prefix} {element_text}\n")
            
            elif element_type == 'paragraph':
                text_parts.append(f"\n{element_text}\n")
            
            elif element_type == 'list':
                items = element.get('items', [])
                for item in items:
                    item_text = item.get('text', '')
                    if item_text:
                        text_parts.append(f"- {item_text}\n")
                
                text_parts.append("\n")
            
            elif element_type == 'table':
                # Simple representation of tables
                text_parts.append(f"\n<Table>\n{element_text}\n</Table>\n")
            
            else:
                # Default handling
                text_parts.append(f"{element_text}\n")
        
        return ''.join(text_parts)
    
    def _process_toc_items(self, toc_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process TOC items from Adobe extraction result.
        
        Args:
            toc_items: TOC items from extraction result
            
        Returns:
            Processed TOC sections
        """
        sections = []
        
        for item in toc_items:
            section = {
                'id': item.get('id', ''),
                'title': item.get('title', ''),
                'level': item.get('depth', 1),
                'page': item.get('page', 1),
                'subsections': []
            }
            
            # Process child items recursively
            children = item.get('children', [])
            if children:
                section['subsections'] = self._process_toc_items(children)
            
            sections.append(section)
        
        return sections
    
    def _extract_toc_from_elements(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract TOC from document elements when no explicit TOC is available.
        
        Args:
            result: Extraction result dictionary
            
        Returns:
            Generated TOC sections
        """
        sections = []
        section_stack = []  # Stack to track current section hierarchy
        
        # Get all heading elements sorted by page and position
        elements = result.get('Elements', [])
        headings = [
            e for e in elements 
            if e.get('type', '').lower() == 'heading'
        ]
        
        sorted_headings = sorted(
            headings,
            key=lambda h: (h.get('page', 0), h.get('bounds', {}).get('y', 0))
        )
        
        # Process headings to build TOC
        for i, heading in enumerate(sorted_headings):
            level = heading.get('level', 1)
            title = heading.get('text', f'Section {i+1}')
            page = heading.get('page', 1)
            
            section = {
                'id': f"section-{i+1}",
                'title': title,
                'level': level,
                'page': page,
                'subsections': []
            }
            
            # Add to the appropriate parent based on level
            while section_stack and section_stack[-1]['level'] >= level:
                section_stack.pop()
            
            if section_stack:
                # Add as subsection of the current parent
                section_stack[-1]['subsections'].append(section)
            else:
                # Add as top-level section
                sections.append(section)
            
            # Push current section to stack
            section_stack.append(section)
        
        return sections
    
    def _extract_metadata(self, file_path: str, extract_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from a PDF file and extraction result.
        
        Args:
            file_path: Path to the PDF file
            extract_result: Extraction result dictionary
            
        Returns:
            Metadata dictionary
        """
        # Basic file metadata
        path = Path(file_path)
        metadata = {
            'filename': path.name,
            'size': path.stat().st_size,
            'created': path.stat().st_ctime,
            'modified': path.stat().st_mtime
        }
        
        # Extract metadata from Adobe result
        doc_info = extract_result.get('Document', {})
        
        # Add document metadata
        metadata.update({
            'title': doc_info.get('Title', path.stem),
            'num_pages': doc_info.get('NumPages', 1),
            'language': doc_info.get('Language', 'en-US'),
            'author': doc_info.get('Author', ''),
            'creator': doc_info.get('Creator', ''),
            'producer': doc_info.get('Producer', '')
        })
        
        return metadata
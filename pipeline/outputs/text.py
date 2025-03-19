"""
Plain text output handler implementation.

This module provides an output handler that transforms normalized document
content into plain text format.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pipeline.core.output_handler import OutputHandler


class TextOutputHandler(OutputHandler):
    """Plain text output handler.
    
    This handler transforms normalized document content into plain text format,
    preserving document structure to the extent possible in plain text.
    """
    
    def format_name(self) -> str:
        """Get the name of the output format.
        
        Returns:
            Name of the output format
        """
        return "text"
    
    def write(self, content: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """Transform and write content to plain text format.
        
        Args:
            content: Normalized document content
            output_path: Optional path for the output file
                        If None, a default path will be generated
                        
        Returns:
            Path to the written text file
            
        Raises:
            ValueError: If content is not in the expected format
            IOError: If writing to the output path fails
        """
        if not content or not isinstance(content, dict):
            raise ValueError("Invalid content format: expected a dictionary")
        
        # Generate output path if not provided
        if not output_path:
            output_path = self._get_default_output_path(content)
            
        # Transform content to plain text
        text_content = self._transform_to_text(content)
        
        # Write to file
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Write content
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(text_content)
                
            return output_path
            
        except IOError as e:
            raise IOError(f"Failed to write text file: {str(e)}")
    
    def _transform_to_text(self, content: Dict[str, Any]) -> str:
        """Transform normalized content to plain text format.
        
        Args:
            content: Normalized document content
            
        Returns:
            Plain text formatted content
        """
        # If we already have raw text in the content, use it
        if 'text' in content and content['text']:
            # Strip any markdown formatting
            return self._strip_markdown(content['text'])
        
        # Otherwise, build text from structured elements
        text_parts = []
        
        # Add title
        metadata = content.get('metadata', {})
        title = metadata.get('title', '')
        if title:
            text_parts.append(f"{title}\n")
            text_parts.append("=" * len(title) + "\n\n")
        
        # Add metadata section if configured
        include_metadata = self._get_config_value('include_metadata', True)
        if include_metadata and metadata:
            text_parts.append("Document Information\n")
            text_parts.append("-" * 20 + "\n\n")
            
            # Filter metadata to include
            metadata_to_show = {
                'Author': metadata.get('author', ''),
                'Created': metadata.get('created', ''),
                'Language': metadata.get('language', '')
            }
            
            # Add to text document
            for key, value in metadata_to_show.items():
                if value:
                    text_parts.append(f"{key}: {value}\n")
                    
            text_parts.append("\n")
        
        # Process elements if available
        elements = content.get('elements', [])
        if elements:
            text_parts.extend(self._process_elements(elements))
        
        # Process sections if available
        sections = content.get('sections', [])
        if sections:
            text_parts.extend(self._process_sections(sections))
        
        return ''.join(text_parts)
    
    def _strip_markdown(self, text: str) -> str:
        """Strip markdown formatting from text.
        
        Args:
            text: Markdown formatted text
            
        Returns:
            Plain text with markdown formatting removed
        """
        # Replace headings with plain text
        import re
        
        # Replace headings
        text = re.sub(r'^#+\s+(.*?)$', r'\1\n' + '-' * 30, text, flags=re.MULTILINE)
        
        # Replace bold/italic
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        
        # Replace links
        text = re.sub(r'\[(.*?)\]\((.*?)\)', r'\1 (\2)', text)
        
        # Replace images
        text = re.sub(r'!\[(.*?)\]\((.*?)\)', r'[Image: \1]', text)
        
        # Replace code blocks
        text = re.sub(r'```(?:.*?)\n(.*?)```', r'\1', text, flags=re.DOTALL)
        
        # Replace inline code
        text = re.sub(r'`(.*?)`', r'\1', text)
        
        # Replace lists
        text = re.sub(r'^\s*[-*+]\s+(.*?)$', r'  • \1', text, flags=re.MULTILINE)
        
        return text
    
    def _process_elements(self, elements: List[Dict[str, Any]]) -> List[str]:
        """Process content elements into plain text.
        
        Args:
            elements: List of content elements
            
        Returns:
            List of text formatted strings
        """
        text_parts = []
        
        # Sort elements by position or page/order
        def get_element_position(elem):
            if 'position' in elem:
                return elem['position']
            elif 'page' in elem and 'bounds' in elem:
                return (elem['page'], elem['bounds'].get('y', 0))
            else:
                return 0
                
        sorted_elements = sorted(elements, key=get_element_position)
        
        # Process each element
        for elem in sorted_elements:
            elem_type = elem.get('type', '').lower()
            text = elem.get('text', '')
            
            if not text:
                continue
                
            if elem_type == 'heading':
                level = elem.get('level', 1)
                text_parts.append(f"\n{text}\n")
                
                # Underline based on heading level
                if level == 1:
                    text_parts.append("=" * len(text) + "\n\n")
                elif level == 2:
                    text_parts.append("-" * len(text) + "\n\n")
                else:
                    text_parts.append("." * len(text) + "\n\n")
                
            elif elem_type == 'paragraph':
                text_parts.append(f"{text}\n\n")
                
            elif elem_type == 'list':
                items = elem.get('items', [])
                for item in items:
                    item_text = item.get('text', '')
                    if item_text:
                        text_parts.append(f"  • {item_text}\n")
                text_parts.append("\n")
                
            elif elem_type == 'table':
                # Simple representation of tables
                text_parts.append("\n")
                rows = elem.get('rows', [])
                if rows:
                    # Determine column widths
                    if 'header' in elem:
                        all_rows = [elem['header']] + rows
                    else:
                        all_rows = rows
                        
                    col_widths = []
                    for row in all_rows:
                        for i, cell in enumerate(row):
                            width = len(str(cell))
                            if i >= len(col_widths):
                                col_widths.append(width)
                            else:
                                col_widths[i] = max(col_widths[i], width)
                    
                    # Create header
                    if 'header' in elem:
                        header = elem['header']
                        header_str = "  ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(header))
                        text_parts.append(header_str + "\n")
                        text_parts.append("  ".join("-" * w for w in col_widths) + "\n")
                    
                    # Create rows
                    for row in rows:
                        row_str = "  ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
                        text_parts.append(row_str + "\n")
                    
                    text_parts.append("\n")
                else:
                    # Fallback for unstructured tables
                    text_parts.append(f"{text}\n\n")
                    
            elif elem_type == 'code':
                text_parts.append("\n--- Code ---\n")
                text_parts.append(f"{text}\n")
                text_parts.append("------------\n\n")
                
            elif elem_type == 'image':
                alt_text = elem.get('alt_text', '')
                text_parts.append(f"[Image: {alt_text}]\n\n")
                    
            elif elem_type == 'link':
                url = elem.get('url', '')
                if url:
                    text_parts.append(f"{text} ({url})\n\n")
                else:
                    text_parts.append(f"{text}\n\n")
                    
            else:
                # Default handling for other element types
                text_parts.append(f"{text}\n\n")
                
        return text_parts
    
    def _process_sections(self, sections: List[Dict[str, Any]], level: int = 1) -> List[str]:
        """Process document sections into plain text.
        
        Args:
            sections: List of section dictionaries
            level: Current heading level
            
        Returns:
            List of text formatted strings
        """
        text_parts = []
        
        for section in sections:
            title = section.get('title', '')
            
            if title:
                text_parts.append(f"\n{title}\n")
                
                # Underline based on heading level
                if level == 1:
                    text_parts.append("=" * len(title) + "\n\n")
                elif level == 2:
                    text_parts.append("-" * len(title) + "\n\n")
                else:
                    text_parts.append("." * len(title) + "\n\n")
                
            # Process subsections recursively
            subsections = section.get('subsections', [])
            if subsections:
                text_parts.extend(self._process_sections(subsections, level + 1))
                
        return text_parts
        
    def _get_format_extension(self) -> str:
        """Get the file extension for this output format.
        
        Returns:
            File extension without the leading dot
        """
        return "txt"
"""
Markdown output handler implementation.

This module provides an output handler that transforms normalized document
content into Markdown format.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pipeline.core.output_handler import OutputHandler


class MarkdownOutputHandler(OutputHandler):
    """Markdown output handler.
    
    This handler transforms normalized document content into Markdown format,
    preserving document structure and formatting.
    """
    
    def format_name(self) -> str:
        """Get the name of the output format.
        
        Returns:
            Name of the output format
        """
        return "markdown"
    
    def write(self, content: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """Transform and write content to Markdown format.
        
        Args:
            content: Normalized document content
            output_path: Optional path for the output file
                        If None, a default path will be generated
                        
        Returns:
            Path to the written Markdown file
            
        Raises:
            ValueError: If content is not in the expected format
            IOError: If writing to the output path fails
        """
        if not content or not isinstance(content, dict):
            raise ValueError("Invalid content format: expected a dictionary")
        
        # Generate output path if not provided
        if not output_path:
            output_path = self._get_default_output_path(content)
            
        # Transform content to Markdown
        markdown_content = self._transform_to_markdown(content)
        
        # Write to file
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Write content
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
                
            return output_path
            
        except IOError as e:
            raise IOError(f"Failed to write Markdown file: {str(e)}")
    
    def _transform_to_markdown(self, content: Dict[str, Any]) -> str:
        """Transform normalized content to Markdown format.
        
        Args:
            content: Normalized document content
            
        Returns:
            Markdown formatted content
        """
        # If we already have markdown text in the content, use it
        if 'text' in content and content['text']:
            return content['text']
        
        # Otherwise, build markdown from structured elements
        markdown_parts = []
        
        # Add title
        metadata = content.get('metadata', {})
        title = metadata.get('title', '')
        if title:
            markdown_parts.append(f"# {title}\n\n")
        
        # Add metadata section if configured
        include_metadata = self._get_config_value('include_metadata', True)
        if include_metadata and metadata:
            markdown_parts.append("## Document Information\n\n")
            
            # Filter metadata to include
            metadata_to_show = {
                'Author': metadata.get('author', ''),
                'Created': metadata.get('created', ''),
                'Language': metadata.get('language', '')
            }
            
            # Add to markdown document
            for key, value in metadata_to_show.items():
                if value:
                    markdown_parts.append(f"- **{key}**: {value}\n")
                    
            markdown_parts.append("\n")
        
        # Process elements if available
        elements = content.get('elements', [])
        if elements:
            markdown_parts.extend(self._process_elements(elements))
        
        # Process sections if available
        sections = content.get('sections', [])
        if sections:
            markdown_parts.extend(self._process_sections(sections))
        
        return ''.join(markdown_parts)
    
    def _process_elements(self, elements: List[Dict[str, Any]]) -> List[str]:
        """Process content elements into Markdown.
        
        Args:
            elements: List of content elements
            
        Returns:
            List of Markdown formatted strings
        """
        markdown_parts = []
        
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
                heading_marker = '#' * min(level, 6)  # Markdown supports up to 6 levels
                markdown_parts.append(f"{heading_marker} {text}\n\n")
                
            elif elem_type == 'paragraph':
                markdown_parts.append(f"{text}\n\n")
                
            elif elem_type == 'list':
                items = elem.get('items', [])
                for item in items:
                    item_text = item.get('text', '')
                    if item_text:
                        markdown_parts.append(f"- {item_text}\n")
                markdown_parts.append("\n")
                
            elif elem_type == 'table':
                # Simple table representation
                rows = elem.get('rows', [])
                if rows:
                    # Create header
                    if 'header' in elem:
                        header = elem['header']
                        markdown_parts.append("| " + " | ".join(header) + " |\n")
                        markdown_parts.append("| " + " | ".join(["---"] * len(header)) + " |\n")
                    
                    # Create rows
                    for row in rows:
                        markdown_parts.append("| " + " | ".join(row) + " |\n")
                    
                    markdown_parts.append("\n")
                else:
                    # Fallback for unstructured tables
                    markdown_parts.append(f"```\n{text}\n```\n\n")
                    
            elif elem_type == 'code':
                language = elem.get('language', '')
                markdown_parts.append(f"```{language}\n{text}\n```\n\n")
                
            elif elem_type == 'image':
                alt_text = elem.get('alt_text', '')
                url = elem.get('url', '')
                if url:
                    markdown_parts.append(f"![{alt_text}]({url})\n\n")
                    
            elif elem_type == 'link':
                url = elem.get('url', '')
                if url:
                    markdown_parts.append(f"[{text}]({url})\n\n")
                    
            else:
                # Default handling for other element types
                markdown_parts.append(f"{text}\n\n")
                
        return markdown_parts
    
    def _process_sections(self, sections: List[Dict[str, Any]], level: int = 1) -> List[str]:
        """Process document sections into Markdown.
        
        Args:
            sections: List of section dictionaries
            level: Current heading level
            
        Returns:
            List of Markdown formatted strings
        """
        markdown_parts = []
        
        for section in sections:
            title = section.get('title', '')
            
            if title:
                heading_level = min(level, 6)  # Markdown supports up to 6 levels
                heading_marker = '#' * heading_level
                markdown_parts.append(f"{heading_marker} {title}\n\n")
                
            # Process subsections recursively
            subsections = section.get('subsections', [])
            if subsections:
                markdown_parts.extend(self._process_sections(subsections, level + 1))
                
        return markdown_parts
        
    def _get_format_extension(self) -> str:
        """Get the file extension for this output format.
        
        Returns:
            File extension without the leading dot
        """
        return "md"
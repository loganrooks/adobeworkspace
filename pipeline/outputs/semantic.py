"""
Semantic Search output handler implementation.

This module provides an output handler that transforms normalized document
content into chunks optimized for semantic search and vector databases.
"""
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pipeline.core.output_handler import OutputHandler


class SemanticOutputHandler(OutputHandler):
    """Semantic search output handler.
    
    This handler transforms normalized document content into chunks optimized
    for semantic search and embedding in vector databases, with metadata for
    context preservation.
    """
    
    def format_name(self) -> str:
        """Get the name of the output format.
        
        Returns:
            Name of the output format
        """
        return "semantic"
    
    def write(self, content: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """Transform and write content to semantic search format.
        
        Args:
            content: Normalized document content
            output_path: Optional path for the output file
                        If None, a default path will be generated
                        
        Returns:
            Path to the written output file
            
        Raises:
            ValueError: If content is not in the expected format
            IOError: If writing to the output path fails
        """
        if not content or not isinstance(content, dict):
            raise ValueError("Invalid content format: expected a dictionary")
        
        # Generate output path if not provided
        if not output_path:
            output_path = self._get_default_output_path(content)
            
        # Transform content to semantic chunks
        semantic_chunks = self._transform_to_semantic_chunks(content)
        
        # Write to file (JSON format)
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Write content
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(semantic_chunks, f, indent=2, ensure_ascii=False)
                
            return output_path
            
        except IOError as e:
            raise IOError(f"Failed to write semantic chunks file: {str(e)}")
    
    def _transform_to_semantic_chunks(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Transform normalized content to semantic search chunks.
        
        Args:
            content: Normalized document content
            
        Returns:
            Dictionary with document metadata and chunked content
        """
        # Prepare result structure
        result = {
            "metadata": self._extract_metadata(content),
            "chunks": []
        }
        
        # Get chunking configuration
        chunking_strategy = self._get_config_value('chunking.strategy', 'semantic_overlap')
        max_chunk_size = self._get_config_value('chunking.max_chunk_size', 2048)
        overlap_tokens = self._get_config_value('chunking.overlap_tokens', 200)
        
        # If we have structured content (elements), use that for chunking
        if 'elements' in content and content['elements']:
            result["chunks"] = self._chunk_elements(
                content['elements'], 
                chunking_strategy, 
                max_chunk_size, 
                overlap_tokens
            )
        # Otherwise use the raw text
        elif 'text' in content and content['text']:
            result["chunks"] = self._chunk_text(
                content['text'], 
                chunking_strategy, 
                max_chunk_size, 
                overlap_tokens
            )
        # If we have sections, use those for chunking
        elif 'sections' in content and content['sections']:
            result["chunks"] = self._chunk_sections(
                content['sections'],
                chunking_strategy,
                max_chunk_size,
                overlap_tokens
            )
            
        return result
    
    def _extract_metadata(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata for the semantic output.
        
        Args:
            content: Normalized document content
            
        Returns:
            Dictionary with metadata
        """
        # Start with content metadata
        metadata = content.get('metadata', {}).copy()
        
        # Add structure info if available
        if 'sections' in content and content['sections']:
            metadata['has_structure'] = True
            metadata['section_count'] = self._count_sections(content['sections'])
        else:
            metadata['has_structure'] = False
        
        # Add element counts if available
        if 'elements' in content and content['elements']:
            element_types = {}
            for elem in content['elements']:
                elem_type = elem.get('type', '').lower()
                if elem_type:
                    element_types[elem_type] = element_types.get(elem_type, 0) + 1
            
            metadata['element_counts'] = element_types
        
        # Add text length if available
        if 'text' in content and content['text']:
            metadata['text_length'] = len(content['text'])
            metadata['word_count'] = len(content['text'].split())
            
        return metadata
    
    def _count_sections(self, sections: List[Dict[str, Any]]) -> int:
        """Count total sections including subsections.
        
        Args:
            sections: List of section dictionaries
            
        Returns:
            Total number of sections
        """
        count = len(sections)
        
        for section in sections:
            subsections = section.get('subsections', [])
            if subsections:
                count += self._count_sections(subsections)
                
        return count
    
    def _chunk_text(self, text: str, strategy: str, max_size: int, overlap: int) -> List[Dict[str, Any]]:
        """Chunk raw text based on the specified strategy.
        
        Args:
            text: Text to chunk
            strategy: Chunking strategy
            max_size: Maximum chunk size (in tokens/chars)
            overlap: Overlap between chunks (in tokens/chars)
            
        Returns:
            List of chunk dictionaries
        """
        chunks = []
        
        if strategy == 'semantic_overlap':
            # Split by paragraphs first
            paragraphs = re.split(r'\n\s*\n', text)
            current_chunk = ""
            current_chunk_size = 0
            
            for i, paragraph in enumerate(paragraphs):
                # Estimate size (tokens ≈ words)
                paragraph_size = len(paragraph.split())
                
                # If adding this paragraph exceeds the limit, create a new chunk
                if current_chunk_size + paragraph_size > max_size and current_chunk:
                    # Create the chunk
                    chunks.append({
                        "id": f"chunk-{len(chunks)+1}",
                        "content": current_chunk,
                        "size": current_chunk_size,
                        "metadata": {
                            "index": len(chunks)
                        }
                    })
                    
                    # Start a new chunk with overlap
                    # Get the last few sentences for overlap
                    sentences = re.split(r'(?<=[.!?])\s+', current_chunk)
                    overlap_text = ""
                    remaining_overlap = overlap
                    
                    # Add sentences from end until we reach the overlap
                    for sentence in reversed(sentences):
                        sentence_size = len(sentence.split())
                        if remaining_overlap > sentence_size:
                            overlap_text = sentence + " " + overlap_text
                            remaining_overlap -= sentence_size
                        else:
                            break
                            
                    current_chunk = overlap_text + "\n\n" + paragraph
                    current_chunk_size = len(current_chunk.split())
                else:
                    # Add to the current chunk
                    if current_chunk:
                        current_chunk += "\n\n" + paragraph
                    else:
                        current_chunk = paragraph
                    current_chunk_size += paragraph_size
            
            # Add the last chunk if not empty
            if current_chunk:
                chunks.append({
                    "id": f"chunk-{len(chunks)+1}",
                    "content": current_chunk,
                    "size": current_chunk_size,
                    "metadata": {
                        "index": len(chunks)
                    }
                })
                
        elif strategy == 'fixed_size':
            # Simple fixed-size chunking with overlap
            words = text.split()
            chunk_start = 0
            
            while chunk_start < len(words):
                # Get chunk end position
                chunk_end = min(chunk_start + max_size, len(words))
                
                # Get the chunk text
                chunk_text = ' '.join(words[chunk_start:chunk_end])
                
                # Create the chunk
                chunks.append({
                    "id": f"chunk-{len(chunks)+1}",
                    "content": chunk_text,
                    "size": len(chunk_text.split()),
                    "metadata": {
                        "index": len(chunks),
                        "start_pos": chunk_start,
                        "end_pos": chunk_end
                    }
                })
                
                # Move to next chunk with overlap
                chunk_start = chunk_end - overlap
                if chunk_start >= len(words):
                    break
        
        return chunks
    
    def _chunk_elements(self, elements: List[Dict[str, Any]], strategy: str, max_size: int, overlap: int) -> List[Dict[str, Any]]:
        """Chunk document elements based on the specified strategy.
        
        Args:
            elements: Document elements
            strategy: Chunking strategy
            max_size: Maximum chunk size (in tokens/chars)
            overlap: Overlap between chunks (in tokens/chars)
            
        Returns:
            List of chunk dictionaries
        """
        chunks = []
        
        # Sort elements by position or page/order
        def get_element_position(elem):
            if 'position' in elem:
                return elem['position']
            elif 'page' in elem and 'bounds' in elem:
                return (elem['page'], elem['bounds'].get('y', 0))
            else:
                return 0
                
        sorted_elements = sorted(elements, key=get_element_position)
        
        # Track the current chunk
        current_chunk_text = ""
        current_chunk_elements = []
        current_chunk_size = 0
        current_heading_stack = []  # Track heading hierarchy
        
        for elem in sorted_elements:
            elem_type = elem.get('type', '').lower()
            text = elem.get('text', '')
            
            if not text:
                continue
                
            # Estimate size (tokens ≈ words)
            elem_size = len(text.split())
            
            # Check if this is a heading
            if elem_type == 'heading':
                level = elem.get('level', 1)
                
                # Update heading stack
                # Remove any headings of same or lower level
                current_heading_stack = [h for h in current_heading_stack if h['level'] < level]
                
                # Add this heading
                current_heading_stack.append({
                    'level': level,
                    'text': text,
                    'id': elem.get('id', '')
                })
                
                # If we have content, complete the current chunk
                if current_chunk_size > 0:
                    chunks.append(self._create_chunk_from_elements(
                        current_chunk_elements, 
                        current_chunk_text,
                        current_chunk_size, 
                        len(chunks),
                        list(current_heading_stack)  # Copy the stack
                    ))
                    
                    current_chunk_text = ""
                    current_chunk_elements = []
                    current_chunk_size = 0
                
                # Add heading to new chunk
                current_chunk_text += f"{'#' * level} {text}\n\n"
                current_chunk_elements.append(elem)
                current_chunk_size += elem_size
                
            elif current_chunk_size + elem_size > max_size and current_chunk_size > 0:
                # This element would exceed the chunk size, create a new chunk
                chunks.append(self._create_chunk_from_elements(
                    current_chunk_elements, 
                    current_chunk_text,
                    current_chunk_size, 
                    len(chunks),
                    list(current_heading_stack)  # Copy the stack
                ))
                
                # Start a new chunk with context
                context_text = ""
                if current_heading_stack:
                    # Add headings as context
                    for heading in current_heading_stack:
                        level_marker = '#' * heading['level']
                        context_text += f"{level_marker} {heading['text']}\n\n"
                
                current_chunk_text = context_text + text
                current_chunk_elements = [elem]
                current_chunk_size = len(context_text.split()) + elem_size
                
            else:
                # Add to current chunk
                if elem_type == 'paragraph':
                    current_chunk_text += f"{text}\n\n"
                elif elem_type == 'list':
                    items = elem.get('items', [])
                    for item in items:
                        item_text = item.get('text', '')
                        if item_text:
                            current_chunk_text += f"- {item_text}\n"
                    current_chunk_text += "\n"
                else:
                    current_chunk_text += f"{text}\n\n"
                    
                current_chunk_elements.append(elem)
                current_chunk_size += elem_size
        
        # Add the last chunk if not empty
        if current_chunk_size > 0:
            chunks.append(self._create_chunk_from_elements(
                current_chunk_elements, 
                current_chunk_text,
                current_chunk_size, 
                len(chunks),
                list(current_heading_stack)  # Copy the stack
            ))
            
        return chunks
    
    def _create_chunk_from_elements(
            self, 
            elements: List[Dict[str, Any]], 
            text: str, 
            size: int, 
            index: int,
            context: List[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
        """Create a chunk dictionary from elements.
        
        Args:
            elements: Elements in the chunk
            text: Text representation of the chunk
            size: Size of the chunk (token/word count)
            index: Index of the chunk in sequence
            context: Context information (heading stack)
            
        Returns:
            Chunk dictionary
        """
        # Create element type counts
        element_types = {}
        for elem in elements:
            elem_type = elem.get('type', '').lower()
            if elem_type:
                element_types[elem_type] = element_types.get(elem_type, 0) + 1
                
        # Create chunk metadata
        metadata = {
            "index": index,
            "element_count": len(elements),
            "element_types": element_types
        }
        
        # Add context if available
        if context:
            metadata["context"] = context
            
            # Create breadcrumb from context
            if len(context) > 0:
                breadcrumb = []
                for heading in context:
                    breadcrumb.append(heading['text'])
                metadata["breadcrumb"] = " > ".join(breadcrumb)
        
        return {
            "id": f"chunk-{index+1}",
            "content": text,
            "size": size,
            "metadata": metadata
        }
    
    def _chunk_sections(self, sections: List[Dict[str, Any]], strategy: str, max_size: int, overlap: int) -> List[Dict[str, Any]]:
        """Chunk document sections based on the specified strategy.
        
        Args:
            sections: Document sections
            strategy: Chunking strategy
            max_size: Maximum chunk size (in tokens/chars)
            overlap: Overlap between chunks (in tokens/chars)
            
        Returns:
            List of chunk dictionaries
        """
        chunks = []
        
        # Process each section recursively
        for section in sections:
            # Process this section
            title = section.get('title', '')
            section_chunks = []
            
            # Get content for this section
            section_text = ""
            if title:
                section_text = f"# {title}\n\n"
                
            # For now, since we don't have section content, just create a chunk with the title
            if section_text:
                size = len(section_text.split())
                section_chunks.append({
                    "id": f"chunk-{len(chunks) + len(section_chunks) + 1}",
                    "content": section_text,
                    "size": size,
                    "metadata": {
                        "index": len(chunks) + len(section_chunks),
                        "section_id": section.get('id', ''),
                        "section_title": title,
                        "section_level": section.get('level', 1)
                    }
                })
            
            # Process subsections recursively
            subsections = section.get('subsections', [])
            if subsections:
                subsection_chunks = self._chunk_sections(subsections, strategy, max_size, overlap)
                
                # Set parent section in metadata
                for chunk in subsection_chunks:
                    chunk["metadata"]["parent_section"] = title
                    
                section_chunks.extend(subsection_chunks)
            
            # Add to result
            chunks.extend(section_chunks)
            
        return chunks
        
    def _get_format_extension(self) -> str:
        """Get the file extension for this output format.
        
        Returns:
            File extension without the leading dot
        """
        return "json"
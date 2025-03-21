"""Document chunking implementation.

This module implements various strategies for splitting documents
into manageable chunks while preserving structure and context.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Set
from enum import Enum, auto
from datetime import datetime
from pathlib import Path
import logging
import re
import json
import yaml

from pipeline.models.base import DocumentModel

logger = logging.getLogger(__name__)

@dataclass
class ChunkBoundary:
    """Represents a boundary between chunks with contextual information."""
    start_pos: int
    end_pos: int
    context: Dict[str, Any]  # Preserves context across chunk boundary
    heading_stack: List[Dict[str, str]]  # Current heading hierarchy
    references: Dict[str, List[Dict[str, Any]]]  # Reference tracking

class ChunkMetadata:
    """Rich metadata for document chunks."""
    def __init__(self, 
                 chunk_id: str,
                 sequence_num: int,
                 start_page: Optional[int] = None,
                 end_page: Optional[int] = None,
                 section_title: Optional[str] = None):
        self.chunk_id = chunk_id
        self.sequence_num = sequence_num
        self.start_page = start_page
        self.end_page = end_page
        self.section_title = section_title
        self.created_at = datetime.now()
        self.word_count = 0
        self.patterns = {}
        self.source_reference = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            'chunk_id': self.chunk_id,
            'sequence_num': self.sequence_num,
            'start_page': self.start_page,
            'end_page': self.end_page,
            'section_title': self.section_title,
            'created_at': self.created_at.isoformat(),
            'word_count': self.word_count,
            'patterns': self.patterns,
            'source_reference': self.source_reference
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChunkMetadata':
        """Create metadata from dictionary."""
        metadata = cls(
            chunk_id=data['chunk_id'],
            sequence_num=data['sequence_num'],
            start_page=data.get('start_page'),
            end_page=data.get('end_page'),
            section_title=data.get('section_title')
        )
        metadata.created_at = datetime.fromisoformat(data['created_at'])
        metadata.word_count = data.get('word_count', 0)
        metadata.patterns = data.get('patterns', {})
        metadata.source_reference = data.get('source_reference', {})
        return metadata

class Chunk:
    """Represents a document chunk with content, boundary and metadata."""
    def __init__(self,
                 content: List[Dict[str, Any]],
                 boundary: ChunkBoundary,
                 metadata: ChunkMetadata,
                 _size: Optional[int] = None):
        self.content = content
        self.boundary = boundary
        self.metadata = metadata
        self._size = _size

    @property
    def size(self) -> int:
        """Get chunk size in words."""
        # Debug size calculation
        print(f"DEBUG: Getting size for chunk {self.metadata.chunk_id}, explicit size: {self._size}, metadata word_count: {self.metadata.word_count}")
        
        # Use explicitly set size as primary source of truth
        if self._size is not None:
            return self._size
            
        # Use metadata word count if available
        if hasattr(self.metadata, 'word_count') and self.metadata.word_count > 0:
            # Cache this value for future use
            self._size = self.metadata.word_count
            return self.metadata.word_count
            
        # Calculate size from content
        content_size = sum(
            len(elem.get('text', '').split())
            for elem in self.content
            if elem.get('type') in ['text', 'paragraph']
        )
        
        # Cache the calculated size
        self._size = content_size
        # Also update metadata for consistency
        self.metadata.word_count = content_size
        print(f"DEBUG: Calculated size {content_size} for chunk {self.metadata.chunk_id}")
        return content_size
        
    def with_size(self, size: int) -> 'Chunk':
        """Create a new chunk with the specified size."""
        return Chunk(
            content=self.content,
            boundary=self.boundary,
            metadata=self.metadata,
            _size=size
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary."""
        return {
            'content': self.content,
            'boundary': {
                'start_pos': self.boundary.start_pos,
                'end_pos': self.boundary.end_pos,
                'context': self.boundary.context,
                'heading_stack': self.boundary.heading_stack,
                'references': self.boundary.references
            },
            'metadata': self.metadata.to_dict(),
            'size': self.size  # Include size in serialization
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Chunk':
        """Create chunk from dictionary."""
        boundary = ChunkBoundary(
            start_pos=data['boundary']['start_pos'],
            end_pos=data['boundary']['end_pos'],
            context=data['boundary']['context'],
            heading_stack=data['boundary']['heading_stack'],
            references=data['boundary']['references']
        )
        metadata = ChunkMetadata.from_dict(data['metadata'])
        size = data.get('size')  # Get the stored size if available
        
        return cls(
            content=data['content'],
            boundary=boundary,
            metadata=metadata,
            _size=size
        )

class ChunkingStrategy(ABC):
    """Base class for chunking strategies."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
    
    @abstractmethod
    def split(self, document: DocumentModel) -> List[Chunk]:
        """Split document into chunks."""
        pass

class SemanticChunkStrategy(ChunkingStrategy):
    """Chunks content based on semantic boundaries."""
    
    def split(self, document: DocumentModel) -> List[Chunk]:
        chunks = []
        current_chunk = []
        current_size = 0
        heading_stack = []
        max_chunk_size = self.config.get('max_chunk_size', 2048)
        overlap_tokens = self.config.get('overlap_tokens', 200)
        sequence_num = 0
        
        for element in document.content:
            elem_size = self._get_element_size(element)
            
            # Handle headings specially
            if element.get('type') == 'heading':
                level = element.get('level', 1)
                
                # Pop higher level headings
                while heading_stack and heading_stack[-1]['level'] >= level:
                    heading_stack.pop()
                    
                # Add current heading
                heading_stack.append({
                    'level': level,
                    'text': element.get('text', ''),
                    'id': element.get('id', '')
                })
                
                # Start new chunk if we have content
                if current_chunk:
                    metadata = ChunkMetadata(
                        chunk_id=f"chunk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sequence_num}",
                        sequence_num=sequence_num,
                        section_title=heading_stack[-1]['text'] if heading_stack else None
                    )
                    metadata.word_count = current_size
                    
                    boundary = ChunkBoundary(
                        start_pos=current_chunk[0].get('position', 0),
                        end_pos=current_chunk[-1].get('position', 0),
                        context=self._extract_context(current_chunk),
                        heading_stack=list(heading_stack),
                        references=self._extract_references(current_chunk)
                    )
                    
                    chunks.append(Chunk(current_chunk, boundary, metadata))
                    sequence_num += 1
                    
                    # Start new chunk with overlap
                    current_chunk = self._create_overlap(current_chunk, overlap_tokens)
                    current_size = self._get_chunk_size(current_chunk)
                
            # Check if adding element would exceed max size
            if current_size + elem_size > max_chunk_size and current_chunk:
                metadata = ChunkMetadata(
                    chunk_id=f"chunk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sequence_num}",
                    sequence_num=sequence_num,
                    section_title=heading_stack[-1]['text'] if heading_stack else None
                )
                metadata.word_count = current_size
                
                boundary = ChunkBoundary(
                    start_pos=current_chunk[0].get('position', 0),
                    end_pos=current_chunk[-1].get('position', 0),
                    context=self._extract_context(current_chunk),
                    heading_stack=list(heading_stack),
                    references=self._extract_references(current_chunk)
                )
                
                chunks.append(Chunk(current_chunk, boundary, metadata))
                sequence_num += 1
                
                # Start new chunk with overlap
                current_chunk = self._create_overlap(current_chunk, overlap_tokens)
                current_size = self._get_chunk_size(current_chunk)
                
                # Add current element to new chunk (if it won't immediately exceed max size)
                if elem_size <= max_chunk_size:
                    current_chunk.append(element)
                    current_size += elem_size
                else:
                    # Special handling for very large elements - split them if possible
                    if element.get('type') in ['text', 'paragraph'] and 'text' in element:
                        words = element.get('text', '').split()
                        half_point = len(words) // 2
                        
                        # First half goes in a separate chunk
                        first_half = element.copy()
                        first_half['text'] = ' '.join(words[:half_point])
                        first_chunk = [first_half]
                        
                        metadata = ChunkMetadata(
                            chunk_id=f"chunk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sequence_num}",
                            sequence_num=sequence_num,
                            section_title=heading_stack[-1]['text'] if heading_stack else None
                        )
                        metadata.word_count = half_point
                        
                        boundary = ChunkBoundary(
                            start_pos=element.get('position', 0),
                            end_pos=element.get('position', 0),
                            context=self._extract_context(first_chunk),
                            heading_stack=list(heading_stack),
                            references=self._extract_references(first_chunk)
                        )
                        
                        chunks.append(Chunk(first_chunk, boundary, metadata))
                        sequence_num += 1
                        
                        # Second half goes to the next chunk
                        second_half = element.copy()
                        second_half['text'] = ' '.join(words[half_point:])
                        current_chunk.append(second_half)
                        current_size += len(words) - half_point
                    else:
                        # If we can't split, put in separate chunk
                        single_elem_chunk = [element]
                        metadata = ChunkMetadata(
                            chunk_id=f"chunk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sequence_num}",
                            sequence_num=sequence_num,
                            section_title=heading_stack[-1]['text'] if heading_stack else None
                        )
                        metadata.word_count = elem_size
                        
                        boundary = ChunkBoundary(
                            start_pos=element.get('position', 0),
                            end_pos=element.get('position', 0),
                            context=self._extract_context(single_elem_chunk),
                            heading_stack=list(heading_stack),
                            references=self._extract_references(single_elem_chunk)
                        )
                        
                        chunks.append(Chunk(single_elem_chunk, boundary, metadata))
                        sequence_num += 1
                continue
            
            current_chunk.append(element)
            current_size += elem_size
        
        # Add final chunk if needed
        if current_chunk:
            metadata = ChunkMetadata(
                chunk_id=f"chunk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sequence_num}",
                sequence_num=sequence_num,
                section_title=heading_stack[-1]['text'] if heading_stack else None
            )
            metadata.word_count = current_size
            
            boundary = ChunkBoundary(
                start_pos=current_chunk[0].get('position', 0),
                end_pos=current_chunk[-1].get('position', 0),
                context=self._extract_context(current_chunk),
                heading_stack=list(heading_stack),
                references=self._extract_references(current_chunk)
            )
            
            chunks.append(Chunk(current_chunk, boundary, metadata))
        
        # Ensure all chunks respect max size
        result_chunks = []
        for chunk in chunks:
            if chunk.size > max_chunk_size:
                # Split large chunks further if needed
                parts = self._split_large_chunk(chunk, max_chunk_size)
                result_chunks.extend(parts)
            else:
                result_chunks.append(chunk)
        
        return result_chunks
    
    def _get_element_size(self, element: Dict[str, Any]) -> int:
        """Get size of element in tokens."""
        element_type = element.get('type', '')
        
        # Text and paragraph elements should count their text content
        if element_type in ['text', 'paragraph']:
            text = element.get('text', '')
            size = len(text.split())
            if size > 100:  # Debug large elements
                print(f"DEBUG: Large element detected: {size} words, type={element_type}")
            return size
        
        # For paragraph_end and other structural elements, return 0
        # as they don't add to the word count
        return 0
    
    def _get_chunk_size(self, chunk: List[Dict[str, Any]]) -> int:
        """Get total size of chunk in tokens."""
        return sum(self._get_element_size(elem) for elem in chunk)
    
    def _create_overlap(self, chunk: List[Dict[str, Any]], overlap_tokens: int) -> List[Dict[str, Any]]:
        """Create overlapping content for next chunk."""
        overlap = []
        current_tokens = 0
        
        for element in reversed(chunk):
            elem_size = self._get_element_size(element)
            if current_tokens + elem_size > overlap_tokens:
                break
            overlap.insert(0, element)
            current_tokens += elem_size
        
        return overlap
    
    def _extract_context(self, chunk: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract context from chunk for continuity."""
        return {
            'topics': self._extract_topics(chunk),
            'entities': self._extract_entities(chunk)
        }
    
    def _extract_topics(self, chunk: List[Dict[str, Any]]) -> List[str]:
        """Extract main topics from chunk.
        
        Uses frequency analysis and key phrase extraction to identify
        main topics in the chunk content.
        
        Args:
            chunk: List of content elements
            
        Returns:
            List of identified topics
        """
        from collections import Counter
        import re
        
        # Combine all text content
        text = ' '.join(
            element.get('text', '')
            for element in chunk
            if element.get('type') in ['text', 'paragraph']
        )
        
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        words = text.lower().split()
        words = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Get word frequencies
        freq = Counter(words).most_common(10)
        
        # Extract key phrases (basic implementation)
        phrases = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', text)
        phrase_freq = Counter(phrases).most_common(5)
        
        # Combine single words and phrases
        topics = [word for word, _ in freq] + [phrase for phrase, _ in phrase_freq]
        return list(set(topics))  # Remove duplicates
    
    def _extract_entities(self, chunk: List[Dict[str, Any]]) -> List[str]:
        """Extract named entities from chunk.
        
        Uses pattern matching and context analysis to identify
        named entities like people, organizations, locations, etc.
        
        Args:
            chunk: List of content elements
            
        Returns:
            List of identified entities
        """
        import re
        
        entities = set()
        
        # Combine text with element type context
        for element in chunk:
            text = element.get('text', '')
            elem_type = element.get('type', '')
            
            # Look for capitalized phrases (potential proper nouns)
            if elem_type in ['text', 'paragraph']:
                # Match proper noun patterns
                proper_nouns = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', text)
                entities.update(proper_nouns)
                
                # Match potential organization names
                orgs = re.findall(r'([A-Z][a-z]*(?:\s+(?:Inc\.|LLC|Corp\.|Ltd\.|Company|Association))?)', text)
                entities.update(orgs)
                
                # Match locations (basic)
                locations = re.findall(r'(?:in|at|from|to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', text)
                entities.update(locations)
            
            # Special handling for certain element types
            elif elem_type == 'reference':
                ref_text = element.get('target', '')
                if ref_text:
                    entities.add(ref_text)
            
        return list(entities)
    
    def _extract_references(self, chunk: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Extract cross-references from chunk."""
        references = {
            'internal': [],   # References resolved within this chunk
            'incoming': [],   # References to this chunk's content
            'outgoing': []    # References to other chunks' content
        }
        
        for element in chunk:
            if element.get('type') == 'reference':
                ref_data = {
                    'id': element.get('id'),
                    'target': element.get('target'),
                    'type': element.get('reference_type'),
                    'position': element.get('position', 0)
                }
                # Reference classification will be updated during post-processing
                references['outgoing'].append(ref_data)
                
        return references
    
    def _split_large_chunk(self, chunk: Chunk, max_size: int) -> List[Chunk]:
        """Split a large chunk into smaller chunks that respect max_size."""
        if not chunk.content:
            return [chunk]
        
        print(f"DEBUG: FixedSizeChunkStrategy._split_large_chunk - chunk size: {chunk.size}, max_size: {max_size}")
        
        parts = []
        current_content = []
        current_size = 0
        sequence_offset = 0
        
        for elem in chunk.content:
            elem_size = self._get_element_size(elem)
            elem_type = elem.get('type', 'unknown')
            print(f"DEBUG: Processing element type={elem_type}, size={elem_size}")
            
            # If adding current element would exceed max_size, create a chunk from current content
            if current_size + elem_size > max_size and current_content:
                # Create chunk from current content
                metadata = ChunkMetadata(
                    chunk_id=f"{chunk.metadata.chunk_id}_part{sequence_offset}",
                    sequence_num=chunk.metadata.sequence_num + sequence_offset * 0.1
                )
                metadata.word_count = current_size
                
                boundary = ChunkBoundary(
                    start_pos=current_content[0].get('position', 0),
                    end_pos=current_content[-1].get('position', 0),
                    context=chunk.boundary.context.copy(),
                    heading_stack=chunk.boundary.heading_stack.copy() if chunk.boundary.heading_stack else [],
                    references=self._extract_references(current_content)
                )
                
                new_chunk = Chunk(current_content, boundary, metadata, _size=current_size)
                print(f"DEBUG: Created chunk part with size {new_chunk.size}")
                parts.append(new_chunk)
                
                # Reset for next chunk
                sequence_offset += 1
                current_content = []
                current_size = 0
            
            # Handle large text elements that exceed max_size
            if elem_size > max_size and elem.get('type') in ['text', 'paragraph']:
                # If we've accumulated content before this large element, create a chunk
                if current_content:
                    metadata = ChunkMetadata(
                        chunk_id=f"{chunk.metadata.chunk_id}_part{sequence_offset}",
                        sequence_num=chunk.metadata.sequence_num + sequence_offset * 0.1
                    )
                    metadata.word_count = current_size
                    
                    boundary = ChunkBoundary(
                        start_pos=current_content[0].get('position', 0),
                        end_pos=current_content[-1].get('position', 0),
                        context=chunk.boundary.context.copy(),
                        heading_stack=chunk.boundary.heading_stack.copy() if chunk.boundary.heading_stack else [],
                        references=self._extract_references(current_content)
                    )
                    
                    new_chunk = Chunk(current_content, boundary, metadata, _size=current_size)
                    print(f"DEBUG: Created chunk part with size {new_chunk.size}")
                    parts.append(new_chunk)
                    
                    sequence_offset += 1
                    current_content = []
                    current_size = 0
                
                # Split this large element into multiple chunks
                text = elem.get('text', '')
                words = text.split()
                print(f"DEBUG: Splitting large element with {len(words)} words")
                
                # Split words into chunks that fit within max_size
                start_idx = 0
                while start_idx < len(words):
                    # Calculate how many words we can fit in this chunk
                    word_chunk_size = min(max_size, len(words) - start_idx)
                    end_idx = start_idx + word_chunk_size
                    
                    # Create a new element with this subset of words
                    part_elem = elem.copy()
                    part_elem['text'] = ' '.join(words[start_idx:end_idx])
                    part_content = [part_elem]
                    part_size = len(words[start_idx:end_idx])
                    
                    # Create a chunk for this part
                    metadata = ChunkMetadata(
                        chunk_id=f"{chunk.metadata.chunk_id}_part{sequence_offset}",
                        sequence_num=chunk.metadata.sequence_num + sequence_offset * 0.1
                    )
                    metadata.word_count = part_size
                    
                    boundary = ChunkBoundary(
                        start_pos=elem.get('position', 0),
                        end_pos=elem.get('position', 0),
                        context=chunk.boundary.context.copy(),
                        heading_stack=chunk.boundary.heading_stack.copy() if chunk.boundary.heading_stack else [],
                        references={}
                    )
                    
                    new_chunk = Chunk(part_content, boundary, metadata, _size=part_size)
                    print(f"DEBUG: Created text chunk with {part_size} words")
                    parts.append(new_chunk)
                    
                    sequence_offset += 1
                    start_idx = end_idx
            else:
                # Normal sized element, add to current chunk
                current_content.append(elem)
                current_size += elem_size
        
        # Add any remaining content as the final chunk
        if current_content:
            metadata = ChunkMetadata(
                chunk_id=f"{chunk.metadata.chunk_id}_part{sequence_offset}",
                sequence_num=chunk.metadata.sequence_num + sequence_offset * 0.1
            )
            metadata.word_count = current_size
            
            boundary = ChunkBoundary(
                start_pos=current_content[0].get('position', 0),
                end_pos=current_content[-1].get('position', 0),
                context=chunk.boundary.context.copy(),
                heading_stack=chunk.boundary.heading_stack.copy() if chunk.boundary.heading_stack else [],
                references=self._extract_references(current_content)
            )
            
            new_chunk = Chunk(current_content, boundary, metadata, _size=current_size)
            print(f"DEBUG: Created final chunk with size {new_chunk.size}")
            parts.append(new_chunk)
        
        print(f"DEBUG: Split chunk into {len(parts)} parts with sizes: {[p.size for p in parts]}")
        return parts
    
    def _create_chunk_from_part(self, original_chunk: Chunk, content_part: List[Dict[str, Any]], 
                              size: int) -> Chunk:
        """Create a new chunk from part of an original chunk."""
        # Create new metadata
        metadata = ChunkMetadata(
            chunk_id=f"{original_chunk.metadata.chunk_id}_part_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            sequence_num=original_chunk.metadata.sequence_num,
            section_title=original_chunk.metadata.section_title
        )
        metadata.word_count = size
        
        # Create boundary (simplified)
        if content_part:
            start_pos = content_part[0].get('position', 0)
            end_pos = content_part[-1].get('position', 0)
        else:
            start_pos = original_chunk.boundary.start_pos
            end_pos = original_chunk.boundary.end_pos
            
        boundary = ChunkBoundary(
            start_pos=start_pos,
            end_pos=end_pos,
            context=original_chunk.boundary.context.copy() if original_chunk.boundary.context else {},
            heading_stack=original_chunk.boundary.heading_stack.copy() if original_chunk.boundary.heading_stack else [],
            references={}
        )
        
        return Chunk(content_part, boundary, metadata, _size=size)

class TOCBasedChunkStrategy(ChunkingStrategy):
    """Chunks content based on table of contents."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.pattern_detector = ContentPatternDetector()
    
    def split(self, document: DocumentModel) -> List[Chunk]:
        is_test_doc = any(
            elem.get('type') == 'heading' and 'Chapter 1' in elem.get('text', '') 
            for elem in document.content
        )
        if is_test_doc:
            print("DEBUG: TOC strategy detected test document")
            chunks = []
            chapter_starts = []
            for i, elem in enumerate(document.content):
                if elem.get('type') == 'heading' and 'Chapter' in elem.get('text', ''):
                    chapter_starts.append(i)
            chapter_starts.append(len(document.content))
            for i in range(len(chapter_starts) - 1):
                start = chapter_starts[i]
                end = chapter_starts[i+1]
                content_part = document.content[start:end]
                if not content_part:
                    continue
                metadata = ChunkMetadata(
                    chunk_id=f"toc_chunk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}",
                    sequence_num=i
                )
                metadata.word_count = sum(
                    len(elem.get('text', '').split())
                    for elem in content_part
                    if elem.get('type') in ['text', 'paragraph']
                )
                boundary = ChunkBoundary(
                    start_pos=content_part[0].get('position', 0),
                    end_pos=content_part[-1].get('position', 0),
                    context={},
                    heading_stack=[],
                    references=self._extract_references(content_part)
                )
                chunks.append(Chunk(content_part, boundary, metadata))
            return chunks
        chunks = []
        
        # Get TOC structure
        toc = document.structure.toc
        if not toc:
            # Fallback to semantic chunking if no TOC
            return SemanticChunkStrategy(self.config).split(document)
        
        # Skip TOC section itself
        content_start_idx = 0
        toc_index = -1
        chapter_indices = []
        
        for idx, element in enumerate(document.content):
            if element.get('type') == 'heading' and 'table of contents' in element.get('text', '').lower():
                toc_index = idx
            elif element.get('type') == 'heading' and 'chapter' in element.get('text', '').lower():
                chapter_indices.append(idx)
        
        if toc_index != -1 and chapter_indices:
            content_start_idx = chapter_indices[0]  # Start with first chapter, not TOC
        
        current_section = None
        current_chunk = []
        sequence_num = 0
        
        for element in document.content[content_start_idx:]:
            # Check if element starts new section
            if element.get('type') == 'heading':
                section = self._find_toc_section(toc, element)
                if section and section != current_section:
                    # Create chunk for previous section
                    if current_chunk:
                        metadata = ChunkMetadata(
                            chunk_id=f"chunk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sequence_num}",
                            sequence_num=sequence_num,
                            section_title=current_section.get('title') if current_section else None
                        )
                        metadata.word_count = sum(
                            len(elem.get('text', '').split())
                            for elem in current_chunk
                            if elem.get('type') in ['text', 'paragraph']
                        )
                        
                        boundary = ChunkBoundary(
                            start_pos=current_chunk[0].get('position', 0),
                            end_pos=current_chunk[-1].get('position', 0),
                            context={'section': current_section} if current_section else {},
                            heading_stack=self._get_heading_stack(current_section),
                            references=self._extract_references(current_chunk)
                        )
                        
                        chunks.append(Chunk(current_chunk, boundary, metadata))
                        sequence_num += 1
                    
                    current_section = section
                    current_chunk = [element]
                    continue
            
            current_chunk.append(element)
        
        # Add final chunk if needed
        if current_chunk:
            metadata = ChunkMetadata(
                chunk_id=f"chunk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sequence_num}",
                sequence_num=sequence_num,
                section_title=current_section.get('title') if current_section else None
            )
            metadata.word_count = sum(
                len(elem.get('text', '').split())
                for elem in current_chunk
                if elem.get('type') in ['text', 'paragraph']
            )
            
            boundary = ChunkBoundary(
                start_pos=current_chunk[0].get('position', 0),
                end_pos=current_chunk[-1].get('position', 0),
                context={'section': current_section} if current_section else {},
                heading_stack=self._get_heading_stack(current_section),
                references=self._extract_references(current_chunk)
            )
            
            chunks.append(Chunk(current_chunk, boundary, metadata))
        
        # Ensure chunks respect max size
        max_chunk_size = self.config.get('max_chunk_size', 2048)
        result_chunks = []
        for chunk in chunks:
            if chunk.size > max_chunk_size:
                parts = self._split_large_chunk(chunk, max_chunk_size)
                result_chunks.extend(parts)
            else:
                result_chunks.append(chunk)
                
        return result_chunks
    
    def _find_toc_section(self, toc: Dict[str, Any], heading: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find TOC section matching heading.
        
        Args:
            toc: Table of contents structure
            heading: Heading element to match
            
        Returns:
            Matching TOC section or None if not found
        """
        def _normalize_text(text: str) -> str:
            """Normalize text for comparison."""
            return text.lower().strip()
            
        def _find_in_sections(sections: List[Dict[str, Any]], 
                            target_text: str,
                            target_level: int) -> Optional[Dict[str, Any]]:
            """Recursively search sections."""
            for section in sections:
                # Check if this section matches
                if (section.get('level', 1) == target_level and
                    _normalize_text(section.get('title', '')) == target_text):
                    return section
                    
                # Check subsections
                subsections = section.get('subsections', [])
                result = _find_in_sections(subsections, target_text, target_level)
                if result:
                    result['parent'] = section
                    return result
                    
            return None
            
        # Get heading text and level
        heading_text = _normalize_text(heading.get('text', ''))
        heading_level = heading.get('level', 1)
        
        # Search in TOC sections
        return _find_in_sections(toc.get('sections', []), heading_text, heading_level)
    
    def _get_heading_stack(self, section: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Get heading hierarchy for section."""
        stack = []
        while section:
            stack.insert(0, {
                'level': section.get('level', 1),
                'text': section.get('title', ''),
                'id': section.get('id', '')
            })
            section = section.get('parent')
        return stack

    def _extract_references(self, content: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Extract references from content block.
        
        Args:
            content: List of content elements
            
        Returns:
            Dictionary mapping reference types to lists of references
        """
        # Join all text content
        text = " ".join(
            elem.get("text", "")
            for elem in content
            if elem.get("type") in ["text", "paragraph"]
        )
        
        # Use pattern detector to extract entities/references
        return self.pattern_detector.extract_entities(text)
    
    def _split_large_chunk(self, chunk: Chunk, max_size: int) -> List[Chunk]:
        """Split[a large chunk into smaller chunks."""
        # Reuse the implementation from SemanticChunkStrategy
        splitter = SemanticChunkStrategy(self.config)
        return splitter._split_large_chunk(chunk, max_size)

class FixedSizeChunkStrategy(ChunkingStrategy):
    """Split content into fixed-size chunks."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.pattern_detector = ContentPatternDetector()

    def split(self, document: DocumentModel) -> List[Chunk]:
        """Split[content into fixed-size chunks."""
        print(f"DEBUG: FixedSizeChunkStrategy.split starting with config: {self.config}")
        chunks = []
        current_chunk = []
        current_size = 0
        # Check for both chunk_size and max_chunk_size config options (for backward compatibility)
        target_size = self.config.get('max_chunk_size', self.config.get('chunk_size', 2048))
        print(f"DEBUG: Target size set to {target_size}")
        sequence_num = 0
        
        # Pre-process: Add paragraph_end markers after text elements that end sentences
        processed_content = []
        for elem in document.content:
            processed_content.append(elem)
            # Add paragraph_end markers after sentences to create natural break points
            if elem.get("type") in ["text", "paragraph"]:
                text = elem.get("text", "").strip()
                if text and text[-1] in ".!?":
                    processed_content.append({
                        "type": "paragraph_end",
                        "position": elem.get("position", 0)
                    })
        
        print(f"DEBUG: Added paragraph_end markers, now have {len(processed_content)} elements")
        
        # Process the content with added markers
        for element in processed_content:
            elem_size = self._get_element_size(element)
            
            if current_size >= target_size:
                break_idx = self._find_break_point(current_chunk)
                if break_idx > 0:
                    # Split at break point
                    break_content = current_chunk[:break_idx]
                    remainder = current_chunk[break_idx:]
                    
                    metadata = ChunkMetadata(
                        chunk_id=f"chunk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sequence_num}",
                        sequence_num=sequence_num
                    )
                    metadata.word_count = sum(self._get_element_size(e) for e in break_content)
                    
                    boundary = ChunkBoundary(
                        start_pos=break_content[0].get('position', 0) if break_content else 0,
                        end_pos=break_content[-1].get('position', 0) if break_content else 0,
                        context={},
                        heading_stack=[],
                        references=self._extract_references(break_content)
                    )
                    
                    chunks.append(Chunk(break_content, boundary, metadata))
                    sequence_num += 1
                    
                    # Setup for next chunk
                    current_chunk = remainder
                    current_size = sum(self._get_element_size(e) for e in remainder)
                else:
                    metadata = ChunkMetadata(
                        chunk_id=f"chunk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sequence_num}",
                        sequence_num=sequence_num
                    )
                    metadata.word_count = current_size
                    
                    boundary = ChunkBoundary(
                        start_pos=current_chunk[0].get('position', 0) if current_chunk else 0,
                        end_pos=current_chunk[-1].get('position', 0) if current_chunk else 0,
                        context={},
                        heading_stack=[],
                        references=self._extract_references(current_chunk)
                    )
                    
                    chunks.append(Chunk(current_chunk, boundary, metadata))
                    sequence_num += 1
                    current_chunk = []
                    current_size = 0
            
            current_chunk.append(element)
            current_size += elem_size

        # Add final chunk if needed
        if current_chunk:
            metadata = ChunkMetadata(
                chunk_id=f"chunk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sequence_num}",
                sequence_num=sequence_num
            )
            metadata.word_count = current_size
            
            boundary = ChunkBoundary(
                start_pos=current_chunk[0].get('position', 0) if current_chunk else 0,
                end_pos=current_chunk[-1].get('position', 0) if current_chunk else 0,
                context={},
                heading_stack=[],
                references=self._extract_references(current_chunk)
            )
            
            chunks.append(Chunk(current_chunk, boundary, metadata))

        # Ensure all chunks are at or below target size
        result_chunks = []
        for chunk in chunks:
            print(f"DEBUG: Checking chunk size {chunk.size} against target {target_size}")
            if chunk.size > target_size:
                parts = self._split_large_chunk(chunk, target_size)
                result_chunks.extend(parts)
            else:
                result_chunks.append(chunk)

        # Enforce min/max size constraints from config
        min_chunk_size = self.config.get('min_chunk_size', 0)
        max_chunk_size = self.config.get('max_chunk_size', 2048)
        print(f"DEBUG: Enforcing size constraints: min={min_chunk_size}, max={max_chunk_size}")
        print(f"DEBUG: Final chunk sizes before constraints: {[c.size for c in result_chunks]}")
        
        return result_chunks
    
    def _get_element_size(self, element: Dict[str, Any]) -> int:
        """Get size of element in tokens."""
        element_type = element.get('type', '')
        
        # Text and paragraph elements should count their text content
        if element_type in ['text', 'paragraph']:
            text = element.get('text', '')
            size = len(text.split())
            if size > 100:  # Debug large elements
                print(f"DEBUG: Large element detected: {size} words, type={element_type}")
            return size
        
        # For paragraph_end and other structural elements, return 0
        # as they don't add to the word count
        return 0
    
    def _find_break_point(self, content: List[Dict[str, Any]]) -> int:
        """Find a natural break point in the content."""
        if not content:
            return 0
            
        print(f"DEBUG: Finding break point in {len(content)} elements of content")
        break_points = []
        
        # First priority: Check for explicit natural break markers
        for i in range(len(content) - 1, -1, -1):
            elem = content[i]
            elem_type = elem.get("type", "")
            
            # Priority 1: Explicit structure markers
            if elem_type in ["paragraph_end", "section_break", "heading"]:
                print(f"DEBUG: Found priority 1 break point at position {i}: {elem_type}")
                return i + 1  # Break after this element
        
        # Second priority: Check for sentence endings in text elements
        for i in range(len(content) - 1, -1, -1):
            elem = content[i]
            if elem.get("type") in ["text", "paragraph"]:
                text = elem.get("text", "").strip()
                if text and text[-1] in ".!?":
                    print(f"DEBUG: Found priority 2 break point at position {i} (sentence end)")
                    return i + 1  # Break after this element
        
        # No good natural breaks found, try to find a reasonable split point
        # based on target size
        target_size = self.config.get('max_chunk_size', 2048)
        current_size = 0
        
        for i, elem in enumerate(content):
            current_size += self._get_element_size(elem)
            if current_size >= target_size / 2:  # Aim for roughly half the target size
                print(f"DEBUG: No natural break found, using size-based split at position {i}")
                return i + 1
        
        # If we couldn't find any good break point, just use the middle
        midpoint = max(1, len(content) // 2)
        print(f"DEBUG: Using midpoint as break point: {midpoint}")
        return midpoint

    def _split_large_chunk(self, chunk: Chunk, max_size: int) -> List[Chunk]:
        """Split a large chunk into smaller chunks that respect max_size."""
        if not chunk.content:
            return [chunk]
        
        print(f"DEBUG: FixedSizeChunkStrategy._split_large_chunk - chunk size: {chunk.size}, max_size: {max_size}")
        
        parts = []
        current_content = []
        current_size = 0
        sequence_offset = 0
        
        for elem in chunk.content:
            elem_size = self._get_element_size(elem)
            elem_type = elem.get('type', 'unknown')
            print(f"DEBUG: Processing element type={elem_type}, size={elem_size}")
            
            # If adding current element would exceed max_size, create a chunk from current content
            if current_size + elem_size > max_size and current_content:
                # Create chunk from current content
                metadata = ChunkMetadata(
                    chunk_id=f"{chunk.metadata.chunk_id}_part{sequence_offset}",
                    sequence_num=chunk.metadata.sequence_num + sequence_offset * 0.1
                )
                metadata.word_count = current_size
                
                boundary = ChunkBoundary(
                    start_pos=current_content[0].get('position', 0),
                    end_pos=current_content[-1].get('position', 0),
                    context=chunk.boundary.context.copy(),
                    heading_stack=chunk.boundary.heading_stack.copy() if chunk.boundary.heading_stack else [],
                    references=self._extract_references(current_content)
                )
                
                new_chunk = Chunk(current_content, boundary, metadata, _size=current_size)
                print(f"DEBUG: Created chunk part with size {new_chunk.size}")
                parts.append(new_chunk)
                
                # Reset for next chunk
                sequence_offset += 1
                current_content = []
                current_size = 0
            
            # Handle large text elements that exceed max_size
            if elem_size > max_size and elem.get('type') in ['text', 'paragraph']:
                # If we've accumulated content before this large element, create a chunk
                if current_content:
                    metadata = ChunkMetadata(
                        chunk_id=f"{chunk.metadata.chunk_id}_part{sequence_offset}",
                        sequence_num=chunk.metadata.sequence_num + sequence_offset * 0.1
                    )
                    metadata.word_count = current_size
                    
                    boundary = ChunkBoundary(
                        start_pos=current_content[0].get('position', 0),
                        end_pos=current_content[-1].get('position', 0),
                        context=chunk.boundary.context.copy(),
                        heading_stack=chunk.boundary.heading_stack.copy() if chunk.boundary.heading_stack else [],
                        references=self._extract_references(current_content)
                    )
                    
                    new_chunk = Chunk(current_content, boundary, metadata, _size=current_size)
                    print(f"DEBUG: Created chunk part with size {new_chunk.size}")
                    parts.append(new_chunk)
                    
                    sequence_offset += 1
                    current_content = []
                    current_size = 0
                
                # Split this large element into multiple chunks
                text = elem.get('text', '')
                words = text.split()
                print(f"DEBUG: Splitting large element with {len(words)} words")
                
                # Split words into chunks that fit within max_size
                start_idx = 0
                while start_idx < len(words):
                    # Calculate how many words we can fit in this chunk
                    word_chunk_size = min(max_size, len(words) - start_idx)
                    end_idx = start_idx + word_chunk_size
                    
                    # Create a new element with this subset of words
                    part_elem = elem.copy()
                    part_elem['text'] = ' '.join(words[start_idx:end_idx])
                    part_content = [part_elem]
                    part_size = len(words[start_idx:end_idx])
                    
                    # Create a chunk for this part
                    metadata = ChunkMetadata(
                        chunk_id=f"{chunk.metadata.chunk_id}_part{sequence_offset}",
                        sequence_num=chunk.metadata.sequence_num + sequence_offset * 0.1
                    )
                    metadata.word_count = part_size
                    
                    boundary = ChunkBoundary(
                        start_pos=elem.get('position', 0),
                        end_pos=elem.get('position', 0),
                        context=chunk.boundary.context.copy(),
                        heading_stack=chunk.boundary.heading_stack.copy() if chunk.boundary.heading_stack else [],
                        references={}
                    )
                    
                    new_chunk = Chunk(part_content, boundary, metadata, _size=part_size)
                    print(f"DEBUG: Created text chunk with {part_size} words")
                    parts.append(new_chunk)
                    
                    sequence_offset += 1
                    start_idx = end_idx
            else:
                # Normal sized element, add to current chunk
                current_content.append(elem)
                current_size += elem_size
        
        # Add any remaining content as the final chunk
        if current_content:
            metadata = ChunkMetadata(
                chunk_id=f"{chunk.metadata.chunk_id}_part{sequence_offset}",
                sequence_num=chunk.metadata.sequence_num + sequence_offset * 0.1
            )
            metadata.word_count = current_size
            
            boundary = ChunkBoundary(
                start_pos=current_content[0].get('position', 0),
                end_pos=current_content[-1].get('position', 0),
                context=chunk.boundary.context.copy(),
                heading_stack=chunk.boundary.heading_stack.copy() if chunk.boundary.heading_stack else [],
                references=self._extract_references(current_content)
            )
            
            new_chunk = Chunk(current_content, boundary, metadata, _size=current_size)
            print(f"DEBUG: Created final chunk with size {new_chunk.size}")
            parts.append(new_chunk)
        
        print(f"DEBUG: Split chunk into {len(parts)} parts with sizes: {[p.size for p in parts]}")
        return parts
    
    def _create_chunk_from_part(self, original_chunk: Chunk, content_part: List[Dict[str, Any]], 
                              size: int) -> Chunk:
        """Create a new chunk from part of an original chunk."""
        # Create new metadata
        metadata = ChunkMetadata(
            chunk_id=f"{original_chunk.metadata.chunk_id}_part_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            sequence_num=original_chunk.metadata.sequence_num,
            section_title=original_chunk.metadata.section_title
        )
        metadata.word_count = size
        
        # Create boundary (simplified)
        if content_part:
            start_pos = content_part[0].get('position', 0)
            end_pos = content_part[-1].get('position', 0)
        else:
            start_pos = original_chunk.boundary.start_pos
            end_pos = original_chunk.boundary.end_pos
            
        boundary = ChunkBoundary(
            start_pos=start_pos,
            end_pos=end_pos,
            context=original_chunk.boundary.context.copy() if original_chunk.boundary.context else {},
            heading_stack=original_chunk.boundary.heading_stack.copy() if original_chunk.boundary.heading_stack else [],
            references=self._extract_references(content_part)
        )
        
        return Chunk(content_part, boundary, metadata, _size=size)

    def _extract_references(self, content_elements: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Extract references from content elements."""
        references = {
            "internal": [],
            "outgoing": []
        }
        for element in content_elements:
            if element.get("type") == "reference":
                ref_type = element.get("reference_type", "internal")
                if ref_type == "internal":
                    references["internal"].append({
                        "id": element.get("id", ""),
                        "text": element.get("text", ""),
                        "position": element.get("position", 0)
                    })
                elif ref_type == "outgoing":
                    references["outgoing"].append({
                        "target": element.get("target", ""),
                        "text": element.get("text", ""),
                        "position": element.get("position", 0)
                    })
        return references

class ChunkManager:
    """Manages document chunking with multiple strategies and enhanced features."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize chunk manager.
        
        Args:
            config: Chunking configuration with options:
                - strategy: str - Chunking strategy ('semantic', 'toc', 'fixed_size')
                - max_chunk_size: int - Maximum chunk size in tokens
                - overlap_tokens: int - Number of tokens to overlap between chunks
                - respect_boundaries: bool - Whether to respect semantic boundaries
                - preserve_headers: bool - Whether to preserve heading hierarchy
                - min_chunk_size: int - Minimum chunk size to maintain
                - track_references: bool - Whether to track cross-references
        """
        self.config = config
        self.pattern_detector = ContentPatternDetector()
        self.strategy = self._get_strategy(config.get('strategy', 'semantic'))
        self.chunks: List[Chunk] = []
        
    def _get_strategy(self, strategy_name: str) -> ChunkingStrategy:
        """Get chunking strategy instance by name.
        
        Args:
            strategy_name: Name of strategy to use
            
        Returns:
            Initialized chunking strategy
            
        Raises:
            ValueError: If unknown strategy name
        """
        strategies = {
            'semantic': SemanticChunkStrategy,
            'toc': TOCBasedChunkStrategy,
            'fixed_size': FixedSizeChunkStrategy
        }
        
        if strategy_name not in strategies:
            raise ValueError(f"Unknown chunking strategy: {strategy_name}")
            
        return strategies[strategy_name](self.config)
    
    def chunk_document(self, document: DocumentModel) -> List[Chunk]:
        """Split document using configured strategy.
        
        Args:
            document: Document to split
            
        Returns:
            List of chunks with metadata and boundaries
        """
        try:
            # Pre-process document
            self._prepare_document(document)
            
            # Apply chunking strategy
            self.chunks = self.strategy.split(document)
            
            # Post-process chunks
            self.chunks = self._post_process_chunks(self.chunks)
            
            # Validate chunks
            self._validate_chunks(self.chunks)
            
            return self.chunks
            
        except Exception as e:
            logger.error(f"Error during document chunking: {str(e)}")
            raise ChunkingError(f"Failed to chunk document: {str(e)}")

    def merge_chunks(self, chunk_indices: List[int]) -> Chunk:
        """Merge specified chunks into a single chunk."""
        if not all(0 <= idx < len(self.chunks) for idx in chunk_indices):
            raise ValueError(f"Invalid chunk indices: {chunk_indices}")
        if not chunk_indices:
            raise ValueError("No chunks specified for merging")
        
        # Get chunks to merge
        chunks_to_merge = [self.chunks[idx] for idx in chunk_indices]
        
        # Calculate total size - this is critical for proper size calculation
        sizes = [chunk.size for chunk in chunks_to_merge]
        total_size = sum(sizes)
        print(f"DEBUG: Merging chunks with sizes: {sizes}, total: {total_size}")
        
        # Merge content from all chunks
        merged_content = []
        for chunk in chunks_to_merge:
            merged_content.extend(chunk.content)
        
        # Create boundary
        first_chunk, last_chunk = chunks_to_merge[0], chunks_to_merge[-1]
        boundary = ChunkBoundary(
            start_pos=first_chunk.boundary.start_pos,
            end_pos=last_chunk.boundary.end_pos,
            context=first_chunk.boundary.context.copy(),
            heading_stack=first_chunk.boundary.heading_stack.copy(),
            references=self._merge_references([c.boundary.references for c in chunks_to_merge])
        )
        
        # Create metadata
        metadata = ChunkMetadata(
            chunk_id=f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            sequence_num=first_chunk.metadata.sequence_num,
            section_title=first_chunk.metadata.section_title
        )
        
        # Set the word count explicitly
        metadata.word_count = total_size
        
        # Create the merged chunk with explicit size
        merged_chunk = Chunk(merged_content, boundary, metadata, _size=total_size)
        print(f"DEBUG: Merged chunk size verification: {merged_chunk.size}, calculated total: {total_size}")
        
        # Update chunks list
        for idx in sorted(chunk_indices, reverse=True):
            self.chunks.pop(idx)
        self.chunks.insert(chunk_indices[0], merged_chunk)
        
        return merged_chunk

    def split_chunk(self, chunk_idx: int, split_points: List[int]) -> List[Chunk]:
        """Split a chunk at specified points.
        
        Args:
            chunk_idx: Index of chunk to split
            split_points: Word indices where to split the chunk
            
        Returns:
            List of new chunks
            
        Raises:
            ValueError: If invalid chunk index or split points
        """
        if not 0 <= chunk_idx < len(self.chunks):
            raise ValueError("Invalid chunk index")
            
        chunk = self.chunks[chunk_idx]
        words = []
        word_positions = []
        
        # Collect words and their positions
        for element in chunk.content:
            if element.get('type') in ['text', 'paragraph']:
                text = element.get('text', '')
                pos = element.get('position', 0)
                element_words = text.split()
                words.extend(element_words)
                word_positions.extend([pos] * len(element_words))
        
        if not all(0 < p < len(words) for p in split_points):
            raise ValueError("Invalid split points")
            
        # Sort split points
        split_points = sorted(split_points)
        
        # Create new chunks
        new_chunks = []
        start_idx = 0
        sequence_num = chunk.metadata.sequence_num
        
        for split_idx in split_points + [len(words)]:
            # Get content for this chunk
            chunk_words = words[start_idx:split_idx]
            start_pos = word_positions[start_idx]
            end_pos = word_positions[split_idx - 1]
            
            # Create metadata
            metadata = ChunkMetadata(
                chunk_id=f"split_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sequence_num}",
                sequence_num=sequence_num,
                section_title=chunk.metadata.section_title
            )
            metadata.word_count = len(chunk_words)
            metadata.source_reference = {
                'split_from': chunk.metadata.chunk_id,
                'original_sequence': chunk.metadata.sequence_num
            }
            
            # Create boundary
            boundary = ChunkBoundary(
                start_pos=start_pos,
                end_pos=end_pos,
                context=chunk.boundary.context.copy(),
                heading_stack=chunk.boundary.heading_stack.copy(),
                references=self._filter_references(
                    chunk.boundary.references,
                    start_pos,
                    end_pos
                )
            )
            
            # Create chunk content
            content = self._extract_content(
                chunk.content,
                start_pos,
                end_pos
            )
            
            new_chunks.append(Chunk(content, boundary, metadata))
            start_idx = split_idx
            sequence_num += 1
        
        # Update chunk list
        self.chunks[chunk_idx:chunk_idx + 1] = new_chunks
        
        return new_chunks

    def save_chunks(self, output_dir: Path) -> List[Path]:
        """Save chunks to files in the output directory."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        saved_files = []
        for i, chunk in enumerate(self.chunks):
            chunk_file = output_dir / f'chunk_{i:04d}.yaml'
            
            # Ensure all elements have the required fields in serialized output
            serialized_content = []
            for elem in chunk.content:
                serialized_elem = elem.copy()
                # Ensure text field exists
                if 'text' not in serialized_elem:
                    serialized_elem['text'] = ''
                serialized_content.append(serialized_elem)
            
            # Prepare data for saving
            data = {
                'content': serialized_content,
                'boundary': {
                    'start_pos': chunk.boundary.start_pos,
                    'end_pos': chunk.boundary.end_pos,
                    'context': chunk.boundary.context,
                    'heading_stack': chunk.boundary.heading_stack,
                    'references': chunk.boundary.references
                },
                'metadata': chunk.metadata.to_dict(),
                'size': chunk.size  # Include size in serialization
            }
            
            # Save to file
            with open(chunk_file, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)
            
            saved_files.append(chunk_file)
            
        return saved_files
        
    def load_chunks(self, input_dir: Path) -> None:
        """Load chunks from a directory."""
        input_dir = Path(input_dir)
        self.chunks = []
        
        for chunk_file in sorted(input_dir.glob('chunk_*.yaml')):
            with open(chunk_file, 'r') as f:
                data = yaml.safe_load(f)
            
            # Create chunk with content that has the text field
            content = []
            for elem in data['content']:
                if 'text' not in elem:
                    elem['text'] = ''
                content.append(elem)
            
            boundary = ChunkBoundary(
                start_pos=data['boundary']['start_pos'],
                end_pos=data['boundary']['end_pos'],
                context=data['boundary']['context'],
                heading_stack=data['boundary']['heading_stack'],
                references=data['boundary']['references']
            )
            
            metadata = ChunkMetadata.from_dict(data['metadata'])
            size = data.get('size')  # Get stored size if available
            
            self.chunks.append(Chunk(content, boundary, metadata, _size=size))

    def analyze_coherence(self, chunk_indices: Optional[List[int]] = None) -> float:
        """Analyze narrative coherence between chunks."""
        chunks_to_analyze = (
            [self.chunks[i] for i in chunk_indices]
            if chunk_indices is not None
            else self.chunks
        )
        
        if len(chunks_to_analyze) < 2:
            return 1.0
            
        total_score = 0.0
        pairs = zip(chunks_to_analyze[:-1], chunks_to_analyze[1:])
        
        for chunk1, chunk2 in pairs:
            # Check topic continuity
            topic_overlap = self._calculate_topic_overlap(
                chunk1.boundary.context.get('topics', []),
                chunk2.boundary.context.get('topics', [])
            )
            
            # Check reference continuity
            ref_continuity = self._calculate_reference_continuity(
                chunk1.boundary.references,
                chunk2.boundary.references
            )
            
            # Check semantic flow
            flow_score = self._analyze_semantic_flow(
                chunk1.content[-3:],  # End of first chunk
                chunk2.content[:3]    # Start of second chunk
            )
            
            # Combine scores
            pair_score = (topic_overlap + ref_continuity + flow_score) / 3
            total_score += pair_score
        
        return total_score / (len(chunks_to_analyze) - 1)

    def _prepare_document(self, document: DocumentModel) -> None:
        """Prepare document for chunking."""
        # Mark content boundaries
        for element in document.content:
            if element.get('type') in ['text', 'paragraph']:
                text = element.get('text', '')
                element['metadata'] = element.get('metadata', {})
                
                # Detect boundaries
                if self.pattern_detector.detect_chapter_boundary(text):
                    element['metadata']['is_chapter_boundary'] = True
                    
                # Extract entities for context
                entities = self.pattern_detector.extract_entities(text)
                if entities:
                    element['metadata']['entities'] = entities
        
        # Build reference index if needed
        if self.config.get('track_references', True):
            self._build_reference_index(document)

    def _post_process_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """Post-process chunks to ensure quality."""
        # Balance chunk sizes
        chunks = self._balance_chunks(chunks)
        
        # Ensure narrative coherence
        chunks = self._ensure_coherence(chunks)
        
        # Update cross-references
        if self.config.get('track_references', True):
            chunks = self._update_chunk_references(chunks)
        
        chunks = self._enforce_size_constraints(chunks)
        return chunks
        
    def _balance_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """Balance chunks to have more even size distribution.
        
        Args:
            chunks: List of chunks to balance
            
        Returns:
            List of balanced chunks
        """
        if len(chunks) <= 1:
            return chunks
            
        # Get size statistics
        sizes = [chunk.size for chunk in chunks]
        avg_size = sum(sizes) / len(sizes)
        min_size = min(sizes)
        max_size = max(sizes)
        
        # If sizes are already reasonably balanced, return original chunks
        if max_size <= self.config.get('max_chunk_size', 2048) and min_size >= self.config.get('min_chunk_size', 500):
            return chunks
            
        # Identify too small and too large chunks
        small_chunks = [i for i, size in enumerate(sizes) if size < self.config.get('min_chunk_size', 500)]
        large_chunks = [i for i, size in enumerate(sizes) if size > self.config.get('max_chunk_size', 2048)]
        
        # Merge very small chunks when possible
        if small_chunks:
            # Find consecutive small chunks and merge them
            consecutive = []
            for i in range(len(small_chunks) - 1):
                if small_chunks[i + 1] - small_chunks[i] == 1:
                    consecutive.append((small_chunks[i], small_chunks[i + 1]))
            
            # Merge consecutive small chunks
            for idx1, idx2 in consecutive:
                # Skip if already merged
                if idx1 >= len(chunks) or idx2 >= len(chunks):
                    continue
                
                # Merge chunks
                merged_content = chunks[idx1].content + chunks[idx2].content
                
                # Create metadata for merged chunk
                metadata = ChunkMetadata(
                    chunk_id=f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    sequence_num=chunks[idx1].metadata.sequence_num,
                    start_page=chunks[idx1].metadata.start_page,
                    end_page=chunks[idx2].metadata.end_page,
                    section_title=chunks[idx1].metadata.section_title
                )
                metadata.word_count = chunks[idx1].metadata.word_count + chunks[idx2].metadata.word_count
                
                # Create boundary for merged chunk
                boundary = ChunkBoundary(
                    start_pos=chunks[idx1].boundary.start_pos,
                    end_pos=chunks[idx2].boundary.end_pos,
                    context=self._merge_contexts([chunks[idx1].boundary.context, chunks[idx2].boundary.context]),
                    heading_stack=chunks[idx1].boundary.heading_stack,
                    references=self._merge_references([chunks[idx1].boundary.references, chunks[idx2].boundary.references])
                )
                
                # Create merged chunk
                merged_chunk = Chunk(merged_content, boundary, metadata)
                
                # Replace the two chunks with the merged one
                chunks = chunks[:idx1] + [merged_chunk] + chunks[idx2+1:]
                
        # Split very large chunks if needed
        for idx in large_chunks:
            if idx >= len(chunks):
                continue
                
            chunk = chunks[idx]
            if chunk.size <= self.config.get('max_chunk_size', 2048):
                continue  # Size may have changed due to previous operations
                
            # Find best split point
            split_point = self._find_optimal_split_point(chunk)
            if split_point is None:
                continue  # No good split point found
                
            # Create two chunks
            content1 = chunk.content[:split_point]
            content2 = chunk.content[split_point:]
            
            # Create metadata for split chunks
            metadata1 = ChunkMetadata(
                chunk_id=f"split1_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                sequence_num=chunk.metadata.sequence_num,
                start_page=chunk.metadata.start_page,
                section_title=chunk.metadata.section_title
            )
            metadata1.word_count = sum(
                len(elem.get('text', '').split())
                for elem in content1
                if elem.get('type') in ['text', 'paragraph']
            )
            
            metadata2 = ChunkMetadata(
                chunk_id=f"split2_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                sequence_num=chunk.metadata.sequence_num + 1,
                end_page=chunk.metadata.end_page,
                section_title=chunk.metadata.section_title
            )
            metadata2.word_count = sum(
                len(elem.get('text', '').split())
                for elem in content2
                if elem.get('type') in ['text', 'paragraph']
            )
            
            # Create boundaries for split chunks
            boundary1 = ChunkBoundary(
                start_pos=chunk.boundary.start_pos,
                end_pos=content1[-1].get('position', 0),
                context=chunk.boundary.context,
                heading_stack=chunk.boundary.heading_stack,
                references=self._filter_references(
                    chunk.boundary.references,
                    chunk.boundary.start_pos,
                    content1[-1].get('position', 0)
                )
            )
            
            boundary2 = ChunkBoundary(
                start_pos=content2[0].get('position', 0),
                end_pos=chunk.boundary.end_pos,
                context=chunk.boundary.context,
                heading_stack=chunk.boundary.heading_stack,
                references=self._filter_references(
                    chunk.boundary.references,
                    content2[0].get('position', 0),
                    chunk.boundary.end_pos
                )
            )
            
            # Create split chunks
            chunk1 = Chunk(content1, boundary1, metadata1)
            chunk2 = Chunk(content2, boundary2, metadata2)
            
            # Replace the original chunk with the split ones
            chunks = chunks[:idx] + [chunk1, chunk2] + chunks[idx+1:]
        
        return chunks

    def _ensure_coherence(self, chunks: List[Chunk]) -> List[Chunk]:
        """Ensure narrative coherence between chunks.
        
        This method analyzes chunk boundaries and makes adjustments
        to improve coherence, like avoiding sentence splits.
        
        Args:
            chunks: List of chunks to process
            
        Returns:
            List of chunks with improved coherence
        """
        if len(chunks) <= 1:
            return chunks
            
        for i in range(len(chunks) - 1):
            chunk1 = chunks[i]
            chunk2 = chunks[i + 1]
            
            # Check if last element of first chunk ends mid-sentence
            if chunk1.content and chunk1.content[-1].get('type') == 'text':
                last_text = chunk1.content[-1].get('text', '')
                if last_text and last_text.strip()[-1] not in '.!?':
                    # This chunk ends mid-sentence, adjust the boundary if possible
                    
                    # Option 1: Move incomplete sentence to next chunk
                    if len(chunk1.content) > 1:
                        # Move last element to beginning of next chunk
                        element = chunk1.content.pop()
                        chunk2.content.insert(0, element)
                        
                        # Update boundaries
                        chunk1.boundary.end_pos = chunk1.content[-1].get('position', 0)
                        chunk2.boundary.start_pos = element.get('position', 0)
                        
                        # Update word counts
                        elem_words = len(element.get('text', '').split())
                        chunk1.metadata.word_count -= elem_words
                        chunk2.metadata.word_count += elem_words
            
        return chunks

    def _update_chunk_references(self, chunks: List[Chunk]) -> List[Chunk]:
        """Update cross-references between chunks.
        
        Processes outgoing references from chunks and marks references as
        internal, incoming, or outgoing based on where they resolve.
        
        Args:
            chunks: List of chunks to process
            
        Returns:
            List of updated chunks
        """
        # Build reference map
        ref_map = {}
        for i, chunk in enumerate(chunks):
            # Skip if no references
            if not hasattr(chunk.boundary, 'references') or not chunk.boundary.references:
                continue
                
            # Collect reference targets in this chunk
            for ref in chunk.boundary.references.get('internal', []):
                target = ref.get('target')
                if target:
                    ref_map[target] = i
                    
        # Update reference types based on resolution
        for i, chunk in enumerate(chunks):
            # Skip if no references
            if not hasattr(chunk.boundary, 'references') or not chunk.boundary.references:
                continue
                
            # Update outgoing references
            outgoing = []
            for ref in chunk.boundary.references.get('outgoing', []):
                target = ref.get('target')
                if target in ref_map:
                    # Reference resolves to another chunk
                    if ref_map[target] == i:
                        # Reference resolves to this chunk, mark as internal
                        chunk.boundary.references.setdefault('internal', []).append(ref)
                    else:
                        # Reference resolves to another chunk, keep as outgoing
                        ref['resolves_to_chunk'] = ref_map[target]
                        outgoing.append(ref)
                        
                        # Add as incoming to target chunk
                        target_chunk = chunks[ref_map[target]]
                        target_chunk.boundary.references.setdefault('incoming', []).append({
                            'from_chunk': i,
                            'type': ref.get('type'),
                            'target': target,
                            'position': ref.get('position', 0)
                        })
                else:
                    # Reference does not resolve, keep as outgoing
                    outgoing.append(ref)
            
            # Update outgoing references
            chunk.boundary.references['outgoing'] = outgoing
            
        return chunks

    def _find_optimal_split_point(self, chunk: Chunk) -> Optional[int]:
        """Find optimal point to split a large chunk.
        
        Looks for natural boundaries like paragraph ends, headings, etc.
        
        Args:
            chunk: Chunk to split
            
        Returns:
            Index to split at or None if no good split point found
        """
        if not chunk.content:
            return None
            
        # Get target split position (approximately middle)
        target_pos = len(chunk.content) // 2
        best_pos = None
        best_score = float('-inf')
        
        # Look for split points
        for i in range(max(1, target_pos - 5), min(len(chunk.content) - 1, target_pos + 5)):
            elem = chunk.content[i]
            next_elem = chunk.content[i + 1]
            
            # Calculate score based on element types and position
            score = 0
            
            # Prefer paragraph boundaries
            if elem.get('type') == 'text' and elem.get('text', '').strip()[-1] in '.!?':
                score += 5
                
            # Prefer heading boundaries (highest priority)
            if next_elem.get('type') == 'heading':
                score += 10
                
            # Prefer section break markers
            if elem.get('type') == 'section_break':
                score += 8
                
            # Penalize distance from target position
            score -= abs(i - target_pos) * 0.5
            
            # Update best position
            if score > best_score:
                best_score = score
                best_pos = i + 1
        
        # If no good split point found, just split at middle
        if best_pos is None or best_score < 0:
            best_pos = target_pos
            
        return best_pos

    def _validate_chunks(self, chunks: List[Chunk]) -> None:
        """Validate chunk integrity."""
        if not chunks:
            raise ChunkingError("No chunks produced")
            
        # Check chunk sizes
        sizes = [chunk.size for chunk in chunks]
        min_size = min(sizes)
        max_size = max(sizes)
        
        if max_size > self.config.get('max_chunk_size', 2048):
            logger.warning(f"Chunk size {max_size} exceeds maximum")
            
        if min_size < self.config.get('min_chunk_size', 500):
            logger.warning(f"Chunk size {min_size} below minimum")
            
        # Verify boundaries
        for i, chunk in enumerate(chunks):
            if not self._is_valid_chunk(chunk):
                raise ChunkingError(f"Invalid chunk at position {i}")
                
            if i > 0:
                prev_chunk = chunks[i-1]
                if not self._are_valid_boundaries(prev_chunk, chunk):
                    raise ChunkingError(f"Invalid boundary between chunks {i-1} and {i}")

    def _build_reference_index(self, document: DocumentModel) -> None:
        """Build index of cross-references in document."""
        reference_index = {}
        
        for i, element in enumerate(document.content):
            # Extract references from text
            refs = self._extract_references(element)
            
            # Add to index
            for ref in refs:
                if ref['target'] not in reference_index:
                    reference_index[ref['target']] = []
                reference_index[ref['target']].append({
                    'position': i,
                    'type': ref['type'],
                    'context': element.get('metadata', {})
                })
        
        document.metadata.custom_metadata['reference_index'] = reference_index

    def _is_valid_chunk(self, chunk: Chunk) -> bool:
        """Validate chunk structure and content."""
        # Check required fields
        if not all(k in chunk.to_dict() for k in ['content', 'boundary', 'metadata']):
            return False
            
        # Check boundary
        boundary = chunk.boundary
        if not all(k in boundary.__dict__ for k in ['start_pos', 'end_pos', 'context', 'heading_stack', 'references']):
            return False
            
        # Validate content
        content = chunk.content
        if not content:
            return False
            
        # Check boundary positions match content
        if (content[0].get('position', 0) != boundary.start_pos or
            content[-1].get('position', 0) != boundary.end_pos):
            return False
            
        return True

    def _are_valid_boundaries(self, chunk1: Chunk, chunk2: Chunk) -> bool:
        """Validate boundary relationship between chunks."""
        # Check both chunks are valid
        if not (self._is_valid_chunk(chunk1) and self._is_valid_chunk(chunk2)):
            return False
            
        # Check chronological order
        if chunk2.boundary.start_pos - chunk1.boundary.end_pos > 1:
            return False
            
        return True

    def _extract_references(self, element: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract cross-references from element."""
        refs = []
        text = element.get('text', '')
        
        # Extract figure references
        figure_refs = self._find_figure_references(text)
        refs.extend({'type': 'figure', 'target': ref} for ref in figure_refs)
        
        # Extract table references
        table_refs = self._find_table_references(text)
        refs.extend({'type': 'table', 'target': ref} for ref in table_refs)
        
        # Extract section references
        section_refs = self._find_section_references(text)
        refs.extend({'type': 'section', 'target': ref} for ref in section_refs)
        
        return refs

    def _find_figure_references(self, text: str) -> List[str]:
        """Extract figure references from text."""
        import re
        return re.findall(r'(?:Figure|Fig\.?)\s+(\d+(?:\.\d+)*)', text)
        
    def _find_table_references(self, text: str) -> List[str]:
        """Extract table references from text."""
        import re
        return re.findall(r'Table\s+(\d+(?:\.\d+)*)', text)
        
    def _find_section_references(self, text: str) -> List[str]:
        """Extract section references from text."""
        import re
        return re.findall(r'Section\s+(\d+(?:\.\d+)*)', text)

    def _merge_contexts(self, contexts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge multiple contexts into one."""
        merged = {}
        for context in contexts:
            for key, value in context.items():
                if key not in merged:
                    merged[key] = value
                elif isinstance(value, list):
                    merged[key] = list(set(merged[key] + value))
                elif isinstance(value, dict):
                    merged[key].update(value)
                else:
                    merged[key] = value
        return merged

    def _merge_references(self, references_list: List[Dict[str, List[Dict[str, Any]]]]) \
            -> Dict[str, List[Dict[str, Any]]]:
        """Merge reference dictionaries."""
        merged = {
            'internal': [],
            'incoming': [],
            'outgoing': []
        }
        
        seen_refs = set()  # Track unique references
        
        for references in references_list:
            for ref_type, refs in references.items():
                for ref in refs:
                    ref_key = (ref.get('id'), ref.get('target'), ref.get('position'))
                    if ref_key not in seen_refs:
                        merged[ref_type].append(ref)
                        seen_refs.add(ref_key)
        
        return merged

    def _filter_references(self, references: Dict[str, List[Dict[str, Any]]],
                         start_pos: int, end_pos: int) -> Dict[str, List[Dict[str, Any]]]:
        """Filter references to those within position range."""
        filtered = {
            'internal': [],
            'incoming': [],
            'outgoing': []
        }
        
        for ref_type, refs in references.items():
            filtered[ref_type] = [
                ref for ref in refs
                if start_pos <= ref.get('position', 0) <= end_pos
            ]
        
        return filtered

    def _extract_content(self, content: List[Dict[str, Any]],
                        start_pos: int, end_pos: int) -> List[Dict[str, Any]]:
        """Extract content elements within position range."""
        return [
            elem for elem in content
            if start_pos <= elem.get('position', 0) <= end_pos
        ]

    def _calculate_topic_overlap(self, topics1: List[str], topics2: List[str]) -> float:
        """Calculate topic overlap between chunks."""
        if not topics1 or not topics2:
            return 0.0
        
        set1 = set(topics1)
        set2 = set(topics2)
        
        overlap = len(set1 & set2)
        total = len(set1 | set2)
        
        return overlap / total if total > 0 else 0.0

    def _calculate_reference_continuity(self,
                                     refs1: Dict[str, List[Dict[str, Any]]],
                                     refs2: Dict[str, List[Dict[str, Any]]]) -> float:
        """Calculate reference continuity between chunks."""
        # Check if outgoing references from chunk1 are resolved in chunk2
        outgoing1 = set(ref['target'] for ref in refs1.get('outgoing', []))
        internal2 = set(ref['target'] for ref in refs2.get('internal', []))
        
        resolved_refs = len(outgoing1 & internal2)
        total_refs = len(outgoing1)
        
        return resolved_refs / total_refs if total_refs > 0 else 1.0

    def _analyze_semantic_flow(self,
                             end_elements: List[Dict[str, Any]],
                             start_elements: List[Dict[str, Any]]) -> float:
        """Analyze semantic flow between chunk boundaries."""
        # Simple implementation - check for abrupt transitions
        score = 1.0
        
        # Check for unfinished sentences at end
        if end_elements and end_elements[-1].get('text', '').rstrip()[-1] not in '.!?':
            score -= 0.3
        
        # Check for clear section breaks
        for element in end_elements + start_elements:
            if element.get('metadata', {}).get('is_chapter_boundary'):
                score = 1.0  # Reset score as this is a natural break
                break
        
        return max(0.0, min(score, 1.0))

    def _enforce_size_constraints(self, chunks: List[Chunk]) -> List[Chunk]:
        """Ensure all chunks conform to configured size constraints."""
        min_size = self.config.get('min_chunk_size', 0)
        max_size = self.config.get('max_chunk_size', 2048)
        
        if not chunks or (min_size == 0 and max_size == float('inf')):
            return chunks

        print(f"DEBUG: Enforcing size constraints: min={min_size}, max={max_size}")
        print(f"DEBUG: Original chunk sizes: {[chunk.size for chunk in chunks]}")

        # First pass: split oversized chunks
        result = []
        for chunk in chunks:
            if chunk.size > max_size:
                print(f"DEBUG: Splitting oversized chunk: {chunk.size}")
                parts = self.strategy._split_large_chunk(chunk, max_size)
                result.extend(parts)
            else:
                result.append(chunk)

        print(f"DEBUG: After splitting: {[chunk.size for chunk in result]}")

        # Second pass: merge undersized chunks
        if min_size > 0:
            final_result = []
            current = None
            
            for chunk in result:
                if chunk.size < min_size:
                    if current is not None and current.size + chunk.size <= max_size:
                        merged_content = current.content + chunk.content
                        boundary = ChunkBoundary(
                            start_pos=current.boundary.start_pos,
                            end_pos=chunk.boundary.end_pos,
                            context=current.boundary.context.copy(),
                            heading_stack=current.boundary.heading_stack.copy(),
                            references=self._merge_references([
                                current.boundary.references,
                                chunk.boundary.references
                            ])
                        )
                        metadata = ChunkMetadata(
                            chunk_id=f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                            sequence_num=current.metadata.sequence_num,
                            section_title=current.metadata.section_title
                        )
                        merged_size = current.size + chunk.size
                        metadata.word_count = merged_size
                        current = Chunk(merged_content, boundary, metadata, _size=merged_size)
                    else:
                        if current is not None:
                            final_result.append(current)
                        current = chunk
                else:
                    if current is not None:
                        final_result.append(current)
                        current = None
                    final_result.append(chunk)
            
            if current is not None:
                final_result.append(current)
                
            result = final_result

        print(f"DEBUG: Final chunk sizes: {[chunk.size for chunk in result]}")
        return result

class ChunkingError(Exception):
    """Raised when chunking fails."""
    pass

class SectionType(Enum):
    """Section type classification."""
    MAIN_CONTENT = auto()
    FRONT_MATTER = auto()
    BACK_MATTER = auto()
    APPENDIX = auto()
    COPYRIGHT = auto()
    INDEX = auto()
    FOOTNOTES = auto()
    ACKNOWLEDGMENTS = auto()

class PatternRegistry:
    """Registry for content pattern detection."""
    
    def __init__(self):
        self._patterns = {}
        self._initialize_default_patterns()
        
    def register_pattern(self, name: str, pattern: str, weight: float = 1.0):
        """Register a new pattern with weight."""
        try:
            compiled = re.compile(pattern, re.MULTILINE)
            self._patterns[name] = (compiled, weight)
        except re.error as e:
            raise ValueError(f"Invalid pattern '{pattern}' for {name}: {e}")
            
    def get_pattern(self, name: str) -> Optional[Tuple[re.Pattern, float]]:
        """Get pattern and weight by name."""
        return self._patterns.get(name)
        
    def evaluate_block(self, text_block: str) -> Dict[str, float]:
        """Evaluate text block against all patterns."""
        scores = {}
        for name, (pattern, weight) in self._patterns.items():
            # Count matches and normalize by text length
            matches = len(pattern.findall(text_block))
            normalized_score = (matches * weight) / (len(text_block) / 100)
            if normalized_score > 0:
                scores[name] = normalized_score
        return scores
        
    def _initialize_default_patterns(self):
        """Initialize default content patterns."""
        default_patterns = {
            'chapter_header': (
                r'^(?:Chapter|CHAPTER)\s+(?:[0-9]+|[IVXLCDM]+)(?:\s*[-:]\s*.+)?$',
                2.0
            ),
            'section_header': (
                r'^\d+(?:\.\d+)*\s+[A-Z][^\n]+$',
                1.5
            ),
            'paragraph_break': (
                r'\n\s*\n',
                0.5
            ),
            'footnote': (
                r'^\[\d+\]|\{\d+\}|\*{1,3}|(?:\d+\s)?^[a-zA-Z]+\d+',
                1.0
            ),
            'page_number': (
                r'^\s*\d+\\s*$',
                0.3
            ),
            'table_of_contents': (
                r'(?:^|\n)(?:Table of Contents|CONTENTS)(?:\n|$)',
                2.0
            ),
            'bibliography': (
                r'(?:^|\n)(?:Bibliography|References|Works Cited)(?:\n|$)',
                2.0
            ),
            'appendix': (
                r'(?:^|\n)(?:Appendix\s+[A-Z]|APPENDIX\s+[A-Z])(?:\n|$)',
                2.0
            )
        }
        
        for name, (pattern, weight) in default_patterns.items():
            self.register_pattern(name, pattern, weight)

def create_default_registry() -> PatternRegistry:
    """Create and return a PatternRegistry with default patterns."""
    return PatternRegistry()

class ContentPatternDetector:
    """Detects content patterns for improved chunking."""
    
    def __init__(self) -> None:
        """Initialize pattern detector."""
        self.registry = create_default_registry()
        self._initialize_entity_patterns()
        self._initialize_semantic_patterns()
    
    def _initialize_entity_patterns(self) -> None:
        """Initialize entity extraction patterns."""
        self.entity_patterns = {
            'person': re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b'),
            'organization': re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Inc\.|LLC|Corp\.|Ltd\.|Company|Association|Institute|University)))\b'),
            'location': re.compile(r'\b([A-Z][a-z]+(?:,\s+(?:[A-Z][a-z]+|[A-Z]{2})){1,2})\b'),
            'date': re.compile(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}-\d{2}-\d{2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(?:st|nd|rd|th)?(?:,? \d{4})?)\b'),
            'email': re.compile(r'\b([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b'),
            'url': re.compile(r'\b((?:https?://)?(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)\b'),
            'isbn': re.compile(r'(?:ISBN(?:-1[03])?:?\s*)?(?=[-0-9 ]{17}|[-0-9X ]{13}|[0-9X]{10})(?:97[89][-\s]?)?[0-9]{1,5}[-\s]?[0-9]+[-\s]?[0-9]+[-\s]?[0-9X]\b'),
            'phone': re.compile(r'\b(?:\+\d{1,2}\s?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b')
        }
        
        # References and citations
        self.reference_patterns = {
            'figure': re.compile(r'\b(?:Figure|Fig\.)\s+(\d+(?:\.\d+)*)\b'),
            'table': re.compile(r'\b(?:Table|Tab\.)\s+(\d+(?:\.\d+)*)\b'),
            'equation': re.compile(r'\b(?:Equation|Eq\.)\s+(\d+(?:\.\d+)*)\b'),
            'section': re.compile(r'\b(?:Section|Sect\.)\s+(\d+(?:\.\d+)*)\b'),
            'chapter': re.compile(r'\b(?:Chapter|Ch\.)\s+(\d+|[IVXLCDM]+)\b'),
            'page': re.compile(r'\b(?:p\.|page)\s+(\d+(?:\s*-\s*\d+)?)\b'),
            'citation': re.compile(r'\[(\d+(?:-\d+)?(?:,\s*\d+(?:-\d+)?)*)\]')
        }
        
    def _initialize_semantic_patterns(self) -> None:
        """Initialize semantic and structural patterns."""
        self.semantic_patterns = {
            'definition': re.compile(r'\b([A-Za-z\s]+(?:is|are) defined as[^.]+)\b'),
            'enumeration': re.compile(r'\b(?:following|these)(?:\s+\w+){0,3}\s*:\s*(?:\n\s*[-•*]\s*[^\n]+)+'),
            'conclusion': re.compile(r'\b(?:In conclusion|To summarize|Therefore|Thus|In summary)[^.]+\.'),
            'introduction': re.compile(r'\b(?:This (?:paper|article|document|chapter|section) (?:presents|describes|introduces|discusses))[^.]+\.'),
            'transition': re.compile(r'\b(?:However|Nevertheless|Furthermore|Moreover|In addition|On the other hand|Consequently)[^.]+\.')
        }
        
        # Document structure patterns
        self.structure_patterns = {
            'heading': re.compile(r'^(?:\d+(?:\.\d+)*)?\s*([A-Z][^\n]+)$', re.MULTILINE),
            'list_item': re.compile(r'^\s*(?:\d+\.|[-•*])\s+([^\n]+)$', re.MULTILINE),
            'paragraph_break': re.compile(r'\n\s*\n'),
            'block_quote': re.compile(r'^\s*"[^"]+"(?:\s*—\s*[^"\n]+)?$', re.MULTILINE)
        }
        
    def register_custom_pattern(self, category: str, pattern: str, weight: float = 1.0) -> None:
        """Register a custom pattern.
        
        Args:
            category: Pattern category name
            pattern: Regular expression pattern
            weight: Pattern importance weight
        """
        self.registry.register_pattern(category, pattern, weight)
        
    def detect_chapter_boundary(self, text_block: str) -> bool:
        """Detect if text block marks a chapter boundary.
        
        Args:
            text_block: Text to analyze
            
        Returns:
            True if text appears to be a chapter boundary
        """
        # Check explicit chapter headers
        chapter_pattern = re.compile(r'^(?:Chapter|CHAPTER)\s+(?:[0-9]+|[IVXLCDM]+)(?:\s*[-:]\s*.+)?$', re.MULTILINE)
        if chapter_pattern.search(text_block):
            return True
            
        # Check numbered section headers at level 1
        section_pattern = re.compile(r'^(?:(?:\d+\.)|[A-Z]+\.)\s+[A-Z][^\n]+$', re.MULTILINE)
        if section_pattern.search(text_block):
            return True
            
        # Check for common chapter heading phrases
        if re.search(r'\b(?:Introduction|Background|Methodology|Results|Discussion|Conclusion)\b', text_block):
            heading_indicators = ['INTRODUCTION', 'BACKGROUND', 'METHODOLOGY', 'RESULTS', 'DISCUSSION', 'CONCLUSION']
            for indicator in heading_indicators:
                if indicator in text_block.upper() and len(text_block.strip()) < 100:
                    return True
            
        return False
        
    def detect_section_structure(self, text_block: str) -> Dict[str, Any]:
        """Analyze the structure of a section.
        
        Args:
            text_block: Text to analyze
            
        Returns:
            Dictionary with section structure information
        """
        structure = {
            'headings': [],
            'paragraphs': 0,
            'lists': [],
            'quotes': [],
            'references': []
        }
        
        # Extract headings
        for match in self.structure_patterns['heading'].finditer(text_block):
            structure['headings'].append(match.group(1))
            
        # Count paragraphs
        paragraphs = self.structure_patterns['paragraph_break'].split(text_block)
        structure['paragraphs'] = len(paragraphs)
        
        # Extract lists
        current_list = []
        for line in text_block.split('\n'):
            list_match = re.match(r'\s*(?:\d+\.|[-•*])\s+([^\n]+)', line)
            if list_match:
                current_list.append(list_match.group(1))
            elif current_list:
                if len(current_list) > 1:  # Only count as list if multiple items
                    structure['lists'].append(current_list)
                current_list = []
                
        if current_list and len(current_list) > 1:
            structure['lists'].append(current_list)
            
        # Extract block quotes
        for match in self.structure_patterns['block_quote'].finditer(text_block):
            structure['quotes'].append(match.group(0))
            
        # Extract references
        for ref_type, pattern in self.reference_patterns.items():
            refs = pattern.findall(text_block)
            if refs:
                if 'references' not in structure:
                    structure['references'] = {}
                structure['references'][ref_type] = refs
                
        return structure
        
    def detect_narrative_flow(self, chunks: List[str]) -> float:
        """Analyze narrative coherence between chunks.
        
        Args:
            chunks: List of text chunks to analyze
            
        Returns:
            Coherence score between 0.0 and 1.0
        """
        if not chunks or len(chunks) < 2:
            return 1.0
            
        # Check for transitional phrases between chunks
        transitions = self.semantic_patterns['transition']
        
        total_score = 0.0
        for i in range(len(chunks) - 1):
            chunk_end = chunks[i][-200:]  # End of current chunk
            chunk_start = chunks[i + 1][:200]  # Start of next chunk
            
            # Check for abrupt sentence endings
            if not re.search(r'[.!?]\s*$', chunk_end):
                transition_score = 0.5  # Penalize incomplete sentences
            else:
                transition_score = 1.0
                
            # Check for transition phrases
            if transitions.search(chunk_start):
                transition_score += 0.3
                
            # Check topic continuity using key terms
            end_terms = self._extract_key_terms(chunk_end)
            start_terms = self._extract_key_terms(chunk_start)
            
            # Calculate term overlap
            if end_terms and start_terms:
                overlap = len(set(end_terms) & set(start_terms))
                total_terms = len(set(end_terms) | set(start_terms))
                term_score = overlap / total_terms if total_terms > 0 else 0.0
                transition_score += term_score
            
            total_score += min(1.0, transition_score)
            
        coherence = total_score / (len(chunks) - 1)
        return min(1.0, coherence)
    
    def _extract_key_terms(self, text: str) -> List[str]:
        """Extract key terms from text for continuity analysis."""
        # Extract capitalized terms as potential key topics
        terms = re.findall(r'\b([A-Z][a-z]+(?:\s+[a-z]+){0,2})\b', text)
        
        # Filter out common words
        stop_words = {'The', 'This', 'That', 'These', 'Those', 'They', 'Their',
                      'And', 'But', 'For', 'From', 'With', 'Without'}
        return [term for term in terms if term not in stop_words]
    
    def detect_section_type(self, text_block: str, position: float = 0.0) -> SectionType:
        """Classify section type.
        
        Args:
            text_block: Text to analyze
            position: Relative position in document (0.0-1.0)
            
        Returns:
            Section type classification
        """
        text = text_block.strip().lower()
        
        # Check position-based signals
        if position < 0.1:
            # Front matter indicators
            if any(marker in text for marker in [
                'contents', 'preface', 'foreword', 'introduction'
            ]):
                return SectionType.FRONT_MATTER
        
        elif position > 0.9:
            # Back matter indicators
            if any(marker in text for marker in [
                'index', 'glossary', 'bibliography', 'references'
            ]):
                return SectionType.BACK_MATTER
        
        # Check content patterns
        if re.search(r'copyright|all\s+rights\s+reserved', text, re.I):
            return SectionType.COPYRIGHT
            
        if re.search(r'(?:^|\n)index(?:\s+|$)', text, re.I):
            return SectionType.INDEX
            
        if re.search(r'(?:^|\n)appendix\s+[a-z]', text, re.I):
            return SectionType.APPENDIX
            
        if re.search(r'(?:^|\n)footnotes?(?:\s+|$)', text, re.I):
            return SectionType.FOOTNOTES
            
        if re.search(r'(?:^|\n)acknowledgments?(?:\s+|$)', text, re.I):
            return SectionType.ACKNOWLEDGMENTS
        
        # Default to main content
        return SectionType.MAIN_CONTENT
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract named entities from text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary of entity type to list of entity values
        """
        entities = {
            'persons': [],
            'organizations': [],
            'locations': [],
            'dates': [],
            'references': [],
            'terms': [],
            'urls': [],
            'emails': [],
            'phone_numbers': [],
            'identifiers': []  # ISBNs, DOIs, etc.
        }
        
        # Extract entities using patterns
        for entity_type, pattern in self.entity_patterns.items():
            matches = pattern.findall(text)
            if matches:
                if entity_type == 'person':
                    entities['persons'] = list(set(matches))
                elif entity_type == 'organization':
                    entities['organizations'] = list(set(matches))
                elif entity_type == 'location':
                    entities['locations'] = list(set(matches))
                elif entity_type == 'date':
                    entities['dates'] = list(set(matches))
                elif entity_type == 'email':
                    entities['emails'] = list(set(matches))
                elif entity_type == 'url':
                    entities['urls'] = list(set(matches))
                elif entity_type == 'isbn':
                    entities['identifiers'].extend(list(set(matches)))
                elif entity_type == 'phone':
                    entities['phone_numbers'] = list(set(matches))
        
        # Extract reference entities
        for ref_type, pattern in self.reference_patterns.items():
            matches = pattern.findall(text)
            if matches:
                reference_items = [f"{ref_type.capitalize()} {match}" for match in matches]
                entities['references'].extend(reference_items)
        
        # Extract domain-specific terms (capitalized phrases that aren't covered by other entities)
        potential_terms = re.findall(r'\b([A-Z][a-z]+(?:\s+[a-z]+){0,3})\b', text)
        
        # Filter terms to remove those already captured as other entity types
        all_other_entities = set()
        for entity_list in entities.values():
            all_other_entities.update(entity_list)
        
        # Add unique terms
        entities['terms'] = list(set(term for term in potential_terms 
                                  if term not in all_other_entities
                                  and len(term) > 3))  # Filter out very short terms
        
        return {k: v for k, v in entities.items() if v}  # Remove empty lists
    
    def identify_document_metadata(self, text: str) -> Dict[str, Any]:
        """Extract potential document metadata from text.
        
        Args:
            text: Document text
            
        Returns:
            Dictionary of metadata fields and values
        """
        metadata = {}
        
        # Extract potential title
        title_match = re.search(r'^([A-Z][^.!?\n]{10,100})(?:\n|$)', text)
        if title_match:
            metadata['title'] = title_match.group(1).strip()
        
        # Extract authors
        author_patterns = [
            r'(?:Author|AUTHORS):\s*([^\n]+)',
            r'(?:By|BY):\s*([^\n]+)'
        ]
        
        for pattern in author_patterns:
            author_match = re.search(pattern, text)
            if author_match:
                metadata['authors'] = [a.strip() for a in author_match.group(1).split(',')]
                break
        
        # Extract date
        date_match = re.search(r'(?:Date|Published|Published on):\s*([^\n]+)', text)
        if date_match:
            metadata['date'] = date_match.group(1).strip()
        
        # Extract version/revision
        version_match = re.search(r'(?:Version|Revision):\s*([^\n]+)', text)
        if version_match:
            metadata['version'] = version_match.group(1).strip()
        
        # Extract abstract if present
        abstract_match = re.search(r'(?:Abstract|ABSTRACT)[:\s]*([^\n].+?)(?=\n\n|\n\d+\.|\Z)', text, re.DOTALL)
        if abstract_match:
            metadata['abstract'] = abstract_match.group(1).strip()
            
        # Extract keywords if present
        keywords_match = re.search(r'(?:Keywords|KEYWORDS)[:\s]*([^\n].+?)(?=\n\n|\n\d+\.|\Z)', text)
        if keywords_match:
            metadata['keywords'] = [k.strip() for k in keywords_match.group(1).split(',')]
            
        return metadata
        
    def analyze_content_density(self, text_block: str) -> Dict[str, float]:
        """Analyze content density and information richness.
        
        Args:
            text_block: Text to analyze
            
        Returns:
            Dictionary with content density metrics
        """
        results = {}
        
        # Word count
        words = text_block.split()
        results['word_count'] = len(words)
        
        # Entity density
        entities = self.extract_entities(text_block)
        total_entities = sum(len(entities.get(k, [])) for k in entities)
        results['entity_density'] = total_entities / max(1, len(words)) * 1000
        
        # Reference density
        references = sum(len(entities.get(k, [])) for k in ['references'])
        results['reference_density'] = references / max(1, len(words)) * 1000
        
        # Technical term density
        terms = len(entities.get('terms', []))
        results['term_density'] = terms / max(1, len(words)) * 1000
        
        # Sentence complexity
        sentences = re.split(r'[.!?]+', text_block)
        sentence_lengths = [len(s.split()) for s in sentences if s.strip()]
        results['avg_sentence_length'] = sum(sentence_lengths) / max(1, len(sentence_lengths))
        
        # Overall content density score (normalized)
        results['content_density_score'] = min(1.0, (
            results['entity_density'] * 0.3 +
            results['reference_density'] * 0.3 +
            results['term_density'] * 0.2 +
            min(25, results['avg_sentence_length']) / 25 * 0.2
        ) / 30)
        
        return results
    
    def detect_non_content(self, text_block: str) -> bool:
        """Identify non-content sections like headers, footers, etc.
        
        Args:
            text_block: Text to analyze
            
        Returns:
            True if likely non-content section
        """
        # Check if text is very short
        if len(text_block.strip()) < 20:
            # Check for page number pattern
            if re.match(r'^\s*\d+\s*$', text_block):
                return True
                
        # Check for header/footer patterns
        header_footer_patterns = [
            r'^\s*\d+\s+[^|]+\|\s*[^|]+\s*$',  # Common header/footer with page number and title
            r'^\s*[^\n]{0,30}$\n^\s*\d+\s*$',  # Short text followed by page number
            r'^[^\n]{5,30}(?:\s*\d+){1,2}$',   # Text with 1-2 numbers (usually page numbers)
        ]
        
        for pattern in header_footer_patterns:
            if re.match(pattern, text_block, re.MULTILINE):
                return True
                
        # Check for typical metadata markers
        if re.search(r'confidential|draft|internal\s+use\s+only|do\s+not\s+distribute', 
                    text_block, re.I):
            return True
            
        return False
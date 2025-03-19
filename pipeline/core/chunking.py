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
                 metadata: ChunkMetadata):
        self.content = content
        self.boundary = boundary
        self.metadata = metadata

    @property
    def size(self) -> int:
        """Get chunk size in words."""
        return sum(
            len(elem.get('text', '').split())
            for elem in self.content
            if elem.get('type') in ['text', 'paragraph']
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
            'metadata': self.metadata.to_dict()
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
        return cls(
            content=data['content'],
            boundary=boundary,
            metadata=metadata
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
        
        return chunks

    def _get_element_size(self, element: Dict[str, Any]) -> int:
        """Get size of element in tokens."""
        if element.get('type') == 'text':
            return len(element.get('text', '').split())
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

class TOCBasedChunkStrategy(ChunkingStrategy):
    """Chunks content based on table of contents."""
    
    def split(self, document: DocumentModel) -> List[Chunk]:
        chunks = []
        
        # Get TOC structure
        toc = document.structure.toc
        if not toc:
            # Fallback to semantic chunking if no TOC
            return SemanticChunkStrategy(self.config).split(document)
        
        # Group content by TOC sections
        current_section = None
        current_chunk = []
        sequence_num = 0
        
        for element in document.content:
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
        
        return chunks
    
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

class FixedSizeChunkStrategy(ChunkingStrategy):
    """Chunks content into fixed-size pieces."""
    
    def split(self, document: DocumentModel) -> List[Chunk]:
        chunks = []
        current_chunk = []
        current_size = 0
        target_size = self.config.get('chunk_size', 2048)
        sequence_num = 0
        
        for element in document.content:
            elem_size = self._get_element_size(element)
            
            # Try to break at natural boundaries
            if current_size >= target_size:
                if self._is_break_point(element):
                    metadata = ChunkMetadata(
                        chunk_id=f"chunk_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{sequence_num}",
                        sequence_num=sequence_num
                    )
                    metadata.word_count = current_size
                    
                    boundary = ChunkBoundary(
                        start_pos=current_chunk[0].get('position', 0),
                        end_pos=current_chunk[-1].get('position', 0),
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
                start_pos=current_chunk[0].get('position', 0),
                end_pos=current_chunk[-1].get('position', 0),
                context={},
                heading_stack=[],
                references=self._extract_references(current_chunk)
            )
            
            chunks.append(Chunk(current_chunk, boundary, metadata))
        
        return chunks
    
    def _get_element_size(self, element: Dict[str, Any]) -> int:
        """Get size of element in tokens."""
        if element.get('type') == 'text':
            return len(element.get('text', '').split())
        return 0
    
    def _is_break_point(self, element: Dict[str, Any]) -> bool:
        """Check if element is suitable break point."""
        return element.get('type') in ['paragraph_end', 'section_break']

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
        """Merge specified chunks into a single chunk.
        
        Args:
            chunk_indices: List of chunk indices to merge
            
        Returns:
            Merged chunk
        
        Raises:
            ValueError: If invalid indices provided
        """
        if not chunk_indices or not all(0 <= i < len(self.chunks) for i in chunk_indices):
            raise ValueError("Invalid chunk indices")
            
        # Sort indices to maintain order
        chunk_indices = sorted(chunk_indices)
        
        # Get chunks to merge
        chunks_to_merge = [self.chunks[i] for i in chunk_indices]
        
        # Combine content
        merged_content = []
        for chunk in chunks_to_merge:
            merged_content.extend(chunk.content)
        
        # Merge metadata
        first_chunk = chunks_to_merge[0]
        last_chunk = chunks_to_merge[-1]
        
        metadata = ChunkMetadata(
            chunk_id=f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            sequence_num=first_chunk.metadata.sequence_num,
            start_page=first_chunk.metadata.start_page,
            end_page=last_chunk.metadata.end_page,
            section_title=first_chunk.metadata.section_title
        )
        metadata.word_count = sum(chunk.metadata.word_count for chunk in chunks_to_merge)
        metadata.source_reference = {
            'merged_from': [chunk.metadata.chunk_id for chunk in chunks_to_merge],
            'original_sequence_range': (
                first_chunk.metadata.sequence_num,
                last_chunk.metadata.sequence_num
            )
        }
        
        # Create merged boundary
        boundary = ChunkBoundary(
            start_pos=first_chunk.boundary.start_pos,
            end_pos=last_chunk.boundary.end_pos,
            context=self._merge_contexts([c.boundary.context for c in chunks_to_merge]),
            heading_stack=first_chunk.boundary.heading_stack,
            references=self._merge_references([c.boundary.references for c in chunks_to_merge])
        )
        
        merged_chunk = Chunk(merged_content, boundary, metadata)
        
        # Update chunk list
        for idx in reversed(chunk_indices):
            del self.chunks[idx]
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
            chunk_file = output_dir / f'chunk_{i:04d}.json'
            with open(chunk_file, 'w') as f:
                json.dump(chunk.to_dict(), f, indent=2)
            saved_files.append(chunk_file)
            
        return saved_files
        
    def load_chunks(self, input_dir: Path) -> None:
        """Load chunks from a directory."""
        input_dir = Path(input_dir)
        self.chunks = []
        
        for chunk_file in sorted(input_dir.glob('chunk_*.json')):
            with open(chunk_file) as f:
                chunk_data = json.load(f)
                self.chunks.append(Chunk.from_dict(chunk_data))

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
        
        return chunks

    def _get_strategy(self, strategy_name: str) -> ChunkingStrategy:
        """Get chunking strategy by name."""
        strategies = {
            'semantic': SemanticChunkStrategy,
            'toc': TOCBasedChunkStrategy,
            'fixed_size': FixedSizeChunkStrategy
        }
        
        strategy_class = strategies.get(strategy_name)
        if not strategy_class:
            logger.warning(f"Unknown strategy '{strategy_name}', falling back to semantic")
            strategy_class = SemanticChunkStrategy
            
        return strategy_class(self.config)

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
        if chunk1.boundary.end_pos >= chunk2.boundary.start_pos:
            return False
            
        # No content gaps
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
    
    def register_custom_pattern(self, category: str, pattern: str, weight: float = 1.0) -> None:
        """Register a custom pattern.
        
        Args:
            category: Pattern category name
            pattern: Regular expression pattern
            weight: Pattern importance weight
        """
        self.registry.register_pattern(category, pattern, weight)

    def detect_chapter_boundary(self, text_block: str) -> bool:
        """Detect if text block marks a chapter boundary."""
        scores = self.registry.evaluate_block(text_block)
        return scores.get('chapter_header', 0.0) > 0.5

    def detect_non_content(self, text_block: str) -> bool:
        """Identify non-content sections."""
        scores = self.registry.evaluate_block(text_block)
        return scores.get('non_content', 0.0) > 0.5

    def detect_narrative_flow(self, chunks: List[str]) -> float:
        """Analyze narrative coherence between chunks."""
        if not chunks or len(chunks) < 2:
            return 1.0
            
        total_score = 0.0
        
        # Look for transition markers between chunks
        for i in range(len(chunks) - 1):
            chunk_end = chunks[i][-200:]  # Check end of chunk
            chunk_start = chunks[i + 1][:200]  # Check start of next chunk
            
            # Get transition scores
            end_scores = self.registry.evaluate_block(chunk_end)
            start_scores = self.registry.evaluate_block(chunk_start)
            
            # Combine scores
            transition_score = (
                end_scores.get('narrative_transition', 0.0) +
                start_scores.get('narrative_transition', 0.0)
            ) / 2
            
            total_score += transition_score
        
        # Calculate coherence score
        score = min(1.0, total_score / (len(chunks) - 1)) if len(chunks) > 1 else 1.0
        return score

    def detect_section_type(self, text_block: str, position: float = 0.0) -> SectionType:
        """Classify section type.
        
        Args:
            text_block: Text to analyze
            position: Relative position in document (0.0-1.0)
            
        Returns:
            Section type classification
        """
        import re
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
            
        if re.search(r'index$', text, re.I):
            return SectionType.INDEX
            
        if re.search(r'appendix\s+[a-z]', text, re.I):
            return SectionType.APPENDIX
            
        if re.search(r'footnotes?$', text, re.I):
            return SectionType.FOOTNOTES
            
        if re.search(r'acknowledgments?$', text, re.I):
            return SectionType.ACKNOWLEDGMENTS
        
        # Default to main content
        return SectionType.MAIN_CONTENT
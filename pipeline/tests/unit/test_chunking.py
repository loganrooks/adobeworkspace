"""Unit tests for chunking components."""
import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import json

from pipeline.core.chunking import (
    ChunkManager, ChunkBoundary, ChunkMetadata, Chunk,
    SemanticChunkStrategy, TOCBasedChunkStrategy, FixedSizeChunkStrategy,
    PatternRegistry, ContentPatternDetector, ChunkingError
)
from ..utils import (
    create_test_document, create_test_toc_document,
    create_large_test_document, create_test_chunk,
    assert_chunks_equal
)

class TestChunkBoundary:
    def test_chunk_boundary_initialization(self):
        """Test chunk boundary initialization with all fields."""
        boundary = ChunkBoundary(
            start_pos=0,
            end_pos=10,
            context={"topics": ["test"]},
            heading_stack=[{"level": 1, "text": "Test"}],
            references={"internal": [], "outgoing": []}
        )
        
        assert boundary.start_pos == 0
        assert boundary.end_pos == 10
        assert "topics" in boundary.context
        assert len(boundary.heading_stack) == 1
        assert "internal" in boundary.references

class TestChunkMetadata:
    def test_metadata_initialization(self):
        """Test chunk metadata initialization and properties."""
        metadata = ChunkMetadata(
            chunk_id="test_001",
            sequence_num=1,
            start_page=1,
            end_page=2,
            section_title="Test Section"
        )
        
        assert metadata.chunk_id == "test_001"
        assert metadata.sequence_num == 1
        assert metadata.start_page == 1
        assert metadata.word_count == 0  # Default value
        
    def test_metadata_serialization(self):
        """Test metadata serialization to/from dict."""
        metadata = ChunkMetadata(
            chunk_id="test_001",
            sequence_num=1
        )
        metadata.word_count = 100
        
        data = metadata.to_dict()
        restored = ChunkMetadata.from_dict(data)
        
        assert restored.chunk_id == metadata.chunk_id
        assert restored.word_count == metadata.word_count

class TestChunk:
    def test_chunk_creation(self):
        """Test chunk creation with all components."""
        chunk = create_test_chunk()
        assert len(chunk.content) == 2
        assert chunk.boundary.start_pos == 0
        assert chunk.metadata.chunk_id == "test_chunk_001"
        
    def test_chunk_size_calculation(self):
        """Test chunk size calculation based on content."""
        chunk = create_test_chunk()
        assert chunk.size == 2  # "Test content" has 2 words
        
    def test_chunk_serialization(self):
        """Test chunk serialization to/from dict."""
        chunk = create_test_chunk()
        data = chunk.to_dict()
        restored = Chunk.from_dict(data)
        assert assert_chunks_equal(chunk, restored)

class TestSemanticChunkStrategy:
    def test_semantic_chunking(self):
        """Test semantic-based document chunking."""
        config = {
            "max_chunk_size": 100,
            "overlap_tokens": 20
        }
        strategy = SemanticChunkStrategy(config)
        doc = create_test_document()
        chunks = strategy.split(doc)
        
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
        
    def test_heading_based_splits(self):
        """Test that chunks are created at major headings."""
        config = {"max_chunk_size": 1000}  # Large enough to not force size-based splits
        strategy = SemanticChunkStrategy(config)
        doc = create_test_document()
        chunks = strategy.split(doc)
        
        # Should split at Chapter 1 heading
        assert len(chunks) >= 1
        assert chunks[0].content[0]["type"] == "heading"
        assert "Chapter 1" in chunks[0].content[0]["text"]

    def test_size_based_splits(self):
        """Test that chunks are split when they exceed max size."""
        config = {"max_chunk_size": 10}  # Small size to force splits
        strategy = SemanticChunkStrategy(config)
        doc = create_large_test_document(20)  # Create a large document
        chunks = strategy.split(doc)
        
        assert len(chunks) > 1
        assert all(chunk.size <= 10 for chunk in chunks)

class TestTOCBasedChunkStrategy:
    def test_toc_based_chunking(self):
        """Test TOC-based document chunking."""
        config = {}
        strategy = TOCBasedChunkStrategy(config)
        doc = create_test_toc_document()
        chunks = strategy.split(doc)
        
        assert len(chunks) > 0
        # First real chunk should start with Chapter 1
        assert "Chapter 1" in chunks[0].content[0]["text"]
        
    def test_toc_structure_preservation(self):
        """Test that TOC structure is preserved in chunks."""
        strategy = TOCBasedChunkStrategy({})
        doc = create_test_toc_document()
        chunks = strategy.split(doc)
        
        # Check heading hierarchy in chunks
        for chunk in chunks:
            if chunk.boundary.heading_stack:
                # Each chunk should have proper heading hierarchy
                levels = [h["level"] for h in chunk.boundary.heading_stack]
                assert sorted(levels) == levels  # Levels should be in ascending order

class TestFixedSizeChunkStrategy:
    def test_fixed_size_chunking(self):
        """Test fixed-size document chunking."""
        config = {"chunk_size": 50}
        strategy = FixedSizeChunkStrategy(config)
        doc = create_large_test_document(10)
        chunks = strategy.split(doc)
        
        assert len(chunks) > 0
        assert all(chunk.size <= 50 for chunk in chunks)
        
    def test_break_point_preference(self):
        """Test that natural break points are preferred."""
        config = {"chunk_size": 100}
        strategy = FixedSizeChunkStrategy(config)
        doc = create_large_test_document(5)
        chunks = strategy.split(doc)
        
        # Check if splits occur at paragraph or section boundaries where possible
        for chunk in chunks[:-1]:  # Skip last chunk
            last_elem = chunk.content[-1]
            assert last_elem.get("type") in ["paragraph_end", "section_break", "heading"]

class TestChunkManager:
    @pytest.fixture
    def chunk_manager(self):
        """Create a chunk manager for testing."""
        config = {
            "strategy": "semantic",
            "max_chunk_size": 100,
            "overlap_tokens": 20,
            "track_references": True
        }
        return ChunkManager(config)
    
    def test_chunk_document(self, chunk_manager):
        """Test basic document chunking."""
        doc = create_test_document()
        chunks = chunk_manager.chunk_document(doc)
        
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
        
    def test_merge_chunks(self, chunk_manager):
        """Test chunk merging."""
        doc = create_large_test_document(10)
        chunks = chunk_manager.chunk_document(doc)
        
        if len(chunks) >= 2:
            merged = chunk_manager.merge_chunks([0, 1])
            assert merged.size == chunks[0].size + chunks[1].size
            assert len(chunk_manager.chunks) == len(chunks) - 1
            
    def test_split_chunk(self, chunk_manager):
        """Test chunk splitting."""
        doc = create_large_test_document(5)
        chunks = chunk_manager.chunk_document(doc)
        
        if chunks and chunks[0].size > 10:
            # Split first chunk at word 5
            new_chunks = chunk_manager.split_chunk(0, [5])
            assert len(new_chunks) == 2
            assert all(c.size > 0 for c in new_chunks)
            
    def test_save_load_chunks(self, chunk_manager):
        """Test chunk serialization to/from files."""
        doc = create_test_document()
        original_chunks = chunk_manager.chunk_document(doc)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save chunks
            save_dir = Path(tmpdir)
            saved_files = chunk_manager.save_chunks(save_dir)
            assert len(saved_files) == len(original_chunks)
            
            # Load chunks
            new_manager = ChunkManager({"strategy": "semantic"})
            new_manager.load_chunks(save_dir)
            
            # Compare chunks
            assert len(new_manager.chunks) == len(original_chunks)
            for c1, c2 in zip(original_chunks, new_manager.chunks):
                assert assert_chunks_equal(c1, c2)
                
    def test_analyze_coherence(self, chunk_manager):
        """Test chunk coherence analysis."""
        doc = create_large_test_document(6)
        chunks = chunk_manager.chunk_document(doc)
        
        if len(chunks) >= 2:
            score = chunk_manager.analyze_coherence([0, 1])
            assert 0.0 <= score <= 1.0
            
    def test_error_handling(self, chunk_manager):
        """Test error handling in chunk manager."""
        with pytest.raises(ChunkingError):
            # Try to chunk an empty document
            doc = create_test_document([])
            chunk_manager.chunk_document(doc)
            
        with pytest.raises(ValueError):
            # Try to merge invalid chunk indices
            chunk_manager.merge_chunks([999, 1000])
            
        with pytest.raises(ValueError):
            # Try to split non-existent chunk
            chunk_manager.split_chunk(999, [5])

class TestPatternRegistry:
    def test_pattern_registration(self):
        """Test pattern registration and retrieval."""
        registry = PatternRegistry()
        registry.register_pattern("test", r"test\s+pattern", 1.5)
        
        pattern = registry.get_pattern("test")
        assert pattern is not None
        assert pattern[1] == 1.5  # Check weight
        
    def test_pattern_evaluation(self):
        """Test pattern evaluation on text blocks."""
        registry = PatternRegistry()
        registry.register_pattern("test", r"test", 1.0)
        
        scores = registry.evaluate_block("this is a test block")
        assert "test" in scores
        assert scores["test"] > 0

class TestContentPatternDetector:
    def test_chapter_boundary_detection(self):
        """Test chapter boundary detection."""
        detector = ContentPatternDetector()
        assert detector.detect_chapter_boundary("Chapter 1: Introduction")
        assert not detector.detect_chapter_boundary("Regular paragraph text")
        
    def test_section_type_detection(self):
        """Test section type detection."""
        detector = ContentPatternDetector()
        text = "Table of Contents"
        position = 0.05  # Near start of document
        section_type = detector.detect_section_type(text, position)
        assert section_type.name == "FRONT_MATTER"
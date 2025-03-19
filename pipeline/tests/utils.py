"""Test utilities and fixtures for chunking tests."""
from datetime import datetime
from typing import Dict, Any, List
from pipeline.models.base import DocumentModel
from pipeline.core.chunking import ChunkBoundary, ChunkMetadata, Chunk

def create_test_document(content: List[Dict[str, Any]] = None) -> DocumentModel:
    """Create a test document with sample content."""
    if content is None:
        content = [
            {"type": "heading", "text": "Chapter 1", "level": 1, "position": 0},
            {"type": "text", "text": "This is the first paragraph.", "position": 1},
            {"type": "heading", "text": "Section 1.1", "level": 2, "position": 2},
            {"type": "text", "text": "This is the second paragraph with a reference to Figure 1.", "position": 3},
            {"type": "reference", "id": "fig1", "target": "Figure 1", "reference_type": "figure", "position": 4}
        ]
    
    doc = DocumentModel()
    doc.content = content
    return doc

def create_test_toc_document() -> DocumentModel:
    """Create a test document with TOC structure."""
    doc = DocumentModel()
    doc.content = [
        {"type": "heading", "text": "Table of Contents", "level": 1, "position": 0},
        {"type": "text", "text": "Chapter 1....1\nSection 1.1....2", "position": 1},
        {"type": "heading", "text": "Chapter 1", "level": 1, "position": 2},
        {"type": "text", "text": "First chapter content", "position": 3},
        {"type": "heading", "text": "Section 1.1", "level": 2, "position": 4},
        {"type": "text", "text": "Section content", "position": 5}
    ]
    
    doc.structure.toc = {
        "sections": [
            {
                "title": "Chapter 1",
                "level": 1,
                "id": "ch1",
                "subsections": [
                    {
                        "title": "Section 1.1",
                        "level": 2,
                        "id": "sec1.1"
                    }
                ]
            }
        ]
    }
    
    return doc

def create_large_test_document(num_paragraphs: int = 10) -> DocumentModel:
    """Create a large test document with the specified number of paragraphs."""
    content = []
    for i in range(num_paragraphs):
        if i % 3 == 0:  # Add heading every 3 paragraphs
            content.append({
                "type": "heading",
                "text": f"Section {i//3 + 1}",
                "level": 1,
                "position": len(content)
            })
        content.append({
            "type": "text",
            "text": f"This is paragraph {i + 1} with some content. " * 5,  # Make it reasonably long
            "position": len(content)
        })
    
    doc = DocumentModel()
    doc.content = content
    return doc

def create_test_chunk_boundary() -> ChunkBoundary:
    """Create a test chunk boundary."""
    return ChunkBoundary(
        start_pos=0,
        end_pos=10,
        context={"topics": ["test"], "entities": ["Test Entity"]},
        heading_stack=[{"level": 1, "text": "Test Heading", "id": "h1"}],
        references={"internal": [], "incoming": [], "outgoing": []}
    )

def create_test_chunk_metadata() -> ChunkMetadata:
    """Create test chunk metadata."""
    metadata = ChunkMetadata(
        chunk_id="test_chunk_001",
        sequence_num=1,
        start_page=1,
        end_page=2,
        section_title="Test Section"
    )
    metadata.word_count = 100
    return metadata

def create_test_chunk() -> Chunk:
    """Create a test chunk with sample content."""
    content = [
        {"type": "heading", "text": "Test Heading", "level": 1, "position": 0},
        {"type": "text", "text": "Test content", "position": 1}
    ]
    boundary = create_test_chunk_boundary()
    metadata = create_test_chunk_metadata()
    return Chunk(content, boundary, metadata)

def assert_chunks_equal(chunk1: Chunk, chunk2: Chunk) -> bool:
    """Assert that two chunks are equal, comparing all relevant attributes."""
    # Compare content
    if chunk1.content != chunk2.content:
        return False
    
    # Compare boundary
    b1, b2 = chunk1.boundary, chunk2.boundary
    if (b1.start_pos != b2.start_pos or
        b1.end_pos != b2.end_pos or
        b1.context != b2.context or
        b1.heading_stack != b2.heading_stack or
        b1.references != b2.references):
        return False
    
    # Compare metadata
    m1, m2 = chunk1.metadata, chunk2.metadata
    if (m1.chunk_id != m2.chunk_id or
        m1.sequence_num != m2.sequence_num or
        m1.start_page != m2.start_page or
        m1.end_page != m2.end_page or
        m1.section_title != m2.section_title or
        m1.word_count != m2.word_count):
        return False
    
    return True
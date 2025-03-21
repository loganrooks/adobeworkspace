"""Test utilities for the document processing pipeline."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pipeline.models.base import (
    Annotation,
    ContentElement,
    DocumentMetadata,
    DocumentModel,
    DocumentSource,
    DocumentStructure,
    ProcessingStep,
    Section,
    SupportedFormats,
    TableOfContents,
    TextElement,
    TextStyle
)
from pipeline.core.chunking import Chunk, ChunkBoundary, ChunkMetadata

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
    
    # Create metadata
    metadata = DocumentMetadata(
        title="Test Document",
        source=DocumentSource(
            type=SupportedFormats.TEXT,
            path="test.txt",
            id=str(uuid4())
        ),
        authors=["Test Author"],
        publication_date=datetime.now()
    )
    
    # Create document structure
    sections = []
    current_section = None
    current_level = 0
    
    for item in content:
        if item["type"] == "heading":
            new_section = Section(
                id=str(uuid4()),
                level=item["level"],
                title=item["text"]
            )
            
            if not sections:
                sections.append(new_section)
                current_section = new_section
            else:
                if item["level"] > current_level:
                    current_section.subsections.append(new_section)
                else:
                    sections.append(new_section)
                current_section = new_section
                current_level = item["level"]
        elif "text" in item:  # Only create text elements when text field exists
            element = TextElement(text=item["text"])
            if current_section:
                current_section.content_elements.append(element)
    
    structure = DocumentStructure(sections=sections)
    
    return DocumentModel(
        metadata=metadata,
        structure=structure,
        content=content  # Use the raw content list instead of TextElement objects
    )

def create_test_toc_document() -> DocumentModel:
    """Create a test document with TOC structure."""
    content = [
        {"type": "heading", "text": "Table of Contents", "level": 1, "position": 0},
        {"type": "text", "text": "Chapter 1....1\\nSection 1.1....2", "position": 1},
        {"type": "heading", "text": "Chapter 1", "level": 1, "position": 2},
        {"type": "text", "text": "First chapter content", "position": 3},
        {"type": "heading", "text": "Section 1.1", "level": 2, "position": 4},
        {"type": "text", "text": "Section content", "position": 5}
    ]
    
    # Create metadata
    metadata = DocumentMetadata(
        title="Test TOC Document",
        source=DocumentSource(
            type=SupportedFormats.TEXT,
            path="test_toc.txt",
            id=str(uuid4())
        ),
        authors=["Test Author"],
        publication_date=datetime.now()
    )
    
    # Create TOC structure
    toc_entries = [
        {
            "title": "Chapter 1",
            "level": 1,
            "id": "ch1",
            "children": [
                {
                    "title": "Section 1.1",
                    "level": 2,
                    "id": "sec1.1"
                }
            ]
        }
    ]
    
    structure = DocumentStructure()
    structure.toc.entries = toc_entries
    
    # Create sections
    sections = []
    current_section = None
    for item in content:
        if item["type"] == "heading" and item["text"] != "Table of Contents":
            new_section = Section(
                id=str(uuid4()),
                level=item["level"],
                title=item["text"]
            )
            if item["level"] == 1:
                sections.append(new_section)
                current_section = new_section
            else:
                if current_section:
                    current_section.subsections.append(new_section)
        elif current_section and item["type"] == "text":
            element = TextElement(text=item["text"])
            current_section.content_elements.append(element)
    
    structure.sections = sections
    
    return DocumentModel(
        metadata=metadata,
        structure=structure,
        content=content  # Use the raw content list instead of TextElement objects
    )

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
        
    # Create metadata
    metadata = DocumentMetadata(
        title="Large Test Document",
        source=DocumentSource(
            type=SupportedFormats.TEXT,
            path="large_test.txt",
            id=str(uuid4())
        ),
        authors=["Test Author"],
        publication_date=datetime.now()
    )
    
    # Create sections and structure
    sections = []
    current_section = None
    for item in content:
        if item["type"] == "heading":
            new_section = Section(
                id=str(uuid4()),
                level=item["level"],
                title=item["text"]
            )
            sections.append(new_section)
            current_section = new_section
        elif current_section and item["type"] == "text":
            element = TextElement(text=item["text"])
            current_section.content_elements.append(element)
    
    structure = DocumentStructure(sections=sections)
    
    return DocumentModel(
        metadata=metadata,
        structure=structure,
        content=content  # Use the raw content list instead of TextElement objects
    )

def create_test_chunk(id_prefix="test_chunk") -> Chunk:
    """Create a test chunk for unit tests.
    
    Args:
        id_prefix: Prefix for the chunk ID
        
    Returns:
        A test chunk
    """
    content = [
        {
            "type": "text",
            "text": "Test content",
            "position": 0
        },
        {
            "type": "paragraph",
            "text": "Additional content",
            "position": 1
        }
    ]
    
    metadata = ChunkMetadata(
        chunk_id=f"{id_prefix}_001",  # Fixed ID for testing
        sequence_num=0,
        section_title="Test Section"
    )
    metadata.word_count = 2  # Explicitly set to match the test expectation
    
    boundary = ChunkBoundary(
        start_pos=0,
        end_pos=1,
        context={},
        heading_stack=[],
        references={}
    )
    
    return Chunk(content, boundary, metadata)

def assert_chunks_equal(chunk1: Chunk, chunk2: Chunk) -> bool:
    """Assert that two chunks are equal by comparing their components."""
    assert len(chunk1.content) == len(chunk2.content)
    for c1, c2 in zip(chunk1.content, chunk2.content):
        assert c1["type"] == c2["type"]
        if "text" in c1 and "text" in c2:
            assert c1["text"] == c2["text"]
    assert chunk1.boundary.start_pos == chunk2.boundary.start_pos
    assert chunk1.boundary.end_pos == chunk2.boundary.end_pos
    assert chunk1.metadata.chunk_id == chunk2.metadata.chunk_id
    assert chunk1.metadata.sequence_num == chunk2.metadata.sequence_num
    assert chunk1.metadata.start_page == chunk2.metadata.start_page
    assert chunk1.metadata.end_page == chunk2.metadata.end_page
    assert chunk1.metadata.section_title == chunk2.metadata.section_title
    return True
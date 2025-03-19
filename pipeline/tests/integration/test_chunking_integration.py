"""Integration tests for document chunking system."""
import pytest
from pathlib import Path
import tempfile

from pipeline.core.chunking import ChunkManager
from pipeline.models.base import DocumentModel
from ..utils import (
    create_test_document,
    create_test_toc_document,
    create_large_test_document
)

class TestChunkingIntegration:
    @pytest.fixture
    def base_config(self):
        """Create base configuration for testing."""
        return {
            "strategy": "semantic",
            "max_chunk_size": 100,
            "overlap_tokens": 20,
            "track_references": True,
            "respect_boundaries": True,
            "preserve_headers": True,
            "min_chunk_size": 50
        }
    
    def test_end_to_end_chunking(self, base_config):
        """Test complete chunking workflow with all features."""
        # Initialize chunk manager
        manager = ChunkManager(base_config)
        
        # Create test document with mixed content
        doc = create_large_test_document(20)
        
        # Process document
        chunks = manager.chunk_document(doc)
        
        # Verify basic chunking
        assert len(chunks) > 0
        assert all(50 <= chunk.size <= 100 for chunk in chunks)
        
        # Verify chunk continuity
        for i in range(len(chunks) - 1):
            curr_chunk = chunks[i]
            next_chunk = chunks[i + 1]
            
            # Check position continuity
            assert curr_chunk.boundary.end_pos < next_chunk.boundary.start_pos
            
            # Check heading hierarchy consistency
            if curr_chunk.boundary.heading_stack and next_chunk.boundary.heading_stack:
                curr_level = curr_chunk.boundary.heading_stack[-1]["level"]
                next_level = next_chunk.boundary.heading_stack[0]["level"]
                assert next_level >= curr_level
    
    def test_cross_reference_handling(self, base_config):
        """Test handling of cross-references between chunks."""
        manager = ChunkManager(base_config)
        
        # Create document with cross-references
        content = [
            {"type": "heading", "text": "Section 1", "level": 1, "position": 0},
            {"type": "text", "text": "See Figure 1 below.", "position": 1},
            {"type": "text", "text": "More content " * 30, "position": 2},  # Force split
            {"type": "figure", "id": "fig1", "text": "Figure 1", "position": 3},
            {"type": "text", "text": "This is Figure 1.", "position": 4}
        ]
        doc = create_test_document(content)
        
        chunks = manager.chunk_document(doc)
        assert len(chunks) >= 2  # Should split due to size
        
        # Find reference and target chunks
        ref_chunk = next(c for c in chunks if "See Figure 1" in str(c.content))
        fig_chunk = next(c for c in chunks if "Figure 1" in str(c.content))
        
        # Verify reference tracking
        assert any(r["target"] == "Figure 1" for r in ref_chunk.boundary.references["outgoing"])
        assert any(r["id"] == "fig1" for r in fig_chunk.boundary.references["internal"])
    
    def test_strategy_switching(self, base_config):
        """Test switching between chunking strategies."""
        doc = create_test_toc_document()
        
        # Try each strategy
        strategies = ["semantic", "toc", "fixed_size"]
        chunk_sets = []
        
        for strategy in strategies:
            config = base_config.copy()
            config["strategy"] = strategy
            manager = ChunkManager(config)
            chunks = manager.chunk_document(doc)
            chunk_sets.append(chunks)
        
        # Verify each strategy produced valid but different results
        assert all(len(chunks) > 0 for chunks in chunk_sets)
        assert len(set(len(chunks) for chunks in chunk_sets)) > 1  # Different strategies should chunk differently
    
    def test_persistence_workflow(self, base_config):
        """Test complete save/load workflow with chunk manipulation."""
        manager = ChunkManager(base_config)
        doc = create_large_test_document(15)
        
        # Initial chunking
        original_chunks = manager.chunk_document(doc)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            save_dir = Path(tmpdir)
            
            # Save chunks
            manager.save_chunks(save_dir)
            
            # Modify chunks
            if len(original_chunks) >= 3:
                manager.merge_chunks([0, 1])  # Merge first two chunks
                manager.split_chunk(1, [5])   # Split another chunk
            
            # Save modified chunks
            manager.save_chunks(save_dir)
            
            # Load in new manager
            new_manager = ChunkManager(base_config)
            new_manager.load_chunks(save_dir)
            
            # Verify state
            assert len(new_manager.chunks) == len(manager.chunks)
            assert all(new_manager.analyze_coherence([i, i+1]) > 0.5 
                      for i in range(len(new_manager.chunks)-1))
    
    def test_error_recovery(self, base_config):
        """Test error handling and recovery in integrated workflow."""
        manager = ChunkManager(base_config)
        doc = create_large_test_document(10)
        
        # Process valid document first
        chunks = manager.chunk_document(doc)
        assert len(chunks) > 0
        
        # Test recovery after error
        with pytest.raises(Exception):
            manager.chunk_document(DocumentModel())  # Empty document should fail
        
        # System should still be usable
        new_chunks = manager.chunk_document(doc)
        assert len(new_chunks) > 0
        
        # Test recovery in chunk operations
        if len(chunks) >= 2:
            # Invalid merge should not affect system
            with pytest.raises(ValueError):
                manager.merge_chunks([999, 1000])
            
            # Should still be able to perform valid operations
            merged = manager.merge_chunks([0, 1])
            assert merged is not None
    
    def test_coherence_optimization(self, base_config):
        """Test chunk coherence optimization workflow."""
        manager = ChunkManager(base_config)
        doc = create_large_test_document(20)
        
        # Initial chunking
        chunks = manager.chunk_document(doc)
        original_coherence = manager.analyze_coherence()
        
        # Find chunks with low coherence
        low_coherence_pairs = []
        for i in range(len(chunks) - 1):
            score = manager.analyze_coherence([i, i+1])
            if score < 0.7:  # Threshold for low coherence
                low_coherence_pairs.append((i, i+1))
        
        # Try to improve coherence
        improved = False
        for i, j in low_coherence_pairs:
            # Try merging
            merged = manager.merge_chunks([i, j])
            new_score = manager.analyze_coherence()
            
            if new_score > original_coherence:
                improved = True
                break
        
        if low_coherence_pairs:
            assert improved, "Should be able to improve coherence through merging"
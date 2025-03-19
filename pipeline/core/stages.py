"""Core pipeline stage implementation.

This module implements the stage management system for the document
processing pipeline, handling stage transitions and validation.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pipeline.core.extension_point import PipelineExtensionPoint
from pipeline.models.base import DocumentModel


class PipelineStage(ABC):
    """Base class for pipeline stages."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize a pipeline stage.
        
        Args:
            config: Stage configuration dictionary
        """
        self.config = config
        
    @abstractmethod
    def process(self, document: DocumentModel) -> DocumentModel:
        """Process a document through this stage.
        
        Args:
            document: Document model to process
            
        Returns:
            Processed document model
        """
        pass
    
    @abstractmethod
    def validate(self, document: DocumentModel) -> bool:
        """Validate stage input/output.
        
        Args:
            document: Document to validate
            
        Returns:
            True if valid, False otherwise
        """
        pass
    
    def handle_error(self, error: Exception, document: DocumentModel) -> DocumentModel:
        """Handle stage processing errors.
        
        Args:
            error: Exception that occurred
            document: Document being processed
            
        Returns:
            Document model with error information
        """
        # Add error information to document metadata
        document.metadata.processing_history.append({
            'step': self.__class__.__name__,
            'error': {
                'type': error.__class__.__name__,
                'message': str(error),
            }
        })
        
        # Add error flag
        document.metadata.custom_metadata['has_error'] = True
        document.metadata.custom_metadata['error_stage'] = self.__class__.__name__
        
        return document


class ExtractionStage(PipelineStage):
    """Initial content extraction stage."""
    
    def process(self, document: DocumentModel) -> DocumentModel:
        """Extract content from source document.
        
        Args:
            document: Document model with source information
            
        Returns:
            Document model with extracted content
        """
        # Get appropriate processor for source type
        source_type = document.metadata.source.type
        processor = self._get_processor(source_type)
        
        if not processor:
            raise ValueError(f"No processor found for format: {source_type}")
        
        try:
            # Extract content
            content = processor.process(document.metadata.source.path)
            
            # Add processing step
            document.metadata.add_processing_step(
                'extraction',
                processor.__class__.__name__,
                getattr(processor, 'version', 'unknown')
            )
            
            # Convert extracted content to document model format
            converter = self._get_converter(source_type)
            if not converter:
                raise ValueError(f"No converter found for format: {source_type}")
                
            converted = converter.convert(content, document.metadata.source.path)
            
            # Update document with converted content
            document.content = converted.content
            document.structure = converted.structure
            document.annotations = converted.annotations
            
            return document
            
        except Exception as e:
            return self.handle_error(e, document)
            
    def validate(self, document: DocumentModel) -> bool:
        """Validate extraction stage output.
        
        Args:
            document: Document to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Check for required content
        if not document.content:
            return False
            
        # Ensure source information is present
        if not document.metadata.source:
            return False
            
        # Check for processing step
        if not any(step['step'] == 'extraction' 
                  for step in document.metadata.processing_history):
            return False
            
        return True
        
    def _get_processor(self, source_type: str) -> Optional[Any]:
        """Get processor for source type."""
        # Get processor from registry
        processors = self.config.get('processors', {})
        return processors.get(source_type)
        
    def _get_converter(self, source_type: str) -> Optional[Any]:
        """Get converter for source type."""
        # Get converter from registry
        converters = self.config.get('converters', {})
        return converters.get(source_type)


class ChunkingStage(PipelineStage):
    """Document chunking and splitting stage."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize chunking stage.
        
        Args:
            config: Stage configuration
        """
        super().__init__(config)
        self.pattern_detector = ContentPatternDetector()
    
    def process(self, document: DocumentModel) -> DocumentModel:
        """Apply chunking strategy to document.
        
        Args:
            document: Document model to chunk
            
        Returns:
            Document model with chunking information
        """
        try:
            chunk_config = self.config.get('chunking', {})
            strategy = chunk_config.get('strategy', 'default')
            chunk_manager = ChunkManager(chunk_config)
            
            # Pre-process content to identify boundaries
            self._mark_content_boundaries(document)
            
            # Apply chunking
            chunks = chunk_manager.chunk_document(document)
            
            # Post-process chunks to ensure narrative coherence
            chunks = self._ensure_chunk_coherence(chunks)
            
            # Add chunking metadata
            document.metadata.custom_metadata['chunks'] = {
                'strategy': strategy,
                'count': len(chunks),
                'boundaries': [c.get('boundary') for c in chunks],
                'section_types': self._analyze_section_types(chunks)
            }
            
            # Add chunking step
            document.metadata.add_processing_step(
                'chunking',
                'ChunkManager',
                strategy
            )
            
            return document
            
        except Exception as e:
            return self.handle_error(e, document)
    
    def _mark_content_boundaries(self, document: DocumentModel) -> None:
        """Mark natural content boundaries in document.
        
        Identifies chapter boundaries and non-content sections to
        improve chunking decisions.
        
        Args:
            document: Document to analyze
        """
        for element in document.content:
            if element.get('type') in ['text', 'paragraph']:
                text = element.get('text', '')
                
                # Mark chapter boundaries
                if self.pattern_detector.detect_chapter_boundary(text):
                    element['metadata'] = element.get('metadata', {})
                    element['metadata']['is_chapter_boundary'] = True
                
                # Mark non-content sections
                if self.pattern_detector.detect_non_content(text):
                    element['metadata'] = element.get('metadata', {})
                    element['metadata']['is_non_content'] = True
    
    def _ensure_chunk_coherence(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensure narrative coherence between chunks.
        
        Analyzes and potentially adjusts chunk boundaries to maintain
        narrative flow.
        
        Args:
            chunks: List of document chunks
            
        Returns:
            Adjusted chunks with improved coherence
        """
        # Convert chunks to text for analysis
        chunk_texts = [
            ' '.join(elem.get('text', '') 
                    for elem in chunk['content']
                    if elem.get('type') in ['text', 'paragraph'])
            for chunk in chunks
        ]
        
        # Check narrative flow
        flow_score = self.pattern_detector.detect_narrative_flow(chunk_texts)
        
        # If flow is poor, try to adjust boundaries
        if flow_score < 0.5 and len(chunks) > 1:
            adjusted_chunks = []
            for i in range(len(chunks)):
                chunk = chunks[i]
                
                # Don't adjust first chunk
                if i == 0:
                    adjusted_chunks.append(chunk)
                    continue
                
                # Try to find better break point
                prev_chunk = adjusted_chunks[-1]
                adjusted_boundary = self._find_better_boundary(
                    prev_chunk['content'][-3:],  # Last few elements of previous chunk
                    chunk['content'][:3]         # First few elements of current chunk
                )
                
                if adjusted_boundary:
                    # Update chunk boundaries
                    self._adjust_chunk_boundary(prev_chunk, chunk, adjusted_boundary)
                
                adjusted_chunks.append(chunk)
            
            return adjusted_chunks
            
        return chunks
    
    def _find_better_boundary(self, end_elements: List[Dict[str, Any]], 
                            start_elements: List[Dict[str, Any]]) -> Optional[int]:
        """Find a better chunk boundary point.
        
        Args:
            end_elements: Elements at end of first chunk
            start_elements: Elements at start of second chunk
            
        Returns:
            Index adjustment for boundary or None
        """
        # Look for natural break points
        for i, element in enumerate(end_elements):
            if element.get('metadata', {}).get('is_chapter_boundary'):
                return i - len(end_elements)  # Move boundary left
                
        for i, element in enumerate(start_elements):
            if element.get('metadata', {}).get('is_chapter_boundary'):
                return i  # Move boundary right
                
        return None
    
    def _adjust_chunk_boundary(self, chunk1: Dict[str, Any],
                             chunk2: Dict[str, Any],
                             adjustment: int) -> None:
        """Adjust the boundary between two chunks.
        
        Args:
            chunk1: First chunk
            chunk2: Second chunk
            adjustment: How many elements to move
        """
        if adjustment < 0:
            # Move elements from chunk1 to chunk2
            elements_to_move = chunk1['content'][adjustment:]
            chunk1['content'] = chunk1['content'][:adjustment]
            chunk2['content'] = elements_to_move + chunk2['content']
        else:
            # Move elements from chunk2 to chunk1
            elements_to_move = chunk2['content'][:adjustment]
            chunk2['content'] = chunk2['content'][adjustment:]
            chunk1['content'].extend(elements_to_move)
        
        # Update boundaries
        if chunk1['content']:
            chunk1['boundary']['end'] = chunk1['content'][-1].get('position', 0)
        if chunk2['content']:
            chunk2['boundary']['start'] = chunk2['content'][0].get('position', 0)
    
    def _analyze_section_types(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """Analyze section types for each chunk.
        
        Args:
            chunks: List of document chunks
            
        Returns:
            List of section type names
        """
        section_types = []
        total_chunks = len(chunks)
        
        for i, chunk in enumerate(chunks):
            # Get representative text from chunk
            text = ' '.join(
                elem.get('text', '')
                for elem in chunk['content'][:2]  # Look at first few elements
                if elem.get('type') in ['text', 'paragraph', 'heading']
            )
            
            # Calculate relative position
            position = i / total_chunks if total_chunks > 1 else 0.5
            
            # Detect section type
            section_type = self.pattern_detector.detect_section_type(text, position)
            section_types.append(section_type.name)
        
        return section_types
    
    def validate(self, document: DocumentModel) -> bool:
        """Validate chunking stage output.
        
        Args:
            document: Document to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Check for chunking metadata
        if 'chunks' not in document.metadata.custom_metadata:
            return False
            
        # Validate chunk boundaries
        chunks = document.metadata.custom_metadata['chunks']
        if not chunks.get('boundaries'):
            return False
            
        # Check for chunking step
        if not any(step['step'] == 'chunking' 
                  for step in document.metadata.processing_history):
            return False
            
        return True


class DomainProcessingStage(PipelineStage):
    """Domain-specific processing stage."""
    
    def process(self, document: DocumentModel) -> DocumentModel:
        """Apply domain-specific processing.
        
        Args:
            document: Document model to process
            
        Returns:
            Document model with domain processing
        """
        try:
            registry = DomainProcessorRegistry()
            
            # Get enabled domains from config
            domains_config = self.config.get('domains', {})
            enabled_domains = []
            for domain, config in domains_config.items():
                if config.get('enabled', False):
                    enabled_domains.append(domain)
            
            # Process with enabled domains
            if enabled_domains:
                document = registry.process(document, enabled_domains)
                
                # Add processing step
                document.metadata.add_processing_step(
                    'domain_processing',
                    'DomainProcessorRegistry',
                    ','.join(enabled_domains)
                )
            
            return document
            
        except Exception as e:
            return self.handle_error(e, document)
            
    def validate(self, document: DocumentModel) -> bool:
        """Validate domain processing stage output.
        
        Args:
            document: Document to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Check for domain processing step
        if not any(step['step'] == 'domain_processing' 
                  for step in document.metadata.processing_history):
            return False
            
        return True


class OutputGenerationStage(PipelineStage):
    """Final output generation stage."""
    
    def process(self, document: DocumentModel) -> DocumentModel:
        """Generate configured output formats.
        
        Args:
            document: Document model to output
            
        Returns:
            Document model with output information
        """
        try:
            registry = OutputHandlerRegistry()
            output_config = self.config.get('output', {})
            formats = output_config.get('formats', ['markdown'])
            
            outputs = {}
            for format_name in formats:
                handler = registry.get_handler(format_name)
                if handler:
                    # Generate output
                    output_path = handler.write(document)
                    outputs[format_name] = output_path
            
            # Add output metadata
            document.metadata.custom_metadata['outputs'] = outputs
            
            # Add processing step
            document.metadata.add_processing_step(
                'output_generation',
                'OutputHandlerRegistry',
                ','.join(formats)
            )
            
            return document
            
        except Exception as e:
            return self.handle_error(e, document)
            
    def validate(self, document: DocumentModel) -> bool:
        """Validate output generation stage.
        
        Args:
            document: Document to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Check for outputs metadata
        if 'outputs' not in document.metadata.custom_metadata:
            return False
            
        # Check for output step
        if not any(step['step'] == 'output_generation' 
                  for step in document.metadata.processing_history):
            return False
            
        return True


class PipelineStages:
    """Manages document processing stage transitions."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize pipeline stages.
        
        Args:
            config: Pipeline configuration dictionary
        """
        self.config = config
        self.stages = self._configure_stages()
        
    def process(self, document: DocumentModel, stage_name: Optional[str] = None) -> DocumentModel:
        """Process document through pipeline stages.
        
        Args:
            document: Document model to process
            stage_name: Optional specific stage to run
            
        Returns:
            Processed document model
        """
        if stage_name:
            # Run specific stage
            stage = self._get_stage(stage_name)
            if not stage:
                raise ValueError(f"Stage not found: {stage_name}")
                
            return stage.process(document)
            
        # Run full pipeline
        for stage in self.stages:
            try:
                document = stage.process(document)
                
                # Validate stage output
                if not stage.validate(document):
                    raise ValueError(f"Stage validation failed: {stage.__class__.__name__}")
                    
                # Check for errors
                if document.metadata.custom_metadata.get('has_error'):
                    break
                    
            except Exception as e:
                document = stage.handle_error(e, document)
                break
        
        return document
        
    def _configure_stages(self) -> list:
        """Configure pipeline stages from config."""
        stages = [
            ExtractionStage(self.config),
            ChunkingStage(self.config),
            DomainProcessingStage(self.config),
            OutputGenerationStage(self.config)
        ]
        
        return stages
        
    def _get_stage(self, stage_name: str) -> Optional[PipelineStage]:
        """Get stage by name.
        
        Args:
            stage_name: Name of stage to get
            
        Returns:
            Stage instance or None if not found
        """
        stage_map = {
            'extraction': ExtractionStage,
            'chunking': ChunkingStage,
            'domain_processing': DomainProcessingStage,
            'output_generation': OutputGenerationStage
        }
        
        stage_class = stage_map.get(stage_name)
        if stage_class:
            return stage_class(self.config)
        
        return None
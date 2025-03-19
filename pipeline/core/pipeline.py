"""
Core pipeline implementation for document processing.

This module implements the central pipeline that orchestrates the entire
document processing workflow.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pipeline.core.extension_point import PipelineExtensionPoint
from pipeline.core.registry import (
    ProcessorRegistry, 
    FilterRegistry, 
    OutputHandlerRegistry, 
    DomainProcessorRegistry
)


class Pipeline:
    """Core document processing pipeline.
    
    The Pipeline class is the central orchestrator for document processing.
    It manages the flow of documents through various processing stages and
    coordinates the extensions that perform the actual work.
    """
    
    def __init__(self):
        """Initialize a new Pipeline instance."""
        self._extension_points: Dict[str, PipelineExtensionPoint] = {}
        self._config: Dict[str, Any] = {}
        
        # Initialize default extension points
        self.add_extension_point('processors', ProcessorRegistry())
        self.add_extension_point('filters', FilterRegistry())
        self.add_extension_point('outputs', OutputHandlerRegistry())
        self.add_extension_point('domains', DomainProcessorRegistry())
    
    def add_extension_point(self, name: str, extension_point: PipelineExtensionPoint) -> None:
        """Register a new extension point.
        
        Args:
            name: The name of the extension point
            extension_point: The extension point implementation
        """
        self._extension_points[name] = extension_point
    
    def get_extension_point(self, name: str) -> Optional[PipelineExtensionPoint]:
        """Get an extension point by name.
        
        Args:
            name: The name of the extension point to retrieve
            
        Returns:
            The extension point implementation, or None if not found
        """
        return self._extension_points.get(name)
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the pipeline and all extension points.
        
        Args:
            config: Configuration dictionary
        """
        self._config = config.copy()
        
        # Configure each extension point with its section of the config
        for name, ext_point in self._extension_points.items():
            if name in config:
                ext_point.configure(config[name])
    
    def process_file(self, file_path: str) -> Dict[str, Any]:
        """Process a single file through the pipeline.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            Dictionary containing processing results
            
        Raises:
            ValueError: If the file format is not supported
            FileNotFoundError: If the file does not exist
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        # Get the appropriate processor for the file
        processors = self.get_extension_point('processors')
        if not processors or not isinstance(processors, ProcessorRegistry):
            raise RuntimeError("No processor registry configured")
            
        processor = processors.get_processor_for_file(file_path)
        if not processor:
            raise ValueError(f"Unsupported file format: {file_path}")
            
        # Extract content
        content = processor.process(file_path)
        
        # Apply filters
        filters = self.get_extension_point('filters')
        if filters and isinstance(filters, FilterRegistry):
            filter_types = self._config.get('content', {}).get('filters', None)
            content = filters.apply_filters(content, filter_types)
        
        # Generate outputs
        outputs = self.get_extension_point('outputs')
        output_results = {}
        if outputs and isinstance(outputs, OutputHandlerRegistry):
            output_formats = self._config.get('output', {}).get('formats', None)
            output_results = outputs.write_outputs(content, output_formats)
        
        # Apply domain-specific processing
        domains = self.get_extension_point('domains')
        domain_results = {}
        if domains and isinstance(domains, DomainProcessorRegistry):
            enabled_domains = []
            domains_config = self._config.get('endpoints', {})
            for domain, config in domains_config.items():
                if config.get('enabled', False):
                    enabled_domains.append(domain)
            domain_results = domains.process_for_domains(content, enabled_domains)
        
        return {
            'file': file_path,
            'content': content,
            'outputs': output_results,
            'domain_results': domain_results
        }
    
    def process_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Process multiple files through the pipeline.
        
        Args:
            file_paths: List of paths to files to process
            
        Returns:
            List of processing results, one per file
        """
        results = []
        for file_path in file_paths:
            try:
                result = self.process_file(file_path)
                results.append(result)
            except Exception as e:
                # In a real implementation, we would have a more sophisticated
                # error handling and recovery mechanism
                results.append({
                    'file': file_path,
                    'error': str(e)
                })
        
        return results
    
    def process_directory(self, directory_path: str, recursive: bool = False) -> List[Dict[str, Any]]:
        """Process all supported files in a directory.
        
        Args:
            directory_path: Path to the directory to process
            recursive: Whether to process subdirectories recursively
            
        Returns:
            List of processing results, one per file
        """
        if not os.path.isdir(directory_path):
            raise NotADirectoryError(f"Not a directory: {directory_path}")
            
        # Get supported formats from configuration
        supported_formats = self._config.get('input', {}).get('supported_formats', ['pdf', 'epub', 'txt', 'md'])
        
        # Find all files with supported extensions
        files_to_process = []
        if recursive:
            for root, _, files in os.walk(directory_path):
                for file in files:
                    ext = os.path.splitext(file)[1].lower().lstrip('.')
                    if ext in supported_formats:
                        files_to_process.append(os.path.join(root, file))
        else:
            for file in os.listdir(directory_path):
                full_path = os.path.join(directory_path, file)
                if os.path.isfile(full_path):
                    ext = os.path.splitext(file)[1].lower().lstrip('.')
                    if ext in supported_formats:
                        files_to_process.append(full_path)
        
        return self.process_files(files_to_process)
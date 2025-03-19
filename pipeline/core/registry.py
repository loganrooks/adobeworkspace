"""
Extension registry implementation for the document processing pipeline.

This module provides concrete implementations of extension points for
different types of extensions used in the pipeline.
"""
from typing import Any, Dict, Generic, Optional, TypeVar

from pipeline.core.extension_point import PipelineExtensionPoint

T = TypeVar('T')  # Type of extension registered with this registry


class BaseRegistry(PipelineExtensionPoint[T], Generic[T]):
    """Base implementation of extension registry.
    
    Provides common functionality for all registry types.
    """
    
    def __init__(self):
        self._extensions: Dict[str, T] = {}
    
    def register_extension(self, name: str, extension: T) -> None:
        """Register an extension with this registry.
        
        Args:
            name: The name of the extension
            extension: The extension implementation
        """
        self._extensions[name] = extension
    
    def get_extension(self, name: str) -> Optional[T]:
        """Get an extension by name.
        
        Args:
            name: The name of the extension to retrieve
            
        Returns:
            The extension implementation, or None if not found
        """
        return self._extensions.get(name)
    
    def get_extensions(self) -> Dict[str, T]:
        """Get all registered extensions.
        
        Returns:
            Dictionary mapping extension names to implementations
        """
        return self._extensions.copy()
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure all extensions managed by this registry.
        
        Args:
            config: Configuration dictionary with settings for extensions
        """
        for name, extension in self._extensions.items():
            if hasattr(extension, 'configure') and name in config:
                extension.configure(config[name])


class ProcessorRegistry(BaseRegistry[Any]):
    """Registry for document processors.
    
    Manages format-specific document processors that handle
    different input file formats (PDF, EPUB, text, etc).
    """
    
    def get_processor_for_file(self, file_path: str) -> Optional[Any]:
        """Get the appropriate processor for a file based on its extension.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            The appropriate processor for the file, or None if unsupported
        """
        # Determine file type from extension
        import os.path
        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        
        # Map extension to processor type
        ext_map = {
            'pdf': 'pdf',
            'epub': 'epub',
            'txt': 'text',
            'md': 'markdown',
            'markdown': 'markdown'
        }
        
        processor_type = ext_map.get(ext)
        if not processor_type:
            return None
            
        return self.get_extension(processor_type)


class FilterRegistry(BaseRegistry[Any]):
    """Registry for content filters.
    
    Manages filters that transform or filter content as it passes
    through the pipeline.
    """
    
    def apply_filters(self, content: Any, filter_types: Optional[list] = None) -> Any:
        """Apply all registered filters to content.
        
        Args:
            content: The content to filter
            filter_types: Optional list of filter types to apply
                          If None, all filters will be applied
                          
        Returns:
            Filtered content
        """
        filtered_content = content
        filters_to_apply = self._extensions
        
        if filter_types:
            filters_to_apply = {k: v for k, v in self._extensions.items() 
                              if k in filter_types}
                              
        for name, filter_obj in filters_to_apply.items():
            if hasattr(filter_obj, 'apply'):
                filtered_content = filter_obj.apply(filtered_content)
                
        return filtered_content


class OutputHandlerRegistry(BaseRegistry[Any]):
    """Registry for output handlers.
    
    Manages handlers that generate different output formats from
    processed content.
    """
    
    def write_outputs(self, content: Any, formats: Optional[list] = None) -> Dict[str, Any]:
        """Write content using all registered output handlers.
        
        Args:
            content: The content to write
            formats: Optional list of output formats to generate
                    If None, all registered handlers will be used
                    
        Returns:
            Dictionary mapping format names to output results
        """
        results = {}
        handlers_to_use = self._extensions
        
        if formats:
            handlers_to_use = {k: v for k, v in self._extensions.items() 
                             if k in formats}
                             
        for format_name, handler in handlers_to_use.items():
            if hasattr(handler, 'write'):
                results[format_name] = handler.write(content)
                
        return results


class DomainProcessorRegistry(BaseRegistry[Any]):
    """Registry for domain-specific processors.
    
    Manages processors that transform content for specific use cases
    like semantic search, audiobook generation, etc.
    """
    
    def process_for_domains(self, content: Any, domains: Optional[list] = None) -> Dict[str, Any]:
        """Process content for specific domains.
        
        Args:
            content: The content to process
            domains: Optional list of domains to process for
                    If None, all enabled domain processors will be used
                    
        Returns:
            Dictionary mapping domain names to processed results
        """
        results = {}
        processors_to_use = self._extensions
        
        if domains:
            processors_to_use = {k: v for k, v in self._extensions.items() 
                               if k in domains}
                               
        for domain_name, processor in processors_to_use.items():
            if hasattr(processor, 'is_enabled') and hasattr(processor, 'process'):
                if processor.is_enabled():
                    results[domain_name] = processor.process(content)
                    
        return results
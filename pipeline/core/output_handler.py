"""
Output handler interface for the document processing pipeline.

This module defines the base interface for output handlers that transform
normalized content into different output formats.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional


class OutputHandler(ABC):
    """Base interface for output handlers.
    
    Output handlers are responsible for transforming normalized document content
    into specific output formats like Markdown, plain text, or specialized formats.
    """
    
    def __init__(self):
        """Initialize a new output handler."""
        self._config = {}
        
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the output handler.
        
        Args:
            config: Configuration dictionary
        """
        self._config = config.copy()
    
    @abstractmethod
    def format_name(self) -> str:
        """Get the name of the output format.
        
        Returns:
            Name of the output format
        """
        pass
    
    @abstractmethod
    def write(self, content: Dict[str, Any], output_path: Optional[str] = None) -> str:
        """Transform and write content to the output format.
        
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
        pass
    
    def _get_config_value(self, key_path: str, default: Any = None) -> Any:
        """Get a configuration value by key path.
        
        Args:
            key_path: Key path (dot-separated)
            default: Default value to return if the key is not found
            
        Returns:
            Configuration value, or default if not found
        """
        keys = key_path.split('.')
        value = self._config
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def _get_default_output_path(self, content: Dict[str, Any]) -> str:
        """Generate a default output path based on content metadata.
        
        Args:
            content: Normalized document content
            
        Returns:
            Default output path
        """
        # Get output directory from configuration
        output_dir = self._get_config_value('directory', 'processed/')
        
        # Create directory if it doesn't exist
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Get content title/filename for the output filename
        metadata = content.get('metadata', {})
        title = metadata.get('title', '')
        filename = metadata.get('filename', '')
        
        # Use title if available, otherwise use filename without extension
        if title:
            base_name = title
        elif filename:
            base_name = Path(filename).stem
        else:
            base_name = "document"
            
        # Clean up the filename to remove invalid characters
        import re
        base_name = re.sub(r'[^\w\s-]', '', base_name).strip()
        base_name = re.sub(r'[-\s]+', '-', base_name)
        
        # Append format-specific extension
        extension = self._get_format_extension()
        
        return str(Path(output_dir) / f"{base_name}.{extension}")
    
    @abstractmethod
    def _get_format_extension(self) -> str:
        """Get the file extension for this output format.
        
        Returns:
            File extension without the leading dot
        """
        pass
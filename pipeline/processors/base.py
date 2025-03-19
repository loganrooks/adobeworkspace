"""
Base document processor interface.

This module defines the base interface for document processors.
"""
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional


class DocumentProcessor(ABC):
    """Base document processor interface.
    
    This class defines the interface for document processors. Subclasses
    should implement the process method to extract content from specific
    document formats.
    """
    
    def __init__(self):
        """Initialize a new document processor."""
        self._config = {}
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the processor with runtime options.
        
        Args:
            config: Configuration dictionary
        """
        self._config = config
    
    @abstractmethod
    def process(self, file_path: str) -> Dict[str, Any]:
        """Process a document and extract its content.
        
        Args:
            file_path: Path to the document
            
        Returns:
            Dictionary containing extracted content and metadata
            
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file format is not supported
            RuntimeError: If extraction fails
        """
        pass
    
    @abstractmethod
    def extract_toc(self, file_path: str) -> Dict[str, Any]:
        """Extract the table of contents from a document.
        
        Args:
            file_path: Path to the document
            
        Returns:
            Dictionary containing TOC structure
        """
        pass
    
    @abstractmethod
    def remove_non_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Remove non-content elements from the extracted content.
        
        Args:
            content: Extracted content dictionary
            
        Returns:
            Content dictionary with non-content elements removed
        """
        pass
    
    @abstractmethod
    def handle_footnotes(self, content: Dict[str, Any], include: bool = True, position: str = 'end') -> Dict[str, Any]:
        """Handle footnotes in the document content.
        
        Args:
            content: Extracted content dictionary
            include: Whether to include footnotes
            position: Where to position footnotes ('end' or 'inline')
            
        Returns:
            Content dictionary with footnotes handled according to parameters
        """
        pass
    
    def _is_path_valid(self, file_path: str) -> bool:
        """Check if a file path exists and is readable.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if the file exists and is readable, False otherwise
        """
        return os.path.isfile(file_path) and os.access(file_path, os.R_OK)
    
    def _get_file_extension(self, file_path: str) -> str:
        """Get the lowercase extension of a file without the dot.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Lowercase file extension without the dot
        """
        return Path(file_path).suffix.lower().lstrip('.')
    
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
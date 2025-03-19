"""
Extension point interface for the document processing pipeline.

This module defines the base interface for all pipeline extensions.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict


class PipelineExtensionPoint(ABC):
    """Base interface for pipeline extension points.
    
    Extension points are the core mechanism for extending the pipeline
    with new functionality. Each extension point represents a specific
    capability that can be plugged into the pipeline.
    """
    
    def __init__(self):
        """Initialize a new extension point."""
        self._config: Dict[str, Any] = {}
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the extension point.
        
        Args:
            config: Configuration dictionary
        """
        self._config = config.copy()
    
    @abstractmethod
    def name(self) -> str:
        """Get the name of the extension point.
        
        Returns:
            Name of the extension point
        """
        pass
    
    @abstractmethod
    def description(self) -> str:
        """Get the description of the extension point.
        
        Returns:
            Description of the extension point
        """
        pass
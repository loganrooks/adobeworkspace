"""
Extension registry for the document processing pipeline.

This module provides a registry for discovering and managing pipeline extensions.
"""
import importlib
import inspect
import pkgutil
from typing import Any, Dict, List, Optional, Type

from pipeline.core.extension_point import PipelineExtensionPoint


class ExtensionRegistry:
    """Registry for pipeline extension points.
    
    The extension registry maintains a collection of available extension points
    and provides methods to discover, register, and instantiate them.
    """
    
    def __init__(self):
        """Initialize a new extension registry."""
        self._extensions: Dict[str, Type[PipelineExtensionPoint]] = {}
    
    def register(self, extension_class: Type[PipelineExtensionPoint]) -> None:
        """Register an extension point.
        
        Args:
            extension_class: Extension point class to register
        """
        # Create a temporary instance to get the name
        temp_instance = extension_class()
        name = temp_instance.name()
        
        # Register the class
        self._extensions[name] = extension_class
    
    def get(self, name: str) -> Optional[Type[PipelineExtensionPoint]]:
        """Get an extension point by name.
        
        Args:
            name: Name of the extension point
            
        Returns:
            Extension point class, or None if not found
        """
        return self._extensions.get(name)
    
    def create(self, name: str, config: Optional[Dict[str, Any]] = None) -> Optional[PipelineExtensionPoint]:
        """Create an instance of an extension point.
        
        Args:
            name: Name of the extension point
            config: Optional configuration dictionary
            
        Returns:
            Extension point instance, or None if not found
        """
        extension_class = self.get(name)
        if extension_class:
            instance = extension_class()
            if config:
                instance.configure(config)
            return instance
        return None
    
    def list_extensions(self) -> List[str]:
        """List all registered extension points.
        
        Returns:
            List of extension point names
        """
        return list(self._extensions.keys())
    
    def discover_extensions(self, package: str) -> None:
        """Discover and register extension points in a package.
        
        Args:
            package: Package name to scan for extension points
        """
        try:
            package_module = importlib.import_module(package)
            for _, name, is_pkg in pkgutil.iter_modules(package_module.__path__):
                if is_pkg:
                    # Recursively scan subpackages
                    self.discover_extensions(f"{package}.{name}")
                else:
                    # Import module and look for extension points
                    module = importlib.import_module(f"{package}.{name}")
                    for _, obj in inspect.getmembers(module, inspect.isclass):
                        # Check if it's a subclass of PipelineExtensionPoint
                        if (issubclass(obj, PipelineExtensionPoint) and 
                            obj != PipelineExtensionPoint):
                            self.register(obj)
        except (ImportError, AttributeError):
            # Skip packages that can't be imported
            pass


# Singleton registry instance
_registry = ExtensionRegistry()


def get_registry() -> ExtensionRegistry:
    """Get the global extension registry.
    
    Returns:
        Global extension registry instance
    """
    return _registry
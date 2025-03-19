"""Core components of the document processing pipeline."""

from pipeline.core.extension_point import PipelineExtensionPoint
from pipeline.core.registry import (
    BaseRegistry,
    ProcessorRegistry,
    FilterRegistry,
    OutputHandlerRegistry,
    DomainProcessorRegistry
)
from pipeline.core.pipeline import Pipeline

__all__ = [
    'PipelineExtensionPoint',
    'BaseRegistry',
    'ProcessorRegistry',
    'FilterRegistry',
    'OutputHandlerRegistry',
    'DomainProcessorRegistry',
    'Pipeline'
]
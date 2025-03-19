"""Document processors for different file formats."""

from pipeline.processors.base import DocumentProcessor
from pipeline.processors.pdf import PDFProcessor
from pipeline.processors.epub import EPUBProcessor
from pipeline.processors.text import TextProcessor

__all__ = [
    'DocumentProcessor',
    'PDFProcessor',
    'EPUBProcessor',
    'TextProcessor'
]
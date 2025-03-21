"""Base document model classes.

This module defines the core document model classes that form the standardized
document interchange format used throughout the pipeline.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

class SupportedFormats(Enum):
    """Supported input document formats."""
    PDF = auto()
    EPUB = auto()
    MARKDOWN = auto()
    TEXT = auto()

@dataclass
class DocumentSource:
    """Source information for a document."""
    type: SupportedFormats
    path: str
    id: str = field(default_factory=lambda: str(uuid4()))

@dataclass
class ProcessingStep:
    """Record of a processing step applied to the document."""
    step: str
    timestamp: datetime
    processor: str
    version: str

@dataclass
class DocumentMetadata:
    """Document metadata including source and processing history."""
    title: str
    source: DocumentSource
    authors: List[str] = field(default_factory=list)
    publication_date: Optional[datetime] = None
    processing_history: List[ProcessingStep] = field(default_factory=list)
    custom_metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TableOfContents:
    """Table of contents structure."""
    entries: List[Dict[str, Any]] = field(default_factory=list)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Dictionary-style access to entries."""
        if hasattr(self, key):
            return getattr(self, key)
        return default

@dataclass
class DocumentStructure:
    """Document structural information."""
    sections: List['Section'] = field(default_factory=list)
    toc: TableOfContents = field(default_factory=TableOfContents)

@dataclass
class Section:
    """Document section containing content elements."""
    id: str
    level: int
    title: str = ""
    content_elements: List['ContentElement'] = field(default_factory=list)
    subsections: List['Section'] = field(default_factory=list)

@dataclass
class Annotation:
    """Content annotation with position and metadata."""
    type: str
    start: int
    end: int
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TextStyle:
    """Text formatting style information."""
    bold: bool = False
    italic: bool = False
    underline: bool = False
    font_size: Optional[float] = None
    font_family: Optional[str] = None

class ContentElement(ABC):
    """Base class for all content elements."""
    def __init__(self, id: str = None):
        self.id = id or str(uuid4())
        self.annotations: List[Annotation] = []

    @property
    @abstractmethod
    def element_type(self) -> str:
        """Get the type of content element."""
        pass

@dataclass
class TextElement(ContentElement):
    """Text content with optional styling."""
    text: str
    style: TextStyle = field(default_factory=TextStyle)

    @property
    def element_type(self) -> str:
        return "text"

@dataclass
class CellElement:
    """Table cell content."""
    id: str
    content: str
    colspan: int = 1
    rowspan: int = 1
    annotations: List[Annotation] = field(default_factory=list)

@dataclass
class TableElement(ContentElement):
    """Table with headers and cell content."""
    rows: List[List[CellElement]]
    headers: List[CellElement] = field(default_factory=list)
    caption: str = ""

    @property
    def element_type(self) -> str:
        return "table"

@dataclass
class ImageElement(ContentElement):
    """Image with metadata."""
    source: str
    alt_text: str = ""
    caption: str = ""

    @property
    def element_type(self) -> str:
        return "image"

@dataclass
class FormulaElement(ContentElement):
    """Mathematical formula in multiple formats."""
    latex: str = ""
    mathml: str = ""
    text_representation: str = ""

    @property
    def element_type(self) -> str:
        return "formula"

@dataclass
class CodeElement(ContentElement):
    """Code block with language information."""
    code: str
    language: str = ""

    @property
    def element_type(self) -> str:
        return "code"

@dataclass
class DocumentModel:
    """Top-level document model containing all document information."""
    metadata: DocumentMetadata
    structure: DocumentStructure
    content: List[ContentElement]
    annotations: List[Annotation] = field(default_factory=list)

    def add_processing_step(self, step_name: str, processor_name: str, version: str) -> None:
        """Record a processing step in document history."""
        step = ProcessingStep(
            step=step_name,
            timestamp=datetime.now(),
            processor=processor_name,
            version=version
        )
        self.metadata.processing_history.append(step)

    def to_dict(self) -> Dict[str, Any]:
        """Convert document model to dictionary format."""
        return {
            "metadata": {
                "title": self.metadata.title,
                "authors": self.metadata.authors,
                "publication_date": self.metadata.publication_date.isoformat() if self.metadata.publication_date else None,
                "source": {
                    "type": self.metadata.source.type.name.lower(),
                    "path": self.metadata.source.path,
                    "id": self.metadata.source.id
                },
                "processing_history": [
                    {
                        "step": step.step,
                        "timestamp": step.timestamp.isoformat(),
                        "processor": step.processor,
                        "version": step.version
                    }
                    for step in self.metadata.processing_history
                ],
                "custom_metadata": self.metadata.custom_metadata
            },
            "structure": self._structure_to_dict(),
            "content": [self._element_to_dict(elem) for elem in self.content],
            "annotations": [self._annotation_to_dict(ann) for ann in self.annotations]
        }

    def _structure_to_dict(self) -> Dict[str, Any]:
        """Convert document structure to dictionary format."""
        def section_to_dict(section: Section) -> Dict[str, Any]:
            return {
                "id": section.id,
                "title": section.title,
                "level": section.level,
                "content_elements": [self._element_to_dict(elem) for elem in section.content_elements],
                "subsections": [section_to_dict(subsec) for subsec in section.subsections]
            }

        return {
            "sections": [section_to_dict(section) for section in self.structure.sections],
            "toc": {
                "entries": self.structure.toc.entries
            }
        }

    def _element_to_dict(self, element: ContentElement) -> Dict[str, Any]:
        """Convert content element to dictionary format."""
        base = {
            "id": element.id,
            "element_type": element.element_type,
            "annotations": [self._annotation_to_dict(ann) for ann in element.annotations]
        }

        if isinstance(element, TextElement):
            base.update({
                "text": element.text,
                "style": {
                    "bold": element.style.bold,
                    "italic": element.style.italic,
                    "underline": element.style.underline,
                    "font_size": element.style.font_size,
                    "font_family": element.style.font_family
                }
            })
        elif isinstance(element, TableElement):
            base.update({
                "rows": [[self._cell_to_dict(cell) for cell in row] for row in element.rows],
                "headers": [self._cell_to_dict(cell) for cell in element.headers],
                "caption": element.caption
            })
        elif isinstance(element, ImageElement):
            base.update({
                "source": element.source,
                "alt_text": element.alt_text,
                "caption": element.caption
            })
        elif isinstance(element, FormulaElement):
            base.update({
                "latex": element.latex,
                "mathml": element.mathml,
                "text_representation": element.text_representation
            })
        elif isinstance(element, CodeElement):
            base.update({
                "code": element.code,
                "language": element.language
            })

        return base

    def _cell_to_dict(self, cell: CellElement) -> Dict[str, Any]:
        """Convert table cell to dictionary format."""
        return {
            "id": cell.id,
            "content": cell.content,
            "colspan": cell.colspan,
            "rowspan": cell.rowspan,
            "annotations": [self._annotation_to_dict(ann) for ann in cell.annotations]
        }

    def _annotation_to_dict(self, annotation: Annotation) -> Dict[str, Any]:
        """Convert annotation to dictionary format."""
        return {
            "type": annotation.type,
            "start": annotation.start,
            "end": annotation.end,
            "metadata": annotation.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DocumentModel':
        """Create a document model from dictionary format.
        
        Args:
            data: Dictionary containing document model data
            
        Returns:
            New DocumentModel instance
        """
        # Convert metadata
        source_data = data["metadata"]["source"]
        source = DocumentSource(
            type=SupportedFormats[source_data["type"].upper()],
            path=source_data["path"],
            id=source_data.get("id", str(uuid4()))
        )
        
        processing_history = []
        for step_data in data["metadata"].get("processing_history", []):
            step = ProcessingStep(
                step=step_data["step"],
                timestamp=datetime.fromisoformat(step_data["timestamp"]),
                processor=step_data["processor"],
                version=step_data["version"]
            )
            processing_history.append(step)
            
        metadata = DocumentMetadata(
            title=data["metadata"]["title"],
            source=source,
            authors=data["metadata"].get("authors", []),
            publication_date=datetime.fromisoformat(data["metadata"]["publication_date"]) 
                if data["metadata"].get("publication_date") else None,
            processing_history=processing_history,
            custom_metadata=data["metadata"].get("custom_metadata", {})
        )
        
        # Convert structure
        def convert_section(section_data: Dict[str, Any]) -> Section:
            content_elements = [
                cls._element_from_dict(elem_data) 
                for elem_data in section_data.get("content_elements", [])
            ]
            subsections = [
                convert_section(subsec_data) 
                for subsec_data in section_data.get("subsections", [])
            ]
            return Section(
                id=section_data["id"],
                level=section_data["level"],
                title=section_data.get("title", ""),
                content_elements=content_elements,
                subsections=subsections
            )
            
        sections = [
            convert_section(section_data) 
            for section_data in data["structure"].get("sections", [])
        ]
        
        toc = TableOfContents(entries=data["structure"].get("toc", {}).get("entries", []))
        structure = DocumentStructure(sections=sections, toc=toc)
        
        # Convert content elements
        content = [
            cls._element_from_dict(elem_data) 
            for elem_data in data["content"]
        ]
        
        # Convert annotations
        def convert_annotation(annotation_data: Dict[str, Any]) -> Annotation:
            return Annotation(
                type=annotation_data["type"],
                start=annotation_data["start"],
                end=annotation_data["end"],
                metadata=annotation_data.get("metadata", {})
            )
            
        annotations = [
            convert_annotation(ann_data) 
            for ann_data in data.get("annotations", [])
        ]
        
        return cls(
            metadata=metadata,
            structure=structure,
            content=content,
            annotations=annotations
        )

    @classmethod
    def _element_from_dict(cls, data: Dict[str, Any]) -> ContentElement:
        """Convert dictionary data to appropriate ContentElement subclass."""
        element_type = data["element_type"]
        annotations = [
            Annotation(
                type=ann_data["type"],
                start=ann_data["start"],
                end=ann_data["end"],
                metadata=ann_data.get("metadata", {})
            )
            for ann_data in data.get("annotations", [])
        ]
        
        if element_type == "text":
            style_data = data.get("style", {})
            style = TextStyle(
                bold=style_data.get("bold", False),
                italic=style_data.get("italic", False),
                underline=style_data.get("underline", False),
                font_size=style_data.get("font_size"),
                font_family=style_data.get("font_family")
            )
            element = TextElement(
                text=data["text"],
                style=style
            )
            
        elif element_type == "table":
            def convert_cell(cell_data: Dict[str, Any]) -> CellElement:
                return CellElement(
                    id=cell_data["id"],
                    content=cell_data["content"],
                    colspan=cell_data.get("colspan", 1),
                    rowspan=cell_data.get("rowspan", 1),
                    annotations=[
                        Annotation(
                            type=ann_data["type"],
                            start=ann_data["start"],
                            end=ann_data["end"],
                            metadata=ann_data.get("metadata", {})
                        )
                        for ann_data in cell_data.get("annotations", [])
                    ]
                )
                
            rows = [
                [convert_cell(cell_data) for cell_data in row]
                for row in data["rows"]
            ]
            headers = [
                convert_cell(header_data)
                for header_data in data.get("headers", [])
            ]
            element = TableElement(
                rows=rows,
                headers=headers,
                caption=data.get("caption", "")
            )
            
        elif element_type == "image":
            element = ImageElement(
                source=data["source"],
                alt_text=data.get("alt_text", ""),
                caption=data.get("caption", "")
            )
            
        elif element_type == "formula":
            element = FormulaElement(
                latex=data.get("latex", ""),
                mathml=data.get("mathml", ""),
                text_representation=data.get("text_representation", "")
            )
            
        elif element_type == "code":
            element = CodeElement(
                code=data["code"],
                language=data.get("language", "")
            )
            
        else:
            raise ValueError(f"Unknown element type: {element_type}")
            
        # Add element ID and annotations
        element.id = data["id"]
        element.annotations = annotations
        return element
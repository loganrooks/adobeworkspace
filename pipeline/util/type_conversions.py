from typing import Dict, Any
from pipeline.models.base import ContentElement

def content_element_to_dict(element: ContentElement) -> Dict[str, Any]:
    """Convert ContentElement to dictionary."""
    return {key: getattr(element, key) for key in dir(element) 
            if not key.startswith('_') and not callable(getattr(element, key))}

def dict_to_content_element(data: Dict[str, Any]) -> ContentElement:
    """Convert dictionary to ContentElement."""
    elem = ContentElement()
    for key, value in data.items():
        setattr(elem, key, value)
    return elem

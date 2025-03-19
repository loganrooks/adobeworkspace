"""
EPUB document processor implementation.

This module implements a document processor that extracts content from
EPUB files and converts it to a normalized format.
"""
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree

from pipeline.processors.base import DocumentProcessor


class EPUBProcessor(DocumentProcessor):
    """EPUB document processor.
    
    This processor extracts content from EPUB files, preserving structure
    and handling various EPUB features.
    """
    
    def __init__(self):
        """Initialize a new EPUB processor."""
        super().__init__()
    
    def process(self, file_path: str) -> Dict[str, Any]:
        """Process an EPUB document and extract its content.
        
        Args:
            file_path: Path to the EPUB document
            
        Returns:
            Dictionary containing extracted content and metadata
            
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file is not an EPUB
            RuntimeError: If extraction fails
        """
        # Validate file
        if not self._is_path_valid(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if self._get_file_extension(file_path) != 'epub':
            raise ValueError(f"Not an EPUB file: {file_path}")
        
        try:
            # Extract content and metadata
            content = self._extract_content(file_path)
            metadata = self._extract_metadata(file_path)
            
            # Post-process content
            include_footnotes = self._get_config_value('footnotes.include', True)
            footnotes_position = self._get_config_value('footnotes.position', 'end')
            
            content = self.remove_non_content(content)
            content = self.handle_footnotes(content, include_footnotes, footnotes_position)
            
            # Add metadata
            content['metadata'] = metadata
            
            return content
        
        except Exception as e:
            raise RuntimeError(f"EPUB extraction failed: {str(e)}")
    
    def extract_toc(self, file_path: str) -> Dict[str, Any]:
        """Extract the table of contents from an EPUB document.
        
        Args:
            file_path: Path to the EPUB document
            
        Returns:
            Dictionary containing TOC structure
        """
        toc = {
            'title': Path(file_path).stem,
            'sections': []
        }
        
        try:
            # EPUB files are essentially ZIP files
            if not zipfile.is_zipfile(file_path):
                return toc
                
            with zipfile.ZipFile(file_path, 'r') as epub:
                # Look for the TOC file (typically toc.ncx or content.opf)
                toc_file = None
                content_opf = None
                
                for name in epub.namelist():
                    if name.endswith('toc.ncx'):
                        toc_file = name
                    elif name.endswith('content.opf'):
                        content_opf = name
                
                # Extract TOC from toc.ncx if available
                if toc_file:
                    with epub.open(toc_file) as f:
                        toc_content = f.read()
                        # Parse XML structure
                        root = ElementTree.fromstring(toc_content)
                        
                        # Find the title
                        title_elem = root.find('.//{http://www.daisy.org/z3986/2005/ncx/}docTitle/{http://www.daisy.org/z3986/2005/ncx/}text')
                        if title_elem is not None and title_elem.text:
                            toc['title'] = title_elem.text
                        
                        # Extract nav points (sections)
                        nav_points = root.findall('.//{http://www.daisy.org/z3986/2005/ncx/}navPoint')
                        toc['sections'] = self._process_nav_points(nav_points)
                
                # If no toc.ncx or empty sections, try to extract from content.opf
                if not toc['sections'] and content_opf:
                    with epub.open(content_opf) as f:
                        opf_content = f.read()
                        # Parse XML structure
                        root = ElementTree.fromstring(opf_content)
                        
                        # Find the title
                        title_elem = root.find('.//{http://purl.org/dc/elements/1.1/}title')
                        if title_elem is not None and title_elem.text:
                            toc['title'] = title_elem.text
        
        except Exception:
            # Silently fail and return whatever we've got
            pass
            
        return toc
    
    def _process_nav_points(self, nav_points) -> List[Dict[str, Any]]:
        """Process navigation points from an EPUB TOC.
        
        Args:
            nav_points: List of NavPoint XML elements
            
        Returns:
            List of section dictionaries
        """
        sections = []
        
        for point in nav_points:
            section = {
                'id': point.get('id', ''),
                'title': '',
                'level': int(point.get('playOrder', 0)),
                'subsections': []
            }
            
            # Extract title
            text_elem = point.find('.//{http://www.daisy.org/z3986/2005/ncx/}text')
            if text_elem is not None and text_elem.text:
                section['title'] = text_elem.text
            
            # Extract subsections (recursive)
            sub_points = point.findall('.//{http://www.daisy.org/z3986/2005/ncx/}navPoint')
            if sub_points:
                section['subsections'] = self._process_nav_points(sub_points)
            
            sections.append(section)
        
        return sections
    
    def remove_non_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Remove non-content elements from the extracted content.
        
        Args:
            content: Extracted content dictionary
            
        Returns:
            Content dictionary with non-content elements removed
        """
        # Remove elements specified in configuration
        remove_elements = self._get_config_value('remove_elements', [])
        
        if 'elements' in content and remove_elements:
            filtered_elements = []
            for element in content['elements']:
                # Check if this element should be removed
                should_remove = False
                for remove_type in remove_elements:
                    if element.get('type') == remove_type:
                        should_remove = True
                        break
                
                if not should_remove:
                    filtered_elements.append(element)
            
            content['elements'] = filtered_elements
            
            # Regenerate the text from filtered elements
            if 'text_elements' in content:
                content['text'] = '\n'.join([e['text'] for e in content['text_elements'] 
                                           if e in filtered_elements])
        
        return content
    
    def handle_footnotes(self, content: Dict[str, Any], include: bool = True, position: str = 'end') -> Dict[str, Any]:
        """Handle footnotes in the document content.
        
        Args:
            content: Extracted content dictionary
            include: Whether to include footnotes
            position: Where to position footnotes ('end' or 'inline')
            
        Returns:
            Content dictionary with footnotes handled according to parameters
        """
        if not include:
            if 'footnotes' in content:
                del content['footnotes']
            return content
        
        # Handle footnotes based on position
        if position == 'end' and 'footnotes' in content and 'text' in content:
            # Append footnotes at the end
            footnotes_text = "\n\n# Footnotes\n\n"
            for i, footnote in enumerate(content['footnotes']):
                footnotes_text += f"[{i+1}] {footnote}\n"
            
            content['text'] += footnotes_text
        
        # For 'inline', we'd need to match footnote markers to their references
        # which is a more complex operation
        
        return content
    
    def _extract_content(self, file_path: str) -> Dict[str, Any]:
        """Extract content from an EPUB file.
        
        Args:
            file_path: Path to the EPUB file
            
        Returns:
            Dictionary containing extracted content
            
        Raises:
            RuntimeError: If extraction fails
        """
        result = {
            'text': '',
            'sections': [],
            'elements': [],
            'text_elements': [],
            'footnotes': []
        }
        
        try:
            # Extract TOC for section info
            toc = self.extract_toc(file_path)
            result['sections'] = toc['sections']
            
            # EPUB files are essentially ZIP files
            if not zipfile.is_zipfile(file_path):
                raise RuntimeError(f"Not a valid EPUB file: {file_path}")
                
            with zipfile.ZipFile(file_path, 'r') as epub:
                # Find the content files (HTML/XHTML)
                content_files = [name for name in epub.namelist() 
                               if name.endswith(('.html', '.xhtml', '.htm')) 
                               and not name.startswith('__MACOSX')]
                
                # Process each content file
                all_text = []
                for content_file in sorted(content_files):
                    try:
                        with epub.open(content_file) as f:
                            html_content = f.read().decode('utf-8', errors='ignore')
                            
                            # Extract text from HTML
                            text, elements = self._extract_text_from_html(html_content)
                            all_text.append(text)
                            
                            # Add elements with source file info
                            for elem in elements:
                                elem['source_file'] = content_file
                                result['elements'].append(elem)
                                
                                if elem['type'] == 'text':
                                    result['text_elements'].append(elem)
                                elif elem['type'] == 'footnote':
                                    result['footnotes'].append(elem['text'])
                    except Exception as e:
                        # Log error and continue with other files
                        print(f"Error processing {content_file}: {str(e)}")
                
                # Combine all text
                result['text'] = '\n\n'.join(all_text)
        
        except Exception as e:
            raise RuntimeError(f"Failed to extract EPUB content: {str(e)}")
            
        return result
    
    def _extract_text_from_html(self, html_content: str) -> tuple:
        """Extract plain text and elements from HTML content.
        
        Args:
            html_content: HTML content as string
            
        Returns:
            Tuple of (plain_text, elements)
        """
        # This is a simplified implementation
        # In a real-world scenario, we would use a proper HTML parser
        
        # Simple regex to remove HTML tags and extract text
        # This is not robust for all HTML, just a placeholder
        text = re.sub(r'<[^>]*>', ' ', html_content)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Create a simple element representing the whole content
        elements = [{
            'type': 'text',
            'text': text,
            'position': 0
        }]
        
        # Look for potential footnotes with a simple heuristic
        footnote_matches = re.finditer(r'\[\d+\]([^[]+)', text)
        for match in footnote_matches:
            elements.append({
                'type': 'footnote',
                'text': match.group(1).strip(),
                'position': match.start()
            })
        
        return text, elements
    
    def _extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from an EPUB file.
        
        Args:
            file_path: Path to the EPUB file
            
        Returns:
            Dictionary containing metadata
        """
        metadata = {
            'filename': Path(file_path).name,
            'size': Path(file_path).stat().st_size,
            'created': Path(file_path).stat().st_ctime,
            'modified': Path(file_path).stat().st_mtime,
            'title': '',
            'authors': [],
            'language': ''
        }
        
        try:
            # EPUB files are essentially ZIP files
            if not zipfile.is_zipfile(file_path):
                return metadata
                
            with zipfile.ZipFile(file_path, 'r') as epub:
                # Look for the content.opf file which contains metadata
                content_opf = None
                
                for name in epub.namelist():
                    if name.endswith('content.opf'):
                        content_opf = name
                        break
                
                if content_opf:
                    with epub.open(content_opf) as f:
                        opf_content = f.read()
                        # Parse XML structure
                        root = ElementTree.fromstring(opf_content)
                        
                        # Extract metadata elements
                        metadata_elem = root.find('.//{http://www.idpf.org/2007/opf}metadata')
                        if metadata_elem is not None:
                            # Title
                            title_elem = metadata_elem.find('.//{http://purl.org/dc/elements/1.1/}title')
                            if title_elem is not None and title_elem.text:
                                metadata['title'] = title_elem.text
                            
                            # Authors
                            author_elems = metadata_elem.findall('.//{http://purl.org/dc/elements/1.1/}creator')
                            for author_elem in author_elems:
                                if author_elem.text:
                                    metadata['authors'].append(author_elem.text)
                            
                            # Language
                            lang_elem = metadata_elem.find('.//{http://purl.org/dc/elements/1.1/}language')
                            if lang_elem is not None and lang_elem.text:
                                metadata['language'] = lang_elem.text
        
        except Exception:
            # Silently fail and return whatever metadata we've got
            pass
            
        return metadata
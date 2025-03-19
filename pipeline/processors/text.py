"""
Text and Markdown document processor implementation.

This module implements a document processor that extracts content from
plain text and Markdown files and converts it to a normalized format.
"""
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pipeline.processors.base import DocumentProcessor


class TextProcessor(DocumentProcessor):
    """Text and Markdown document processor.
    
    This processor extracts content from plain text and Markdown files,
    preserving structure and handling various text features.
    """
    
    def __init__(self):
        """Initialize a new text processor."""
        super().__init__()
    
    def process(self, file_path: str) -> Dict[str, Any]:
        """Process a text document and extract its content.
        
        Args:
            file_path: Path to the text document
            
        Returns:
            Dictionary containing extracted content and metadata
            
        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file format is not supported
            RuntimeError: If extraction fails
        """
        # Validate file
        if not self._is_path_valid(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        ext = self._get_file_extension(file_path)
        if ext not in ['txt', 'text', 'md', 'markdown']:
            raise ValueError(f"Unsupported file format: {ext}")
        
        try:
            # Extract content
            is_markdown = ext in ['md', 'markdown']
            content = self._extract_content(file_path, is_markdown)
            
            # Post-process content
            include_footnotes = self._get_config_value('footnotes.include', True)
            footnotes_position = self._get_config_value('footnotes.position', 'end')
            
            content = self.remove_non_content(content)
            content = self.handle_footnotes(content, include_footnotes, footnotes_position)
            
            # Add metadata
            content['metadata'] = self._extract_metadata(file_path)
            
            return content
            
        except Exception as e:
            raise RuntimeError(f"Text extraction failed: {str(e)}")
    
    def extract_toc(self, file_path: str) -> Dict[str, Any]:
        """Extract the table of contents from a text document.
        
        For text files, this analyzes headings to build a TOC.
        For Markdown files, it looks for # headings.
        
        Args:
            file_path: Path to the document
            
        Returns:
            Dictionary containing TOC structure
        """
        toc = {
            'title': Path(file_path).stem,
            'sections': []
        }
        
        try:
            # Determine if it's Markdown
            is_markdown = self._get_file_extension(file_path) in ['md', 'markdown']
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Extract sections
            if is_markdown:
                # For Markdown: Look for headings with # syntax
                headings = re.finditer(r'^(#+)\s+(.+)$', content, re.MULTILINE)
                
                for match in headings:
                    level = len(match.group(1))  # Number of # characters
                    title = match.group(2).strip()
                    section = {
                        'id': f"section-{len(toc['sections'])+1}",
                        'title': title,
                        'level': level,
                        'position': match.start(),
                        'subsections': []
                    }
                    
                    # Add to appropriate parent based on heading level
                    if level == 1:
                        toc['sections'].append(section)
                    else:
                        # Find the closest parent section with a lower level
                        parent = None
                        for potential_parent in reversed(toc['sections']):
                            if potential_parent['level'] < level:
                                parent = potential_parent
                                break
                        
                        if parent:
                            parent['subsections'].append(section)
                        else:
                            # No appropriate parent, add to top level
                            toc['sections'].append(section)
            else:
                # For plain text: Look for lines in all caps or with underlines
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    # Check for underlined headings
                    if i > 0 and re.match(r'^[=\-]{3,}$', line.strip()):
                        title = lines[i-1].strip()
                        level = 1 if '=' in line else 2
                        section = {
                            'id': f"section-{len(toc['sections'])+1}",
                            'title': title,
                            'level': level,
                            'position': content.find(title),
                            'subsections': []
                        }
                        toc['sections'].append(section)
                    
                    # Check for ALL CAPS headings (at least 3 words)
                    elif re.match(r'^[A-Z][A-Z\s]{10,}$', line.strip()):
                        words = line.split()
                        if len(words) >= 3:
                            section = {
                                'id': f"section-{len(toc['sections'])+1}",
                                'title': line.strip(),
                                'level': 1,
                                'position': content.find(line),
                                'subsections': []
                            }
                            toc['sections'].append(section)
            
            # Try to extract title from first lines
            if not toc['title'] or toc['title'] == Path(file_path).stem:
                lines = content.split('\n', 3)
                for line in lines:
                    line = line.strip()
                    if line and len(line) < 100:  # Reasonable title length
                        toc['title'] = line
                        break
        
        except Exception:
            # Silently fail and return what we have
            pass
            
        return toc
    
    def remove_non_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Remove non-content elements from the extracted content.
        
        Args:
            content: Extracted content dictionary
            
        Returns:
            Content dictionary with non-content elements removed
        """
        # Get elements to remove from configuration
        remove_elements = self._get_config_value('remove_elements', [])
        
        if not remove_elements:
            return content
        
        # Look for elements to remove
        text = content.get('text', '')
        elements_to_remove = []
        
        for element_type in remove_elements:
            if element_type == 'copyright':
                # Look for copyright notices
                copyright_matches = re.finditer(r'copyright\s+(?:\(c\)|\©)?\s*\d{4}.*?\n', 
                                             text, re.IGNORECASE)
                for match in copyright_matches:
                    elements_to_remove.append((match.start(), match.end()))
            
            elif element_type == 'index':
                # Look for index sections
                index_match = re.search(r'\bindex\b.*?(?=\n\n|\Z)', 
                                      text, re.IGNORECASE | re.DOTALL)
                if index_match:
                    elements_to_remove.append((index_match.start(), index_match.end()))
            
            elif element_type == 'advertisements':
                # Look for ad-like content
                ad_patterns = [
                    r'(?i)advertisement\s+.*?(?=\n\n|\Z)',
                    r'(?i)sponsored\s+content\s+.*?(?=\n\n|\Z)'
                ]
                for pattern in ad_patterns:
                    for match in re.finditer(pattern, text, re.DOTALL):
                        elements_to_remove.append((match.start(), match.end()))
        
        # Remove elements from text
        if elements_to_remove:
            # Sort in reverse order to avoid invalidating positions
            elements_to_remove.sort(reverse=True)
            text_parts = list(text)
            for start, end in elements_to_remove:
                text_parts[start:end] = []
            
            content['text'] = ''.join(text_parts)
        
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
        if position == 'end' and 'footnotes' in content and content['footnotes'] and 'text' in content:
            # Append footnotes at the end
            footnotes_text = "\n\n# Footnotes\n\n"
            for i, footnote in enumerate(content['footnotes']):
                footnotes_text += f"[{i+1}] {footnote['text']}\n"
            
            content['text'] += footnotes_text
        
        return content
    
    def _extract_content(self, file_path: str, is_markdown: bool) -> Dict[str, Any]:
        """Extract content from a text file.
        
        Args:
            file_path: Path to the text file
            is_markdown: Whether the file is Markdown
            
        Returns:
            Dictionary containing extracted content
            
        Raises:
            RuntimeError: If extraction fails
        """
        result = {
            'text': '',
            'elements': [],
            'footnotes': [],
            'sections': []
        }
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Store raw text
            result['text'] = content
            
            # Extract TOC and sections
            toc = self.extract_toc(file_path)
            result['sections'] = toc['sections']
            
            # Process content based on type
            if is_markdown:
                # Process Markdown-specific elements
                
                # Extract footnotes
                # Look for [^1]: style footnotes
                footnotes = re.finditer(r'\[\^(\d+)\]:\s*([^\n]+(?:\n[^\[].*?)*?)(?=\n\[\^|$)', 
                                      content, re.MULTILINE)
                
                for match in footnotes:
                    footnote_id = match.group(1)
                    footnote_text = match.group(2).strip()
                    result['footnotes'].append({
                        'id': footnote_id,
                        'text': footnote_text,
                        'position': match.start()
                    })
                
                # Extract links
                links = re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', content)
                for match in links:
                    link_text = match.group(1)
                    link_url = match.group(2)
                    result['elements'].append({
                        'type': 'link',
                        'text': link_text,
                        'url': link_url,
                        'position': match.start()
                    })
                
                # Extract images
                images = re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', content)
                for match in images:
                    alt_text = match.group(1)
                    image_url = match.group(2)
                    result['elements'].append({
                        'type': 'image',
                        'alt_text': alt_text,
                        'url': image_url,
                        'position': match.start()
                    })
                
                # Extract code blocks
                code_blocks = re.finditer(r'```([^\n]*)\n(.*?)```', content, re.DOTALL)
                for match in code_blocks:
                    language = match.group(1).strip()
                    code = match.group(2)
                    result['elements'].append({
                        'type': 'code',
                        'language': language,
                        'code': code,
                        'position': match.start()
                    })
            else:
                # Process plain text
                # For plain text, just look for patterns that might indicate structure
                
                # Look for potential sections with all-caps headings
                cap_headings = re.finditer(r'^([A-Z][A-Z\s]{10,})$', content, re.MULTILINE)
                for match in cap_headings:
                    heading_text = match.group(1)
                    result['elements'].append({
                        'type': 'heading',
                        'text': heading_text,
                        'level': 1,
                        'position': match.start()
                    })
                
                # Look for potential footnotes with [1], [2], etc. markers
                footnote_refs = re.finditer(r'\[(\d+)\]([^\n\[]+)', content)
                for match in footnote_refs:
                    footnote_id = match.group(1)
                    footnote_text = match.group(2).strip()
                    result['footnotes'].append({
                        'id': footnote_id,
                        'text': footnote_text,
                        'position': match.start()
                    })
        
        except Exception as e:
            raise RuntimeError(f"Failed to extract text content: {str(e)}")
            
        return result
    
    def _extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from a text file.
        
        Args:
            file_path: Path to the text file
            
        Returns:
            Dictionary containing metadata
        """
        path = Path(file_path)
        metadata = {
            'filename': path.name,
            'size': path.stat().st_size,
            'created': path.stat().st_ctime,
            'modified': path.stat().st_mtime,
            'title': path.stem
        }
        
        # Try to extract more metadata from file contents
        try:
            # Look for potential title in first lines
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_lines = []
                for _ in range(5):  # Read first 5 lines
                    line = f.readline().strip()
                    if line:
                        first_lines.append(line)
            
            # Use first non-empty line as title if it's reasonably short
            if first_lines and len(first_lines[0]) < 100:
                metadata['title'] = first_lines[0]
                
        except Exception:
            # Silently fail and return what we have
            pass
            
        return metadata
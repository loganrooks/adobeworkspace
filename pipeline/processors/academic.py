"""
Academic document processor implementation.

This module implements a processor for academic and scientific documents
like research papers, journal articles, and theses.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from pipeline.processors.base import DocumentProcessor


class AcademicDocumentProcessor(DocumentProcessor):
    """Processor for academic and scientific documents.
    
    This processor specializes in handling academic content such as:
    - Research papers
    - Journal articles
    - Theses and dissertations
    - Scientific reports
    """
    
    def __init__(self):
        """Initialize a new academic document processor."""
        super().__init__()
    
    def process(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Process normalized content with academic document handling.
        
        Args:
            content: Normalized document content
            
        Returns:
            Processed document content
            
        Raises:
            ValueError: If content is not in the expected format
        """
        if not content or not isinstance(content, dict):
            raise ValueError("Invalid content format: expected a dictionary")
        
        # Extract citations
        content = self._extract_citations(content)
        
        # Process equations
        content = self._process_equations(content)
        
        # Extract figures and tables
        content = self._process_figures_and_tables(content)
        
        # Extract abstract
        content = self._extract_abstract(content)
        
        # Process references
        content = self._process_references(content)
        
        return content
    
    def _extract_citations(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract citations from academic content.
        
        Args:
            content: Document content
            
        Returns:
            Content with extracted citations
        """
        if 'text' not in content:
            return content
        
        # Look for citation patterns in text
        text = content['text']
        
        # Common citation formats: [1], (Smith et al., 2020), etc.
        citation_patterns = [
            r'\[(\d+(?:,\s*\d+)*)\]',                         # [1] or [1, 2, 3]
            r'\((\w+(?:\s+et\s+al\.)?(?:,\s*\d{4})?)\)',      # (Smith et al., 2020)
            r'\((\w+\s+and\s+\w+(?:,\s*\d{4})?)\)'            # (Smith and Jones, 2020)
        ]
        
        citations = []
        
        for pattern in citation_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                citation_text = match.group(1)
                citation = {
                    'type': 'citation',
                    'text': citation_text,
                    'position': match.start()
                }
                
                # Determine citation style
                if re.match(r'\d+', citation_text):
                    citation['style'] = 'numeric'
                elif re.search(r'et\s+al', citation_text):
                    citation['style'] = 'author_year'
                elif re.search(r'\w+\s+and\s+\w+', citation_text):
                    citation['style'] = 'author_year'
                else:
                    citation['style'] = 'unknown'
                
                citations.append(citation)
        
        # Add citations to content
        if citations:
            if 'elements' not in content:
                content['elements'] = []
            content['elements'].extend(citations)
        
        return content
    
    def _process_equations(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Process mathematical equations in academic content.
        
        Args:
            content: Document content
            
        Returns:
            Content with processed equations
        """
        if 'text' not in content:
            return content
        
        # Look for equation patterns
        text = content['text']
        elements = content.get('elements', [])
        
        # Look for LaTeX-style equations
        # Inline equations: $...$
        inline_matches = re.finditer(r'\$([^$]+)\$', text)
        
        # Display equations: $$...$$
        display_matches = re.finditer(r'\$\$([^$]+)\$\$', text)
        
        equations = []
        
        # Process inline equations
        for match in inline_matches:
            equation_text = match.group(1)
            equation = {
                'type': 'equation',
                'text': equation_text,
                'display': False,
                'position': match.start()
            }
            equations.append(equation)
        
        # Process display equations
        for match in display_matches:
            equation_text = match.group(1)
            equation = {
                'type': 'equation',
                'text': equation_text,
                'display': True,
                'position': match.start()
            }
            equations.append(equation)
        
        # Check for existing equation elements
        for element in elements:
            if element.get('type') == 'equation':
                # Clean up equation format
                equation_text = element.get('text', '')
                element['text'] = self._clean_equation_format(equation_text)
        
        # Add new equations to content
        if equations:
            if 'elements' not in content:
                content['elements'] = []
            content['elements'].extend(equations)
        
        return content
    
    def _clean_equation_format(self, equation_text: str) -> str:
        """Clean up equation formatting.
        
        Args:
            equation_text: Raw equation text
            
        Returns:
            Cleaned equation text
        """
        # Remove excessive whitespace
        clean_text = re.sub(r'\s+', ' ', equation_text).strip()
        
        # Fix common formatting issues
        clean_text = clean_text.replace('\\\\', '\\')
        
        return clean_text
    
    def _process_figures_and_tables(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Process figures and tables in academic content.
        
        Args:
            content: Document content
            
        Returns:
            Content with processed figures and tables
        """
        if 'elements' not in content:
            return content
        
        elements = content.get('elements', [])
        
        # Extract and process figure and table captions
        for i, element in enumerate(elements):
            if element.get('type') == 'figure':
                # Process figure caption
                caption = element.get('caption', '')
                if caption:
                    # Extract figure number if present
                    figure_match = re.search(r'figure\s+(\d+)[:.]\s*(.*)', caption, re.IGNORECASE)
                    if figure_match:
                        elements[i]['number'] = figure_match.group(1)
                        elements[i]['caption'] = figure_match.group(2).strip()
            
            elif element.get('type') == 'table':
                # Process table caption
                caption = element.get('caption', '')
                if caption:
                    # Extract table number if present
                    table_match = re.search(r'table\s+(\d+)[:.]\s*(.*)', caption, re.IGNORECASE)
                    if table_match:
                        elements[i]['number'] = table_match.group(1)
                        elements[i]['caption'] = table_match.group(2).strip()
        
        return content
    
    def _extract_abstract(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and process the abstract from academic content.
        
        Args:
            content: Document content
            
        Returns:
            Content with processed abstract
        """
        if 'text' not in content:
            return content
        
        # Look for abstract section
        text = content['text']
        
        # Common patterns for abstract sections
        abstract_patterns = [
            r'Abstract\s*\n+(.*?)(?=\n\s*(?:Introduction|Keywords|Background)|\Z)',
            r'ABSTRACT\s*\n+(.*?)(?=\n\s*(?:Introduction|Keywords|Background)|\Z)',
            r'Abstract[:.-]\s*(.*?)(?=\n\s*(?:Introduction|Keywords|Background)|\Z)'
        ]
        
        for pattern in abstract_patterns:
            abstract_match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if abstract_match:
                abstract_text = abstract_match.group(1).strip()
                
                # Create or update metadata with abstract
                if 'metadata' not in content:
                    content['metadata'] = {}
                
                content['metadata']['abstract'] = abstract_text
                
                # Also create an abstract element
                abstract_element = {
                    'type': 'abstract',
                    'text': abstract_text,
                    'position': abstract_match.start()
                }
                
                if 'elements' not in content:
                    content['elements'] = []
                
                # Check if we already have an abstract element
                has_abstract = False
                for element in content['elements']:
                    if element.get('type') == 'abstract':
                        has_abstract = True
                        break
                
                if not has_abstract:
                    content['elements'].append(abstract_element)
                
                break  # Stop after finding the first valid abstract
        
        return content
    
    def _process_references(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Process the references section in academic content.
        
        Args:
            content: Document content
            
        Returns:
            Content with processed references
        """
        if 'text' not in content:
            return content
        
        # Look for references section
        text = content['text']
        
        # Common patterns for references sections
        refs_patterns = [
            r'References\s*\n+(.*?)(?=\n\s*(?:Appendix|Acknowledgements)|\Z)',
            r'REFERENCES\s*\n+(.*?)(?=\n\s*(?:Appendix|Acknowledgements)|\Z)',
            r'Bibliography\s*\n+(.*?)(?=\n\s*(?:Appendix|Acknowledgements)|\Z)'
        ]
        
        references_list = []
        
        for pattern in refs_patterns:
            refs_match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if refs_match:
                refs_text = refs_match.group(1).strip()
                
                # Split references into individual entries
                # This is simplified and might need adjustment based on citation style
                ref_entries = re.split(r'\n\s*(?:\[\d+\]|\d+\.|\w+,\s*\w\.)', refs_text)
                
                # Clean up and process each reference
                for entry in ref_entries:
                    entry = entry.strip()
                    if entry:
                        # Attempt to parse author, year, title
                        ref_parts = self._parse_reference_parts(entry)
                        references_list.append(ref_parts)
                
                break  # Stop after finding the first valid references section
        
        # Add references to content
        if references_list:
            if 'metadata' not in content:
                content['metadata'] = {}
            
            content['metadata']['references'] = references_list
            
            # Create a references element
            refs_element = {
                'type': 'references',
                'entries': references_list,
                'position': refs_match.start() if refs_match else 0
            }
            
            if 'elements' not in content:
                content['elements'] = []
            
            # Check if we already have a references element
            has_refs = False
            for element in content['elements']:
                if element.get('type') == 'references':
                    has_refs = True
                    break
            
            if not has_refs:
                content['elements'].append(refs_element)
        
        return content
    
    def _parse_reference_parts(self, ref_text: str) -> Dict[str, str]:
        """Parse parts of a reference entry.
        
        Args:
            ref_text: Reference text to parse
            
        Returns:
            Dictionary with parsed reference parts
        """
        # This is a simplified implementation
        # A full implementation would need to handle various citation styles
        
        reference = {
            'text': ref_text.strip()
        }
        
        # Try to extract author
        author_match = re.search(r'^([^.]*?),', ref_text)
        if author_match:
            reference['author'] = author_match.group(1).strip()
        
        # Try to extract year
        year_match = re.search(r'\((\d{4})\)', ref_text)
        if year_match:
            reference['year'] = year_match.group(1)
        else:
            # Alternative year pattern
            alt_year_match = re.search(r'(?:,|\.)\s*(\d{4})\b', ref_text)
            if alt_year_match:
                reference['year'] = alt_year_match.group(1)
        
        # Try to extract title
        if 'author' in reference and 'year' in reference:
            # Look for title after author and year
            remaining_text = ref_text.split(reference['year'], 1)[-1].strip()
            if remaining_text:
                # Title is often the first segment until a period
                title_match = re.search(r'^\s*[.:,]?\s*(.*?)\.', remaining_text)
                if title_match:
                    reference['title'] = title_match.group(1).strip()
                else:
                    # If no period found, use the first line
                    lines = remaining_text.split('\n', 1)
                    reference['title'] = lines[0].strip()
        
        # Try to extract journal/publication
        if 'title' in reference:
            remaining_text = ref_text.split(reference['title'], 1)[-1].strip()
            if remaining_text:
                # Journal often follows the title after a period
                journal_match = re.search(r'^\s*\.\s*(.*?)(?:,|\d+\()', remaining_text)
                if journal_match:
                    reference['journal'] = journal_match.group(1).strip()
        
        return reference
"""
Technical document processor implementation.

This module implements a processor for technical documents like
manuals, documentation, and code-heavy content.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from pipeline.processors.base import DocumentProcessor


class TechnicalDocumentProcessor(DocumentProcessor):
    """Processor for technical documents.
    
    This processor specializes in handling technical content such as:
    - Technical manuals
    - API documentation
    - Code samples and tutorials
    - Technical specifications
    """
    
    def __init__(self):
        """Initialize a new technical document processor."""
        super().__init__()
    
    def process(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Process normalized content with technical document handling.
        
        Args:
            content: Normalized document content
            
        Returns:
            Processed document content
            
        Raises:
            ValueError: If content is not in the expected format
        """
        if not content or not isinstance(content, dict):
            raise ValueError("Invalid content format: expected a dictionary")
        
        # Extract code blocks
        content = self._extract_code_blocks(content)
        
        # Process command examples
        content = self._process_command_examples(content)
        
        # Extract API endpoints
        content = self._extract_api_endpoints(content)
        
        # Process technical diagrams
        content = self._process_diagrams(content)
        
        # Extract configuration examples
        content = self._extract_configuration_examples(content)
        
        return content
    
    def _extract_code_blocks(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and process code blocks from technical content.
        
        Args:
            content: Document content
            
        Returns:
            Content with processed code blocks
        """
        if 'text' not in content:
            return content
        
        # Look for code block patterns in text
        text = content['text']
        
        # Common code block formats: ```language code```, indented blocks, etc.
        code_patterns = [
            r'```(\w+)?\n(.*?)```',              # Markdown fenced code blocks
            r'<code.*?>(.*?)</code>',             # HTML code tags
            r'<pre.*?>(.*?)</pre>'                # HTML pre tags
        ]
        
        code_blocks = []
        
        for pattern in code_patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            for match in matches:
                # Extract language if available (from markdown blocks)
                language = None
                if match.lastindex == 2:  # Pattern with language group
                    language = match.group(1)
                    code_text = match.group(2)
                else:
                    code_text = match.group(1)
                
                # Try to detect language if not specified
                if not language:
                    language = self._detect_code_language(code_text)
                
                code_block = {
                    'type': 'code',
                    'text': code_text,
                    'language': language,
                    'position': match.start()
                }
                code_blocks.append(code_block)
        
        # Also look for indented code blocks (4+ spaces or tabs)
        indented_blocks = re.finditer(r'(?:^(?:[ ]{4,}|\t).*?$)+', text, re.MULTILINE)
        for match in indented_blocks:
            code_text = match.group(0)
            
            # Skip if already part of another code block
            skip = False
            for block in code_blocks:
                if match.start() >= block['position'] and match.end() <= block['position'] + len(block['text']):
                    skip = True
                    break
            
            if not skip:
                # Dedent the code block
                lines = code_text.split('\n')
                dedented_lines = []
                for line in lines:
                    dedented_lines.append(re.sub(r'^([ ]{4,}|\t)', '', line))
                
                code_text = '\n'.join(dedented_lines)
                language = self._detect_code_language(code_text)
                
                code_block = {
                    'type': 'code',
                    'text': code_text,
                    'language': language,
                    'position': match.start()
                }
                code_blocks.append(code_block)
        
        # Add code blocks to content
        if code_blocks:
            if 'elements' not in content:
                content['elements'] = []
            content['elements'].extend(code_blocks)
        
        return content
    
    def _detect_code_language(self, code_text: str) -> str:
        """Attempt to detect the programming language of a code block.
        
        Args:
            code_text: Code text to analyze
            
        Returns:
            Detected language or 'unknown'
        """
        # Simple heuristics for common languages
        if re.search(r'function\s+\w+\s*\([^)]*\)\s*{', code_text):
            return 'javascript'
        elif re.search(r'def\s+\w+\s*\([^)]*\):', code_text):
            return 'python'
        elif re.search(r'public\s+(?:static\s+)?(?:void|class|int|String)\s+\w+', code_text):
            return 'java'
        elif re.search(r'#include\s*<[^>]+>', code_text):
            return 'c'
        elif re.search(r'<?php', code_text):
            return 'php'
        elif re.search(r'<html.*?>|<div.*?>', code_text):
            return 'html'
        elif re.search(r'SELECT|INSERT|UPDATE|DELETE|CREATE|DROP', code_text, re.IGNORECASE):
            return 'sql'
        elif re.search(r'^\s*{[\s\n]*"', code_text) or re.search(r'^\s*\[[\s\n]*{', code_text):
            return 'json'
        elif re.search(r'^\s*<\?xml', code_text):
            return 'xml'
        elif re.search(r'import\s+(?:\w+\.)*\w+;', code_text):
            return 'java'
        elif re.search(r'func\s+\w+\s*\([^)]*\)\s*{', code_text):
            return 'go'
        elif re.search(r'(?:let|const|var)\s+\w+\s*=', code_text):
            return 'javascript'
        elif re.search(r'^\s*@[\w\.-]+:(?:\s*$|\s+[\w\.-]+:)', code_text, re.MULTILINE):
            return 'yaml'
        
        return 'unknown'
    
    def _process_command_examples(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Process command-line examples in technical content.
        
        Args:
            content: Document content
            
        Returns:
            Content with processed command examples
        """
        if 'text' not in content:
            return content
        
        # Look for command examples in text
        text = content['text']
        elements = content.get('elements', [])
        
        # Common patterns for command-line examples
        command_patterns = [
            r'(?:^|\n)(?:\$|>)\s+([^\n]+)',  # $ or > prefixed commands
            r'(?:^|\n)(?:bash|sh|shell|cmd)(?:[#]|:\s*|\$)\s+([^\n]+)'  # explicit shell commands
        ]
        
        commands = []
        
        for pattern in command_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                cmd_text = match.group(1).strip()
                command = {
                    'type': 'command',
                    'text': cmd_text,
                    'position': match.start()
                }
                
                # Try to categorize the command
                if re.search(r'^git\s+', cmd_text):
                    command['category'] = 'git'
                elif re.search(r'^docker\s+|^kubectl\s+', cmd_text):
                    command['category'] = 'container'
                elif re.search(r'^npm\s+|^yarn\s+', cmd_text):
                    command['category'] = 'package_manager'
                elif re.search(r'^python\s+|^pip\s+', cmd_text):
                    command['category'] = 'python'
                elif re.search(r'^curl\s+|^wget\s+', cmd_text):
                    command['category'] = 'http'
                elif re.search(r'^ssh\s+|^scp\s+', cmd_text):
                    command['category'] = 'remote_access'
                else:
                    command['category'] = 'shell'
                
                commands.append(command)
        
        # Add commands to content
        if commands:
            if 'elements' not in content:
                content['elements'] = []
            content['elements'].extend(commands)
        
        return content
    
    def _extract_api_endpoints(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract API endpoints from technical content.
        
        Args:
            content: Document content
            
        Returns:
            Content with extracted API endpoints
        """
        if 'text' not in content:
            return content
        
        # Look for API endpoint patterns in text
        text = content['text']
        
        # Common patterns for API endpoints
        api_patterns = [
            r'(?:GET|POST|PUT|DELETE|PATCH)\s+(/[a-zA-Z0-9_/{}.-]+)',  # HTTP method and path
            r'https?://[a-zA-Z0-9.-]+(?::[0-9]+)?(/[a-zA-Z0-9_/{}.-]+)',  # Full URL with path
            r'endpoint:\s*[\'"]?(/[a-zA-Z0-9_/{}.-]+)[\'"]?'  # Endpoint label
        ]
        
        endpoints = []
        
        for pattern in api_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                # If we matched a full URL, get just the path portion
                if match.lastindex is None:
                    endpoint_path = match.group(0)
                else:
                    endpoint_path = match.group(1)
                
                # Try to extract HTTP method if present
                method = None
                method_match = re.search(r'(GET|POST|PUT|DELETE|PATCH)', 
                                     text[max(0, match.start() - 10):match.start()], 
                                     re.IGNORECASE)
                if method_match:
                    method = method_match.group(1).upper()
                
                endpoint = {
                    'type': 'api_endpoint',
                    'path': endpoint_path,
                    'position': match.start()
                }
                
                if method:
                    endpoint['method'] = method
                
                endpoints.append(endpoint)
        
        # Add endpoints to content
        if endpoints:
            if 'elements' not in content:
                content['elements'] = []
            content['elements'].extend(endpoints)
        
        return content
    
    def _process_diagrams(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Process technical diagrams in content.
        
        Args:
            content: Document content
            
        Returns:
            Content with processed diagrams
        """
        if 'text' not in content:
            return content
        
        # Look for diagram patterns in text
        text = content['text']
        
        # Common patterns for diagrams
        diagram_patterns = [
            r'```mermaid\n(.*?)```',                # Mermaid diagrams
            r'```plantuml\n(.*?)```',               # PlantUML diagrams
            r'```diagram\n(.*?)```',                # Generic diagrams
            r'<div\s+class=[\'"]diagram[\'"]>(.*?)</div>'  # HTML diagram containers
        ]
        
        diagrams = []
        
        for pattern in diagram_patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            for match in matches:
                diagram_text = match.group(1)
                diagram_type = 'unknown'
                
                # Determine diagram type
                if 'mermaid' in pattern:
                    diagram_type = 'mermaid'
                elif 'plantuml' in pattern:
                    diagram_type = 'plantuml'
                else:
                    # Try to detect based on content
                    if re.search(r'sequenceDiagram|classDiagram|flowchart', diagram_text):
                        diagram_type = 'mermaid'
                    elif re.search(r'@startuml|@enduml', diagram_text):
                        diagram_type = 'plantuml'
                    elif re.search(r'graph\s+[A-Z]{2}\s*{', diagram_text):
                        diagram_type = 'graphviz'
                
                diagram = {
                    'type': 'diagram',
                    'text': diagram_text,
                    'diagram_type': diagram_type,
                    'position': match.start()
                }
                diagrams.append(diagram)
        
        # Add diagrams to content
        if diagrams:
            if 'elements' not in content:
                content['elements'] = []
            content['elements'].extend(diagrams)
        
        return content
    
    def _extract_configuration_examples(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract configuration examples from technical content.
        
        Args:
            content: Document content
            
        Returns:
            Content with extracted configuration examples
        """
        if 'elements' not in content:
            return content
        
        elements = content.get('elements', [])
        configs = []
        
        # Identify configuration files from code blocks
        for element in elements:
            if element.get('type') == 'code':
                code_text = element.get('text', '')
                language = element.get('language', 'unknown')
                
                # Check if this looks like a configuration file
                is_config = False
                
                if language in ['yaml', 'json', 'toml', 'ini', 'xml']:
                    is_config = True
                elif language == 'unknown':
                    # Try to detect if it's a config file by content patterns
                    if re.search(r'^\s*[a-zA-Z0-9_.-]+\s*[:=]', code_text, re.MULTILINE):
                        is_config = True
                    elif re.search(r'^\s*\[[a-zA-Z0-9_.-]+\]', code_text, re.MULTILINE):
                        is_config = True
                    elif re.search(r'^\s*<[a-zA-Z0-9_.-]+>\s*$', code_text, re.MULTILINE):
                        is_config = True
                
                if is_config:
                    config = {
                        'type': 'configuration',
                        'text': code_text,
                        'format': language if language != 'unknown' else self._detect_config_format(code_text),
                        'position': element.get('position', 0)
                    }
                    configs.append(config)
        
        # Add configurations to content
        if configs:
            if 'elements' not in content:
                content['elements'] = []
            content['elements'].extend(configs)
        
        return content
    
    def _detect_config_format(self, config_text: str) -> str:
        """Detect the format of a configuration file.
        
        Args:
            config_text: Configuration text to analyze
            
        Returns:
            Detected format type
        """
        # Check for YAML format
        if re.search(r'^\s*[a-zA-Z0-9_.-]+:\s*(?:$|[^:=])', config_text, re.MULTILINE):
            return 'yaml'
        
        # Check for JSON format
        if re.search(r'^\s*{\s*"[^"]+"\s*:', config_text):
            return 'json'
        
        # Check for INI/TOML format
        if re.search(r'^\s*\[[a-zA-Z0-9_.-]+\]\s*$', config_text, re.MULTILINE):
            return 'ini'
        
        # Check for XML format
        if re.search(r'^\s*<\?xml|^\s*<[a-zA-Z0-9_.-]+\s*>', config_text):
            return 'xml'
        
        # Check for .env format
        if re.search(r'^\s*[A-Z_]+=', config_text, re.MULTILINE):
            return 'env'
        
        return 'unknown'
"""
Configuration schema for the document processing pipeline.

This module defines the structure of the pipeline configuration and
provides validation functionality.
"""
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml


class ConfigValidationError(Exception):
    """Exception raised for configuration validation errors."""
    pass


class ConfigSchema:
    """Configuration schema definition and validation.
    
    This class defines the expected structure of the pipeline configuration
    and provides methods to validate configuration instances against the schema.
    """
    
    # Schema definition
    SCHEMA = {
        'input': {
            'type': 'dict',
            'required': True,
            'schema': {
                'recursive': {'type': 'bool', 'default': True},
                'supported_formats': {
                    'type': 'list',
                    'schema': {'type': 'string'},
                    'default': ['pdf', 'epub', 'markdown', 'txt']
                }
            }
        },
        'extraction': {
            'type': 'dict',
            'required': True,
            'schema': {
                'pdf': {
                    'type': 'dict',
                    'schema': {
                        'adobe_api': {
                            'type': 'dict',
                            'schema': {
                                'max_retries': {'type': 'int', 'default': 3},
                                'retry_delay': {'type': 'int', 'default': 5},
                                'page_limits': {
                                    'type': 'dict',
                                    'schema': {
                                        'scanned': {'type': 'int', 'default': 150},
                                        'native': {'type': 'int', 'default': 400}
                                    }
                                }
                            }
                        }
                    }
                },
                'epub': {
                    'type': 'dict',
                    'schema': {
                        'preserve_structure': {'type': 'bool', 'default': True}
                    }
                },
                'text': {
                    'type': 'dict',
                    'schema': {
                        'detect_headers': {'type': 'bool', 'default': True},
                        'parse_chapters': {'type': 'bool', 'default': True}
                    }
                }
            }
        },
        'content': {
            'type': 'dict',
            'required': True,
            'schema': {
                'remove_elements': {
                    'type': 'list',
                    'schema': {'type': 'string'},
                    'default': ['copyright', 'index', 'advertisements']
                },
                'footnotes': {
                    'type': 'dict',
                    'schema': {
                        'include': {'type': 'bool', 'default': True},
                        'position': {'type': 'string', 'default': 'end', 'allowed': ['end', 'inline']}
                    }
                }
            }
        },
        'output': {
            'type': 'dict',
            'required': True,
            'schema': {
                'formats': {
                    'type': 'list',
                    'schema': {'type': 'string'},
                    'default': ['markdown', 'text', 'semantic']
                },
                'directory': {'type': 'string', 'default': 'processed/'},
                'merge': {
                    'type': 'dict',
                    'schema': {
                        'strategy': {'type': 'string', 'default': 'semantic', 'allowed': ['semantic', 'single']},
                        'semantic_options': {
                            'type': 'dict',
                            'schema': {
                                'max_words_per_file': {'type': 'int', 'default': 500000},
                                'preserve_chapters': {'type': 'bool', 'default': True}
                            }
                        }
                    }
                }
            }
        },
        'endpoints': {
            'type': 'dict',
            'required': False,
            'schema': {
                'semantic_search': {
                    'type': 'dict',
                    'schema': {
                        'enabled': {'type': 'bool', 'default': False},
                        'chunking': {
                            'type': 'dict',
                            'schema': {
                                'strategy': {'type': 'string', 'default': 'semantic_overlap'},
                                'max_chunk_size': {'type': 'int', 'default': 2048},
                                'overlap_tokens': {'type': 'int', 'default': 200}
                            }
                        },
                        'content': {
                            'type': 'dict',
                            'schema': {
                                'preserve_headings': {'type': 'bool', 'default': True},
                                'include_metadata': {'type': 'bool', 'default': True}
                            }
                        },
                        'analysis': {
                            'type': 'dict',
                            'schema': {
                                'entities': {'type': 'bool', 'default': True},
                                'keywords': {'type': 'bool', 'default': True},
                                'concepts': {'type': 'bool', 'default': True}
                            }
                        },
                        'metadata': {
                            'type': 'dict',
                            'schema': {
                                'include_document_structure': {'type': 'bool', 'default': True},
                                'store_embeddings': {'type': 'bool', 'default': True},
                                'vector_model': {'type': 'string', 'default': 'default'}
                            }
                        }
                    }
                },
                'audiobook': {
                    'type': 'dict',
                    'schema': {
                        'enabled': {'type': 'bool', 'default': False},
                        'content': {
                            'type': 'dict',
                            'schema': {
                                'exclude': {
                                    'type': 'list',
                                    'schema': {'type': 'string'},
                                    'default': ['footnotes', 'tables', 'figures']
                                },
                                'include_chapter_markers': {'type': 'bool', 'default': True}
                            }
                        },
                        'text_normalization': {
                            'type': 'dict',
                            'schema': {
                                'abbreviation_expansion': {'type': 'bool', 'default': True},
                                'number_verbalization': {'type': 'bool', 'default': True},
                                'pronunciation_guidance': {'type': 'bool', 'default': True}
                            }
                        },
                        'chunking': {
                            'type': 'dict',
                            'schema': {
                                'strategy': {'type': 'string', 'default': 'chapter_based'},
                                'max_duration': {'type': 'string', 'default': '30m'}
                            }
                        },
                        'voice': {
                            'type': 'dict',
                            'schema': {
                                'default': {'type': 'string', 'default': 'neutral'},
                                'dialog_detection': {'type': 'bool', 'default': True}
                            }
                        }
                    }
                },
                'knowledge_base': {
                    'type': 'dict',
                    'schema': {
                        'enabled': {'type': 'bool', 'default': False},
                        'content': {
                            'type': 'dict',
                            'schema': {
                                'extract_facts': {'type': 'bool', 'default': True}
                            }
                        },
                        'analysis': {
                            'type': 'dict',
                            'schema': {
                                'topics': {'type': 'bool', 'default': True},
                                'relationships': {'type': 'bool', 'default': True},
                                'entities': {'type': 'bool', 'default': True}
                            }
                        },
                        'chunking': {
                            'type': 'dict',
                            'schema': {
                                'strategy': {'type': 'string', 'default': 'concept_based'},
                                'link_related_chunks': {'type': 'bool', 'default': True}
                            }
                        }
                    }
                }
            }
        },
        'operational': {
            'type': 'dict',
            'required': False,
            'schema': {
                'error_handling': {
                    'type': 'dict',
                    'schema': {
                        'max_retries': {'type': 'int', 'default': 3},
                        'retry_delay': {'type': 'int', 'default': 5},
                        'fallback_strategy': {'type': 'string', 'default': 'skip', 'allowed': ['skip', 'halt']},
                        'error_log': {'type': 'string', 'default': 'errors.log'}
                    }
                },
                'progress': {
                    'type': 'dict',
                    'schema': {
                        'display': {'type': 'string', 'default': 'rich', 'allowed': ['rich', 'simple']},
                        'metrics_file': {'type': 'string', 'default': 'metrics.json'},
                        'save_interval': {'type': 'int', 'default': 60}
                    }
                },
                'performance': {
                    'type': 'dict',
                    'schema': {
                        'cache': {
                            'type': 'dict',
                            'schema': {
                                'enabled': {'type': 'bool', 'default': True},
                                'memory': {
                                    'type': 'dict',
                                    'schema': {
                                        'enabled': {'type': 'bool', 'default': True},
                                        'max_size': {'type': 'string', 'default': '500MB'}
                                    }
                                },
                                'disk': {
                                    'type': 'dict',
                                    'schema': {
                                        'enabled': {'type': 'bool', 'default': True},
                                        'location': {'type': 'string', 'default': '.cache/'},
                                        'max_size': {'type': 'string', 'default': '10GB'}
                                    }
                                },
                                'content_addressable': {
                                    'type': 'dict',
                                    'schema': {
                                        'enabled': {'type': 'bool', 'default': True},
                                        'compression': {'type': 'bool', 'default': True}
                                    }
                                },
                                'differential': {
                                    'type': 'dict',
                                    'schema': {
                                        'enabled': {'type': 'bool', 'default': True},
                                        'compare_strategy': {'type': 'string', 'default': 'structure', 
                                                          'allowed': ['structure', 'content', 'metadata']}
                                    }
                                }
                            }
                        },
                        'parallel': {
                            'type': 'dict',
                            'schema': {
                                'max_workers': {'type': 'int', 'default': 4},
                                'chunk_size': {'type': 'int', 'default': 10}
                            }
                        }
                    }
                },
                'cli': {
                    'type': 'dict',
                    'schema': {
                        'progress_bar': {'type': 'bool', 'default': True},
                        'verbose': {'type': 'bool', 'default': False},
                        'batch_mode': {'type': 'bool', 'default': False}
                    }
                }
            }
        }
    }
    
    @staticmethod
    def validate(config: Dict[str, Any]) -> List[str]:
        """Validate a configuration against the schema.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            List of validation errors, empty if no errors
        """
        errors = []
        
        # Validate each section
        for section, section_schema in ConfigSchema.SCHEMA.items():
            if section_schema.get('required', False) and section not in config:
                errors.append(f"Required section '{section}' is missing")
                continue
            
            if section in config:
                section_errors = ConfigSchema._validate_section(
                    config[section], 
                    section_schema.get('schema', {}), 
                    section
                )
                errors.extend(section_errors)
        
        return errors
    
    @staticmethod
    def _validate_section(config: Dict[str, Any], schema: Dict[str, Any], path: str) -> List[str]:
        """Validate a configuration section against its schema.
        
        Args:
            config: Configuration section to validate
            schema: Schema for the section
            path: Path to the section for error reporting
            
        Returns:
            List of validation errors, empty if no errors
        """
        errors = []
        
        # Check section type
        if schema.get('type') == 'dict' and not isinstance(config, dict):
            errors.append(f"Section '{path}' should be a dictionary")
            return errors
        
        if schema.get('type') == 'list' and not isinstance(config, list):
            errors.append(f"Section '{path}' should be a list")
            return errors
        
        # For dictionary types, check each field
        if schema.get('type') == 'dict':
            for field, field_schema in schema.get('schema', {}).items():
                field_path = f"{path}.{field}"
                
                if field in config:
                    # Check field type
                    if field_schema.get('type') == 'dict':
                        field_errors = ConfigSchema._validate_section(
                            config[field], 
                            field_schema, 
                            field_path
                        )
                        errors.extend(field_errors)
                    elif field_schema.get('type') == 'list':
                        if not isinstance(config[field], list):
                            errors.append(f"Field '{field_path}' should be a list")
                        else:
                            # Check list item schema if provided
                            item_schema = field_schema.get('schema')
                            if item_schema:
                                for i, item in enumerate(config[field]):
                                    item_path = f"{field_path}[{i}]"
                                    item_errors = ConfigSchema._validate_value(
                                        item, 
                                        item_schema, 
                                        item_path
                                    )
                                    errors.extend(item_errors)
                    else:
                        # Simple value type
                        value_errors = ConfigSchema._validate_value(
                            config[field], 
                            field_schema, 
                            field_path
                        )
                        errors.extend(value_errors)
        
        return errors
    
    @staticmethod
    def _validate_value(value: Any, schema: Dict[str, Any], path: str) -> List[str]:
        """Validate a configuration value against its schema.
        
        Args:
            value: Configuration value to validate
            schema: Schema for the value
            path: Path to the value for error reporting
            
        Returns:
            List of validation errors, empty if no errors
        """
        errors = []
        
        # Check value type
        value_type = schema.get('type')
        if value_type == 'bool' and not isinstance(value, bool):
            errors.append(f"Value '{path}' should be a boolean")
        elif value_type == 'int' and not isinstance(value, int):
            errors.append(f"Value '{path}' should be an integer")
        elif value_type == 'float' and not isinstance(value, (int, float)):
            errors.append(f"Value '{path}' should be a number")
        elif value_type == 'string' and not isinstance(value, str):
            errors.append(f"Value '{path}' should be a string")
        
        # Check allowed values
        if 'allowed' in schema and value not in schema['allowed']:
            allowed = ', '.join(str(a) for a in schema['allowed'])
            errors.append(f"Value '{path}' should be one of: {allowed}")
        
        # Check dictionary schema
        if value_type == 'dict' and isinstance(value, dict):
            if 'schema' in schema:
                dict_errors = ConfigSchema._validate_section(
                    value, 
                    schema['schema'], 
                    path
                )
                errors.extend(dict_errors)
        
        return errors
    
    @staticmethod
    def merge_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge default values into a configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Configuration with default values filled in
        """
        result = {}
        
        # Process each section in the schema
        for section, section_schema in ConfigSchema.SCHEMA.items():
            if section not in config and 'default' in section_schema:
                result[section] = section_schema['default']
                continue
                
            if section in config:
                # Copy existing section
                result[section] = ConfigSchema._merge_section_defaults(
                    config[section], 
                    section_schema.get('schema', {})
                )
            elif section_schema.get('required', False):
                # Create a section with defaults for required sections
                result[section] = ConfigSchema._create_default_section(
                    section_schema.get('schema', {})
                )
        
        return result
    
    @staticmethod
    def _merge_section_defaults(config: Union[Dict[str, Any], List[Any]], schema: Dict[str, Any]) -> Union[Dict[str, Any], List[Any]]:
        """Merge default values into a configuration section.
        
        Args:
            config: Configuration section
            schema: Schema for the section
            
        Returns:
            Configuration section with default values filled in
        """
        if schema.get('type') == 'dict' and isinstance(config, dict):
            result = {}
            
            # Process each field in the schema
            for field, field_schema in schema.get('schema', {}).items():
                if field not in config and 'default' in field_schema:
                    result[field] = field_schema['default']
                elif field in config:
                    if field_schema.get('type') in ['dict', 'list']:
                        result[field] = ConfigSchema._merge_section_defaults(
                            config[field], 
                            field_schema
                        )
                    else:
                        result[field] = config[field]
                elif field_schema.get('required', False):
                    if field_schema.get('type') in ['dict', 'list']:
                        result[field] = ConfigSchema._create_default_section(
                            field_schema.get('schema', {})
                        )
                    elif 'default' in field_schema:
                        result[field] = field_schema['default']
            
            # Copy any extra fields not in the schema
            for field in config:
                if field not in schema.get('schema', {}):
                    result[field] = config[field]
            
            return result
        elif schema.get('type') == 'list' and isinstance(config, list):
            # For lists, just return the list as is
            return config
        else:
            # For simple types, just return the value
            return config
    
    @staticmethod
    def _create_default_section(schema: Dict[str, Any]) -> Union[Dict[str, Any], List[Any]]:
        """Create a section with default values from a schema.
        
        Args:
            schema: Schema for the section
            
        Returns:
            Section with default values
        """
        if schema.get('type') == 'dict':
            result = {}
            
            for field, field_schema in schema.get('schema', {}).items():
                if 'default' in field_schema:
                    result[field] = field_schema['default']
                elif field_schema.get('required', False):
                    if field_schema.get('type') in ['dict', 'list']:
                        result[field] = ConfigSchema._create_default_section(
                            field_schema.get('schema', {})
                        )
            
            return result
        elif schema.get('type') == 'list':
            # For lists, return an empty list or the default if specified
            return schema.get('default', [])
        else:
            # For simple types, return the default or None
            return schema.get('default')


class ConfigLoader:
    """Configuration loader for the document processing pipeline.
    
    This class is responsible for loading configuration from YAML files,
    applying environment variable overrides, and validating the configuration.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize a new configuration loader.
        
        Args:
            config_path: Path to the configuration file (YAML)
                         If None, looks for 'config.yaml' in the current directory
        """
        self._config_path = config_path or 'config.yaml'
        self._config = {}
    
    def load(self) -> Dict[str, Any]:
        """Load and process configuration.
        
        Returns:
            Processed configuration dictionary
            
        Raises:
            FileNotFoundError: If the configuration file is not found
            yaml.YAMLError: If the configuration file is not valid YAML
            ConfigValidationError: If the configuration is not valid
        """
        # Load configuration from file
        self._load_from_file()
        
        # Apply environment variable overrides
        self._apply_env_overrides()
        
        # Merge defaults
        self._config = ConfigSchema.merge_defaults(self._config)
        
        # Validate configuration
        errors = ConfigSchema.validate(self._config)
        if errors:
            raise ConfigValidationError(
                f"Configuration validation failed:\n" +
                "\n".join(f"- {error}" for error in errors)
            )
        
        return self._config
    
    def _load_from_file(self) -> None:
        """Load configuration from the YAML file.
        
        Raises:
            FileNotFoundError: If the configuration file is not found
            yaml.YAMLError: If the configuration file is not valid YAML
        """
        if not os.path.exists(self._config_path):
            raise FileNotFoundError(f"Configuration file not found: {self._config_path}")
        
        with open(self._config_path, 'r') as f:
            self._config = yaml.safe_load(f) or {}
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to the configuration."""
        # Look for environment variables with the PIPELINE_ prefix
        for key, value in os.environ.items():
            if key.startswith('PIPELINE_'):
                # Convert environment variable name to configuration path
                # e.g., PIPELINE_OUTPUT_DIRECTORY -> output.directory
                config_path = key[9:].lower().replace('_', '.')
                
                # Apply override
                self._set_config_value(config_path, value)
    
    def _set_config_value(self, path: str, value: str) -> None:
        """Set a configuration value by path.
        
        Args:
            path: Configuration path (dot-separated)
            value: String value to set (will be converted to appropriate type)
        """
        parts = path.split('.')
        
        # Navigate to the correct section
        config = self._config
        for i, part in enumerate(parts[:-1]):
            if part not in config:
                config[part] = {}
            config = config[part]
        
        # Set the value with appropriate type conversion
        last_part = parts[-1]
        
        # Convert value to appropriate type
        if value.lower() in ['true', 'yes', 'on']:
            config[last_part] = True
        elif value.lower() in ['false', 'no', 'off']:
            config[last_part] = False
        elif value.isdigit():
            config[last_part] = int(value)
        elif re.match(r'^-?\d+(\.\d+)?$', value):
            config[last_part] = float(value)
        elif value.startswith('[') and value.endswith(']'):
            # Simple list parsing
            items = value[1:-1].split(',')
            config[last_part] = [item.strip() for item in items if item.strip()]
        else:
            config[last_part] = value
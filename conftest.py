"""
Configure pytest environment.

This file adds the project root directory to the Python path,
allowing the pipeline package to be imported during testing.
"""
import os
import sys
from pathlib import Path

# Add the project root directory to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
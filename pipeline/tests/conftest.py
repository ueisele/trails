"""Test configuration for pipeline tests."""

import sys
from pathlib import Path

# Add src directory to Python path
pipeline_root = Path(__file__).parent.parent
src_dir = pipeline_root / "src"
sys.path.insert(0, str(src_dir))

"""
Pytest configuration and fixtures for CLIS tests.
"""

import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def temp_file():
    """Create a temporary file for tests."""
    fd, path = tempfile.mkstemp(suffix='.txt')
    yield Path(path)
    try:
        Path(path).unlink()
    except:
        pass


@pytest.fixture
def sample_python_file(temp_dir):
    """Create a sample Python file."""
    file_path = temp_dir / "sample.py"
    content = """def hello():
    print("Hello")

def world():
    print("World")

class TestClass:
    def method(self):
        pass
"""
    file_path.write_text(content)
    return file_path

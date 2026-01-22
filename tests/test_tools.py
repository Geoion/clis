"""
Unit tests for CLIS tools.
"""

import pytest
from pathlib import Path
import tempfile
import os

from clis.tools.filesystem.edit_file import EditFileTool
from clis.tools.filesystem.insert_code import InsertCodeTool
from clis.tools.filesystem.delete_lines import DeleteLinesTool
from clis.tools.filesystem.search_replace import SearchReplaceTool
from clis.tools.filesystem.grep import GrepTool


class TestEditFileTool:
    """Tests for edit_file tool."""
    
    def test_edit_file_basic(self):
        """Test basic file editing."""
        tool = EditFileTool()
        
        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Hello World\nFoo Bar\n")
            temp_path = f.name
        
        try:
            # Edit file
            result = tool.execute(
                path=temp_path,
                old_content="Foo Bar",
                new_content="Baz Qux",
                dry_run=False
            )
            
            assert result.success
            assert "edited successfully" in result.output
            
            # Verify content
            with open(temp_path, 'r') as f:
                content = f.read()
            assert "Baz Qux" in content
            assert "Foo Bar" not in content
        
        finally:
            os.unlink(temp_path)
    
    def test_edit_file_dry_run(self):
        """Test dry_run mode doesn't modify file."""
        tool = EditFileTool()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Hello World\n")
            temp_path = f.name
        
        try:
            result = tool.execute(
                path=temp_path,
                old_content="Hello",
                new_content="Hi",
                dry_run=True
            )
            
            assert result.success
            assert "DRY RUN" in result.output
            
            # Verify file unchanged
            with open(temp_path, 'r') as f:
                content = f.read()
            assert "Hello" in content
            assert "Hi" not in content
        
        finally:
            os.unlink(temp_path)
    
    def test_edit_file_not_unique(self):
        """Test error when old_content is not unique."""
        tool = EditFileTool()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Hello\nHello\n")
            temp_path = f.name
        
        try:
            result = tool.execute(
                path=temp_path,
                old_content="Hello",
                new_content="Hi",
                dry_run=False
            )
            
            assert not result.success
            assert "must be unique" in result.error
        
        finally:
            os.unlink(temp_path)


class TestInsertCodeTool:
    """Tests for insert_code tool."""
    
    def test_insert_code_basic(self):
        """Test basic code insertion."""
        tool = InsertCodeTool()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("def hello():\n    pass\n")
            temp_path = f.name
        
        try:
            result = tool.execute(
                path=temp_path,
                line_number=2,
                code="    print('test')",
                auto_indent=False,
                dry_run=False
            )
            
            assert result.success
            assert "inserted successfully" in result.output
            
            # Verify content
            with open(temp_path, 'r') as f:
                lines = f.readlines()
            assert len(lines) == 3
            assert "print('test')" in lines[1]
        
        finally:
            os.unlink(temp_path)
    
    def test_insert_code_at_end(self):
        """Test inserting at end of file."""
        tool = InsertCodeTool()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("line1\nline2\n")
            temp_path = f.name
        
        try:
            result = tool.execute(
                path=temp_path,
                line_number=-1,  # End of file
                code="line3",
                dry_run=False
            )
            
            assert result.success
            
            with open(temp_path, 'r') as f:
                lines = f.readlines()
            assert len(lines) == 3
        
        finally:
            os.unlink(temp_path)


class TestDeleteLinesTool:
    """Tests for delete_lines tool."""
    
    def test_delete_single_line(self):
        """Test deleting a single line."""
        tool = DeleteLinesTool()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("line1\nline2\nline3\n")
            temp_path = f.name
        
        try:
            result = tool.execute(
                path=temp_path,
                start_line=2,
                end_line=2,
                dry_run=False
            )
            
            assert result.success
            
            with open(temp_path, 'r') as f:
                lines = f.readlines()
            assert len(lines) == 2
            assert "line2" not in ''.join(lines)
        
        finally:
            os.unlink(temp_path)
    
    def test_delete_range(self):
        """Test deleting a range of lines."""
        tool = DeleteLinesTool()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("line1\nline2\nline3\nline4\n")
            temp_path = f.name
        
        try:
            result = tool.execute(
                path=temp_path,
                start_line=2,
                end_line=3,
                dry_run=False
            )
            
            assert result.success
            
            with open(temp_path, 'r') as f:
                content = f.read()
            assert "line1" in content
            assert "line4" in content
            assert "line2" not in content
            assert "line3" not in content
        
        finally:
            os.unlink(temp_path)


class TestGrepTool:
    """Tests for grep tool."""
    
    def test_grep_literal(self):
        """Test literal pattern search."""
        tool = GrepTool()
        
        # Create test directory
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def hello():\n    print('Hello')\n")
            
            result = tool.execute(
                pattern="hello",
                path=tmpdir,
                regex=False,
                ignore_case=False
            )
            
            assert result.success
            assert "hello" in result.output.lower()
    
    def test_grep_regex(self):
        """Test regex pattern search."""
        tool = GrepTool()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("def func1():\n    pass\ndef func2():\n    pass\n")
            
            result = tool.execute(
                pattern=r"def func\d+",
                path=tmpdir,
                regex=True
            )
            
            assert result.success
            # Should find both functions
            assert "func1" in result.output or "func2" in result.output


class TestSearchReplaceTool:
    """Tests for search_replace tool."""
    
    def test_search_replace_dry_run(self):
        """Test dry_run mode doesn't modify files."""
        tool = SearchReplaceTool()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("old text\n")
            
            result = tool.execute(
                pattern="old",
                replacement="new",
                path=str(test_file),
                dry_run=True
            )
            
            assert result.success
            assert "DRY RUN" in result.output
            
            # File should be unchanged
            assert test_file.read_text() == "old text\n"
    
    def test_search_replace_actual(self):
        """Test actual replacement."""
        tool = SearchReplaceTool()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("foo bar baz\n")
            
            result = tool.execute(
                pattern="bar",
                replacement="qux",
                path=str(test_file),
                dry_run=False
            )
            
            assert result.success
            assert test_file.read_text() == "foo qux baz\n"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Tests for Code Graph Analyzer.

Validates AST parsing, function/class extraction, and call graph analysis.
"""

import asyncio
from pathlib import Path

import pytest

from mcp_common.code_graph import (
    ClassNode,
    CodeGraphAnalyzer,
    FileNode,
    FunctionNode,
)


@pytest.mark.asyncio
async def test_analyze_simple_repository(tmp_path: Path) -> None:
    """Test analyzing a simple Python repository."""
    # Create test files
    (tmp_path / "main.py").write_text(
        """
def hello():
    '''Say hello.'''
    print('Hello, world!')

class Greeter:
    '''Greets people.'''
    def greet(self, name: str) -> None:
        self.hello()
        print(f'Hello, {name}!')
"""
    )

    (tmp_path / "utils.py").write_text(
        """
def add(a: int, b: int) -> int:
    '''Add two numbers.'''
    return a + b
"""
    )

    # Analyze
    analyzer = CodeGraphAnalyzer(tmp_path)
    stats = await analyzer.analyze_repository(str(tmp_path))

    # Verify stats
    assert stats["files_indexed"] == 2
    assert stats["functions_indexed"] >= 2  # hello, add (greet is a method, counted separately)
    assert stats["classes_indexed"] == 1  # Greeter
    assert stats["duration_ms"] > 0

    # Verify nodes exist
    assert "main.py" in analyzer.nodes
    assert "utils.py" in analyzer.nodes

    # Verify functions
    hello_func = None
    for node in analyzer.nodes.values():
        if node.name == "hello" and node.node_type == "function":
            hello_func = node
            break

    assert hello_func is not None
    assert isinstance(hello_func, FunctionNode)
    assert hello_func.is_export is True


@pytest.mark.asyncio
async def test_function_context(tmp_path: Path) -> None:
    """Test getting function context including callers and callees."""
    # Create test files with call relationships
    (tmp_path / "caller.py").write_text(
        """
def callee():
    '''Called function.'''
    pass

def caller():
    '''Calling function.'''
    callee()
"""
    )

    # Analyze
    analyzer = CodeGraphAnalyzer(tmp_path)
    await analyzer.analyze_repository(str(tmp_path))

    # Get context for caller
    context = await analyzer.get_function_context("caller")

    assert context["function"]["name"] == "caller"
    assert len(context["callees"]) >= 1
    assert any(c["name"] == "callee" for c in context["callees"])

    # Get context for callee
    callee_context = await analyzer.get_function_context("callee", include_callers=True)
    assert len(callee_context["callers"]) >= 1
    assert any(c["name"] == "caller" for c in callee_context["callers"])


@pytest.mark.asyncio
async def test_related_files(tmp_path: Path) -> None:
    """Test finding related files based on imports."""
    # Create test files with imports
    (tmp_path / "main.py").write_text(
        """
from utils import helper

def main():
    helper()
"""
    )

    (tmp_path / "utils.py").write_text(
        """
def helper():
    '''Helper function.'''
    pass
"""
    )

    # Analyze
    analyzer = CodeGraphAnalyzer(tmp_path)
    await analyzer.analyze_repository(str(tmp_path))

    # Find files related to main.py
    related = await analyzer.find_related_files("main.py", relationship_type="all")

    # Should find utils.py as related
    assert len(related) > 0
    assert any("utils.py" in rf["file_path"] for rf in related)


@pytest.mark.asyncio
async def test_class_extraction(tmp_path: Path) -> None:
    """Test extracting class information."""
    (tmp_path / "models.py").write_text(
        """
class BaseModel:
    '''Base model class.'''
    def save(self):
        '''Save the model.'''
        pass

class User(BaseModel):
    '''User model.'''
    def __init__(self, name: str):
        self.name = name
"""
    )

    # Analyze
    analyzer = CodeGraphAnalyzer(tmp_path)
    stats = await analyzer.analyze_repository(str(tmp_path))

    # Verify classes extracted
    assert stats["classes_indexed"] == 2

    # Check BaseModel
    base_model = None
    for node in analyzer.nodes.values():
        if node.name == "BaseModel" and node.node_type == "class":
            base_model = node
            break

    assert base_model is not None
    assert isinstance(base_model, ClassNode)
    assert base_model.docstring == "Base model class."

    # Check User inherits from BaseModel
    user_class = None
    for node in analyzer.nodes.values():
        if node.name == "User" and node.node_type == "class":
            user_class = node
            break

    assert user_class is not None
    assert "BaseModel" in user_class.base_classes


@pytest.mark.asyncio
async def test_skip_test_files(tmp_path: Path) -> None:
    """Test that test files are skipped when include_tests=False."""
    # Create files - some with "test" in name/path
    (tmp_path / "main.py").write_text("def main(): pass")
    (tmp_path / "utils.py").write_text("def helper(): pass")
    (tmp_path / "test_main.py").write_text("def test_main(): pass")
    (tmp_path / "test_utils.py").write_text("def test_utils(): pass")

    # Analyze without tests
    analyzer = CodeGraphAnalyzer(tmp_path)
    stats = await analyzer.analyze_repository(str(tmp_path), include_tests=False)

    # Should only index non-test files
    assert stats["files_indexed"] == 2  # main.py and utils.py only

    # Verify test files were excluded
    file_names = [node.name for node in analyzer.nodes.values() if node.node_type == "file"]
    assert "test_main.py" not in file_names
    assert "test_utils.py" not in file_names
    assert "main.py" in file_names
    assert "utils.py" in file_names

    # Analyze with tests - should get all files
    analyzer2 = CodeGraphAnalyzer(tmp_path)
    stats2 = await analyzer2.analyze_repository(str(tmp_path), include_tests=True)

    # Should index all files
    assert stats2["files_indexed"] == 4


@pytest.mark.asyncio
async def test_function_complexity(tmp_path: Path) -> None:
    """Test cyclomatic complexity calculation."""
    (tmp_path / "complex.py").write_text(
        """
def simple():
    '''Simple function.'''
    pass

def complex_func(x):
    '''Complex function with many branches.'''
    if x > 0:
        if x > 10:
            return 1
        else:
            return 2
    else:
        return 0
"""
    )

    # Analyze
    analyzer = CodeGraphAnalyzer(tmp_path)
    await analyzer.analyze_repository(str(tmp_path))

    # Find complex_func
    func = None
    for node in analyzer.nodes.values():
        if node.name == "complex_func" and node.node_type == "function":
            func = node
            break

    assert func is not None
    assert func.complexity > 1  # Should have higher complexity


@pytest.mark.asyncio
async def test_private_functions_not_exported(tmp_path: Path) -> None:
    """Test that private functions (starting with _) are marked as not exported."""
    (tmp_path / "module.py").write_text(
        """
def public_function():
    '''Public function.'''
    pass

def _private_function():
    '''Private function.'''
    pass
"""
    )

    # Analyze
    analyzer = CodeGraphAnalyzer(tmp_path)
    await analyzer.analyze_repository(str(tmp_path))

    # Check public_function
    public = None
    private = None
    for node in analyzer.nodes.values():
        if node.node_type == "function":
            if node.name == "public_function":
                public = node
            elif node.name == "_private_function":
                private = node

    assert public is not None
    assert public.is_export is True

    assert private is not None
    assert private.is_export is False


def test_analyzer_initialization() -> None:
    """Test analyzer initialization with path."""
    analyzer = CodeGraphAnalyzer("/tmp")
    assert analyzer.project_path == Path("/tmp")
    assert len(analyzer.nodes) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

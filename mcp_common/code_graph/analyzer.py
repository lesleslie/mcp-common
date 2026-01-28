"""
Code Graph Analyzer - Shared infrastructure for Session Buddy and Mahavishnu.

Analyzes codebase structure to extract functions, classes, imports, and call graphs.
Used for context compaction, RAG enhancement, and workflow intelligence.

Version: 0.4.0
"""

from __future__ import annotations

import ast
import operator
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CodeNode:
    """Base class for code nodes in the graph."""

    id: str
    name: str
    file_id: str
    node_type: str  # "file", "function", "class", "import"


@dataclass
class FunctionNode(CodeNode):
    """Represents a function or method in the codebase."""

    is_export: bool
    start_line: int
    end_line: int
    calls: list[str] = field(default_factory=list)
    docstring: str | None = None
    complexity: int = 1  # Cyclomatic complexity


@dataclass
class ClassNode(CodeNode):
    """Represents a class in the codebase."""

    start_line: int
    end_line: int
    methods: list[str] = field(default_factory=list)
    base_classes: list[str] = field(default_factory=list)
    docstring: str | None = None


@dataclass
class ImportNode(CodeNode):
    """Represents an import statement."""

    module: str
    alias: str | None = None
    is_from_import: bool = False
    imported_names: list[str] = field(default_factory=list)


@dataclass
class FileNode(CodeNode):
    """Represents a source file in the codebase."""

    path: str
    language: str
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


class CodeGraphAnalyzer:
    """
    Analyze and index codebase structure.

    Extracts functions, classes, imports, and builds a call graph.
    Supports Python initially, with planned support for JS/TS.

    Example:
        ```python
        analyzer = CodeGraphAnalyzer(Path("/path/to/repo"))
        stats = await analyzer.analyze_repository("/path/to/repo")

        # Get function context
        context = await analyzer.get_function_context("my_function")

        # Find related files
        related = await analyzer.find_related_files("src/main.py", "imports")
        ```
    """

    def __init__(self, project_path: Path | str):
        """Initialize the analyzer with a project path.

        Args:
            project_path: Path to the project directory to analyze
        """
        self.project_path = Path(project_path)
        self.nodes: dict[str, CodeNode] = {}
        self._call_graph: dict[str, set[str]] = defaultdict(set)
        self._import_graph: dict[str, set[str]] = defaultdict(set)
        self._file_nodes: dict[str, FileNode] = {}

    async def analyze_repository(
        self,
        repo_path: str,
        languages: list[str] | None = None,
        include_tests: bool = False,
    ) -> dict[str, Any]:
        """
        Analyze a repository and build the code graph.

        Args:
            repo_path: Path to the repository
            languages: Languages to index (default: ["python"])
            include_tests: Whether to include test files

        Returns:
            Statistics about the indexed code:
            {
                "files_indexed": int,
                "functions_indexed": int,
                "classes_indexed": int,
                "calls_indexed": int,
                "imports_indexed": int,
                "duration_ms": int
            }
        """
        start_time = time.time()
        repo = Path(repo_path)

        if not repo.exists():
            raise FileNotFoundError(f"Repository not found: {repo_path}")

        languages = languages or ["python"]
        stats = {
            "files_indexed": 0,
            "functions_indexed": 0,
            "classes_indexed": 0,
            "calls_indexed": 0,
            "imports_indexed": 0,
            "duration_ms": 0,
        }

        # Process each language
        for language in languages:
            await self._process_language(repo, language, include_tests, stats)

        # Count totals
        self._count_totals(stats)

        stats["duration_ms"] = int((time.time() - start_time) * 1000)

        return stats

    async def _process_language(
        self, repo: Path, language: str, include_tests: bool, stats: dict[str, int]
    ) -> None:
        """Process files for a specific programming language."""
        file_pattern = self._get_file_pattern(language)
        if not file_pattern:
            return

        # Find all source files
        for file_path in repo.rglob(file_pattern):
            if not include_tests and self._should_skip_test_file(file_path):
                continue

            if self._should_skip_non_source_dir(file_path):
                continue

            # Analyze the file
            if language == "python":
                await self._analyze_python_file(file_path)

            stats["files_indexed"] += 1

    def _get_file_pattern(self, language: str) -> str | None:
        """Get file pattern for a specific language."""
        if language == "python":
            return "*.py"
        if language in ("javascript", "typescript"):
            return "*.js" if language == "javascript" else "*.ts"
        return None

    def _should_skip_test_file(self, file_path: Path) -> bool:
        """Check if a test file should be skipped."""
        # Skip if "test" is in directory path
        if "test" in file_path.parts:
            return True
        # Skip if filename starts with "test_"
        if file_path.name.startswith("test_"):
            return True
        # Skip if filename is "test_*.py"
        if file_path.stem.startswith("test_"):
            return True
        return False

    def _should_skip_non_source_dir(self, file_path: Path) -> bool:
        """Check if file is in a non-source directory that should be skipped."""
        non_source_dirs = {"__pycache__", ".venv", "venv", "node_modules"}
        return any(part in file_path.parts for part in non_source_dirs)

    def _count_totals(self, stats: dict[str, int]) -> None:
        """Count total functions, classes, and imports."""
        for node in self.nodes.values():
            if node.node_type == "function":
                stats["functions_indexed"] += 1
            elif node.node_type == "class":
                stats["classes_indexed"] += 1
            elif node.node_type == "import":
                stats["imports_indexed"] += 1

        # Count calls
        for callees in self._call_graph.values():
            stats["calls_indexed"] += len(callees)

    async def _analyze_python_file(self, file_path: Path) -> None:
        """Analyze a Python source file and extract code structure.

        Args:
            file_path: Path to the Python file
        """
        source = await self._read_file_content(file_path)
        if source is None:
            return

        tree = await self._parse_ast(source, file_path)
        if tree is None:
            return

        # Create file node
        file_id = str(file_path.relative_to(self.project_path))
        file_node = self._create_file_node(file_path, file_id)
        self.nodes[file_id] = file_node
        self._file_nodes[file_id] = file_node

        # Process imports and definitions
        await self._process_file_content(tree, file_node, file_id)

    async def _read_file_content(self, file_path: Path) -> str | None:
        """Read file content, returning None if there's an error."""
        try:
            return file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    async def _parse_ast(self, source: str, file_path: Path) -> ast.AST | None:
        """Parse AST from source, returning None if there's a syntax error."""
        try:
            return ast.parse(source, filename=str(file_path))
        except SyntaxError:
            return None

    def _create_file_node(self, file_path: Path, file_id: str) -> FileNode:
        """Create a file node for the given file."""
        return FileNode(
            id=file_id,
            name=file_path.name,
            file_id=file_id,
            node_type="file",
            path=str(file_path),
            language="python",
        )

    async def _process_file_content(
        self, tree: ast.AST, file_node: FileNode, file_id: str
    ) -> None:
        """Process the AST tree to extract imports, classes, and functions."""
        self._extract_and_add_imports(tree, file_node, file_id)
        self._extract_and_add_definitions(tree, file_node, file_id)

    def _extract_and_add_imports(
        self, tree: ast.AST, file_node: FileNode, file_id: str
    ) -> None:
        """Extract imports from the AST and add them to the file node."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_node = self._extract_import(node, file_id)
                if import_node:
                    self.nodes[import_node.id] = import_node
                    file_node.imports.append(import_node.id)

    def _extract_and_add_definitions(
        self, tree: ast.AST, file_node: FileNode, file_id: str
    ) -> None:
        """Extract classes and functions from the AST and add them to the file node."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_node = self._extract_class(node, file_id, Path(file_node.path))
                if class_node:
                    self.nodes[class_node.id] = class_node
                    file_node.classes.append(class_node.id)

            elif isinstance(node, ast.FunctionDef):
                # Skip methods (they're part of classes)
                if not self._is_method(node, tree):
                    func_node = self._extract_function(
                        node, file_id, Path(file_node.path)
                    )
                    if func_node:
                        self.nodes[func_node.id] = func_node
                        file_node.functions.append(func_node.id)

    def _is_method(self, func_node: ast.FunctionDef, tree: ast.AST) -> bool:
        """Check if a function is a method (defined inside a class)."""
        for parent in ast.walk(tree):
            if isinstance(parent, ast.ClassDef):
                for child in parent.body:
                    if child is func_node:
                        return True
        return False

    def _extract_import(
        self, node: ast.Import | ast.ImportFrom, file_id: str
    ) -> ImportNode | None:
        """Extract import information from an AST import node."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                import_id = f"{file_id}:import:{alias.name}"
                return ImportNode(
                    id=import_id,
                    name=alias.name,
                    file_id=file_id,
                    node_type="import",
                    module=alias.name,
                    alias=alias.asname,
                    is_from_import=False,
                )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                import_id = f"{file_id}:from:{module}:{alias.name}"
                return ImportNode(
                    id=import_id,
                    name=alias.name,
                    file_id=file_id,
                    node_type="import",
                    module=module,
                    alias=alias.asname,
                    is_from_import=True,
                    imported_names=[alias.name],
                )
        return None

    def _extract_class(
        self, node: ast.ClassDef, file_id: str, file_path: Path
    ) -> ClassNode | None:
        """Extract class information from an AST ClassDef node."""
        class_id = f"{file_id}:class:{node.name}"

        # Get base classes
        base_classes = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_classes.append(base.id)
            elif isinstance(base, ast.Attribute):
                base_classes.append(ast.unparse(base))

        # Get docstring
        docstring = ast.get_docstring(node)

        # Calculate span
        start_line = node.lineno
        end_line = (
            node.end_lineno
            if hasattr(node, "end_lineno") and node.end_lineno is not None
            else start_line
        )

        return ClassNode(
            id=class_id,
            name=node.name,
            file_id=file_id,
            node_type="class",
            start_line=start_line,
            end_line=end_line,
            base_classes=base_classes,
            docstring=docstring,
        )

    def _extract_function(
        self, node: ast.FunctionDef, file_id: str, file_path: Path
    ) -> FunctionNode | None:
        """Extract function information from an AST FunctionDef node."""
        func_id = f"{file_id}:function:{node.name}"

        # Check if it's exported (not starting with _)
        is_export = not node.name.startswith("_")

        # Get docstring
        docstring = ast.get_docstring(node)

        # Calculate complexity (simplified - count branches)
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.Try)):
                complexity += 1

        # Extract function calls
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = self._extract_call_name(child)
                if call_name:
                    calls.append(call_name)
                    # Add to call graph
                    self._call_graph[func_id].add(call_name)

        # Calculate span
        start_line = node.lineno
        end_line = (
            node.end_lineno
            if hasattr(node, "end_lineno") and node.end_lineno is not None
            else start_line
        )

        return FunctionNode(
            id=func_id,
            name=node.name,
            file_id=file_id,
            node_type="function",
            is_export=is_export,
            start_line=start_line,
            end_line=end_line,
            calls=calls,
            docstring=docstring,
            complexity=complexity,
        )

    def _extract_call_name(self, call_node: ast.Call) -> str | None:
        """Extract the name of a function call."""
        if isinstance(call_node.func, ast.Name):
            return call_node.func.id
        elif isinstance(call_node.func, ast.Attribute):
            return ast.unparse(call_node.func)
        return None

    async def get_function_context(
        self,
        function_name: str,
        include_callers: bool = True,
        include_callees: bool = True,
        max_depth: int = 3,
    ) -> dict[str, Any]:
        """
        Get comprehensive context for a function.

        Args:
            function_name: Name of the function to query
            include_callers: Include functions that call this function
            include_callees: Include functions that this function calls
            max_depth: Maximum depth for call graph traversal

        Returns:
            Function context including callers, callees, and metadata
        """
        func_node = self._find_function_node(function_name)
        if not func_node:
            raise ValueError(f"Function not found: {function_name}")

        context: dict[str, Any] = {
            "function": self._build_function_metadata(func_node),
            "callers": [],
            "callees": [],
        }

        # Get callers and callees based on flags
        if include_callers:
            context["callers"] = self._get_callers(function_name)

        if include_callees:
            context["callees"] = self._get_callees(func_node)

        return context

    def _find_function_node(self, function_name: str) -> FunctionNode | None:
        """Find a function node by name."""
        for node in self.nodes.values():
            if node.node_type == "function" and node.name == function_name:
                if isinstance(node, FunctionNode):
                    return node
        return None

    def _build_function_metadata(self, func_node: FunctionNode) -> dict[str, Any]:
        """Build function metadata dictionary."""
        return {
            "name": func_node.name,
            "file": func_node.file_id,
            "start_line": func_node.start_line,
            "end_line": func_node.end_line,
            "is_export": func_node.is_export,
        }

    def _get_callers(self, function_name: str) -> list[dict[str, Any]]:
        """Get list of functions that call the specified function."""
        callers = []
        for caller_id, callees in self._call_graph.items():
            if function_name in callees:
                caller_node = self.nodes.get(caller_id)
                if caller_node and isinstance(caller_node, FunctionNode):
                    callers.append(
                        {
                            "name": caller_node.name,
                            "file": caller_node.file_id,
                            "line": caller_node.start_line,
                        }
                    )
        return callers

    def _get_callees(self, func_node: FunctionNode) -> list[dict[str, Any]]:
        """Get list of functions called by the specified function."""
        callees = []
        for callee_name in func_node.calls:
            callee_node = self._find_function_by_name(callee_name)
            if callee_node:
                callees.append(
                    {
                        "name": callee_node.name,
                        "file": callee_node.file_id,
                        "line": callee_node.start_line,
                    }
                )
        return callees

    def _find_function_by_name(self, name: str) -> FunctionNode | None:
        """Find a function node by name."""
        for node in self.nodes.values():
            if (
                node.node_type == "function"
                and node.name == name
                and isinstance(node, FunctionNode)
            ):
                return node
        return None

    async def find_related_files(
        self,
        file_path: str,
        relationship_type: str = "all",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Find files related to a specific file based on imports and call relationships.

        Args:
            file_path: Path to source file (relative to project_path)
            relationship_type: Type of relationship (imports, imported_by, calls, called_by, all)
            limit: Maximum number of related files to return

        Returns:
            List of related files with relationship types and strength
        """
        file_id = str(Path(file_path))
        related_files: list[dict[str, Any]] = []

        # Get imports from this file
        imports, imports_from = self._get_file_imports(file_id)

        # Add relationships based on type
        if relationship_type in ("imported_by", "all"):
            related_files.extend(self._find_imported_by_relationships(file_id))

        if relationship_type in ("imports", "all"):
            related_files.extend(
                self._find_imports_relationships(imports | imports_from)
            )

        if relationship_type in ("calls", "all"):
            file_func_ids = self._get_file_function_ids(file_id)
            related_files.extend(self._find_calls_relationships(file_func_ids, file_id))

        if relationship_type in ("called_by", "all"):
            file_func_ids = self._get_file_function_ids(file_id)
            related_files.extend(self._find_called_by_relationships(file_func_ids))

        # Aggregate by file and sort by strength
        result = self._aggregate_and_sort_results(related_files)

        return result[:limit]

    def _get_file_imports(self, file_id: str) -> tuple[set[str], set[str]]:
        """Get imports from a specific file."""
        imports = set()
        imports_from = set()
        for node in self.nodes.values():
            if node.file_id == file_id and node.node_type == "import":
                if isinstance(node, ImportNode):
                    if node.is_from_import:
                        imports_from.add(node.module)
                    else:
                        imports.add(node.module)
        return imports, imports_from

    def _find_imported_by_relationships(self, file_id: str) -> list[dict[str, Any]]:
        """Find files that import this file's modules."""
        related_files = []
        for node in self.nodes.values():
            if node.node_type == "import" and node.file_id != file_id:
                if isinstance(node, ImportNode):
                    # Check if this import references our file
                    if any(
                        imp in file_id for imp in [node.module] + node.imported_names
                    ):
                        related_files.append(
                            {
                                "file_path": node.file_id,
                                "relationship": "imported_by",
                                "strength": 1,
                            }
                        )
        return related_files

    def _find_imports_relationships(
        self, all_imports: set[str]
    ) -> list[dict[str, Any]]:
        """Find files that this file imports."""
        related_files = []
        for module in all_imports:
            for node in self.nodes.values():
                if node.node_type == "file" and module in node.file_id:
                    related_files.append(
                        {
                            "file_path": node.file_id,
                            "relationship": "imports",
                            "strength": 1,
                        }
                    )
        return related_files

    def _get_file_function_ids(self, file_id: str) -> list[str]:
        """Get function IDs for a specific file."""
        return [
            node.id
            for node in self.nodes.values()
            if node.file_id == file_id and node.node_type == "function"
        ]

    def _find_calls_relationships(
        self, file_func_ids: list[str], file_id: str
    ) -> list[dict[str, Any]]:
        """Find files with calls relationships."""
        related_files = []
        for func_id in file_func_ids:
            for callee in self._call_graph.get(func_id, set()):
                callee_node = self.nodes.get(f"{file_id}:function:{callee}")
                if callee_node:
                    related_files.append(
                        {
                            "file_path": callee_node.file_id,
                            "relationship": "calls",
                            "strength": 1,
                        }
                    )
        return related_files

    def _find_called_by_relationships(
        self, file_func_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Find files that call functions in this file."""
        related_files = []
        for caller_id, callees in self._call_graph.items():
            if any(func_id in callees for func_id in file_func_ids):
                caller_node = self.nodes.get(caller_id)
                if caller_node:
                    related_files.append(
                        {
                            "file_path": caller_node.file_id,
                            "relationship": "called_by",
                            "strength": 1,
                        }
                    )
        return related_files

    def _aggregate_and_sort_results(
        self, related_files: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Aggregate by file and sort by strength."""
        aggregated: dict[str, dict[str, Any]] = {}
        for rf in related_files:
            fp = rf["file_path"]
            if fp not in aggregated:
                aggregated[fp] = {"file_path": fp, "relationship": [], "strength": 0}
            aggregated[fp]["relationship"].append(rf["relationship"])
            aggregated[fp]["strength"] += rf["strength"]

        # Convert to list and sort
        result = list(aggregated.values())
        result.sort(key=operator.itemgetter("strength"), reverse=True)

        return result

# MCP Tool Contracts for Code Graph Operations

# Version: 0.4.0

# Purpose: Define schemas for code graph tools shared across Session Buddy and Mahavishnu

______________________________________________________________________

## Tool: `index_code_graph`

Description: Analyze and index codebase structure for better context compaction and RAG enhancement.

Parameters:

```yaml
project_path:
  type: string
  description: Absolute path to project directory
  required: true
  format: absolute-path
languages:
  type: array
  description: Programming languages to index (default: ["python"])
  items:
    type: string
    enum: [python, javascript, typescript, ruby]
  required: false
include_tests:
  type: boolean
  description: Whether to include test files in indexing
  required: false
  default: false
```

Returns:

```yaml
success:
  type: boolean
stats:
  type: object
  properties:
    files_indexed:
      type: integer
    functions_indexed:
      type: integer
    classes_indexed:
      type: integer
    calls_indexed:
      type: integer
    imports_indexed:
      type: integer
    duration_ms:
      type: integer
```

Error Cases:

- `project_path` does not exist → Return `{success: false, error: "Directory not found"}`
- No supported language files found → Return `{success: false, error: "No code files found"}`
- Parse errors during indexing → Log warning, continue with successfully parsed files

______________________________________________________________________

## Tool: `get_function_context`

Description: Get comprehensive context for a function including callers, callees, and related code.

Parameters:

```yaml
project_path:
  type: string
  description: Absolute path to project directory
  required: true
  format: absolute-path
function_name:
  type: string
  description: Function name to query
  required: true
include_callers:
  type: boolean
  description: Include functions that call this function
  required: false
  default: true
include_callees:
  type: boolean
  description: Include functions that this function calls
  required: false
  default: true
max_depth:
  type: integer
  description: Maximum depth for call graph traversal
  required: false
  default: 3
```

Returns:

```yaml
success:
  type: boolean
context:
  type: object
  properties:
    function:
      type: object
      properties:
        name:
          type: string
        file:
          type: string
        start_line:
          type: integer
        end_line:
          type: integer
        is_export:
          type: boolean
    callers:
      type: array
      description: Functions that call this function
      items:
        type: object
        properties:
          name:
            type: string
          file:
            type: string
          line:
            type: integer
    callees:
      type: array
      description: Functions that this function calls
      items:
        type: object
        properties:
          name:
            type: string
          file:
            type: string
          line:
            type: integer
```

Error Cases:

- Function not found → Return `{success: false, error: "Function not found"}`
- Code graph not indexed → Return `{success: false, error: "Code graph not indexed. Run index_code_graph first."}`

______________________________________________________________________

## Tool: `find_related_code`

Description: Find code related to a specific file based on imports and call relationships.

Parameters:

```yaml
project_path:
  type: string
  description: Absolute path to project directory
  required: true
  format: absolute-path
file_path:
  type: string
  description: Path to source file (relative to project_path)
  required: true
relationship_type:
  type: string
  description: Type of relationship to find
  required: false
  default: all
  enum: [imports, imported_by, calls, called_by, all]
limit:
  type: integer
  description: Maximum number of related files to return
  required: false
  default: 20
```

Returns:

```yaml
success:
  type: boolean
related_files:
  type: array
  items:
    type: object
    properties:
      file_path:
        type: string
      relationship:
        type: string
        enum: [imports, imported_by, calls, called_by]
      strength:
        type: integer
        description: Number of relationships (imports, calls, etc.)
```

Error Cases:

- File not found → Return `{success: false, error: "File not found"}`
- File not indexed → Return `{success: false, error: "File not in code graph. Run index_code_graph first."}`

______________________________________________________________________

## Implementation Notes

### Session Buddy Implementation

File: `session_buddy/mcp/tools/code_graph_tools.py`

```python
from fastmcp import FastMCP
from mcp_common.code_graph import CodeGraphAnalyzer
from pathlib import Path

mcp = FastMCP("session-buddy-code-graph")

@mcp.tool()
async def index_code_graph(
    project_path: str,
    languages: list[str] | None = None,
    include_tests: bool = False
) -> dict:
    """Index codebase structure for better context compaction."""
    # Use mcp-common CodeGraphAnalyzer
    analyzer = CodeGraphAnalyzer(Path(project_path))
    stats = await analyzer.analyze_repository(project_path)

    return {
        "success": True,
        "stats": stats
    }

@mcp.tool()
async def get_function_context(
    project_path: str,
    function_name: str,
    include_callers: bool = True,
    include_callees: bool = True,
    max_depth: int = 3
) -> dict:
    """Get comprehensive context for a function."""
    analyzer = CodeGraphAnalyzer(Path(project_path))
    context = await analyzer.get_function_context(function_name)

    return {
        "success": True,
        "context": context
    }

@mcp.tool()
async def find_related_code(
    project_path: str,
    file_path: str,
    relationship_type: str = "all",
    limit: int = 20
) -> dict:
    """Find code related to a specific file."""
    analyzer = CodeGraphAnalyzer(Path(project_path))
    related = await analyzer.find_related_files(file_path, relationship_type)

    return {
        "success": True,
        "related_files": related[:limit]
    }
```

### Mahavishnu Implementation

File: `mahavishnu/mcp/tools/code_graph_tools.py`

```python
from fastmcp import FastMCP
from mcp_common.code_graph import CodeGraphAnalyzer
from pathlib import Path

mcp = FastMCP("mahavishnu-code-graph")

@mcp.tool()
async def index_code_graph(
    project_path: str,
    languages: list[str] | None = None,
    include_tests: bool = False
) -> dict:
    """Index codebase structure for RAG enhancement."""
    # Use same mcp-common CodeGraphAnalyzer
    analyzer = CodeGraphAnalyzer(Path(project_path))
    stats = await analyzer.analyze_repository(project_path)

    return {
        "success": True,
        "stats": stats
    }

@mcp.tool()
async def get_function_context(
    project_path: str,
    function_name: str,
    include_callers: bool = True,
    include_callees: bool = True,
    max_depth: int = 3
) -> dict:
    """Get function context for enhanced RAG retrieval."""
    analyzer = CodeGraphAnalyzer(Path(project_path))
    context = await analyzer.get_function_context(function_name)

    return {
        "success": True,
        "context": context
    }

@mcp.tool()
async def find_related_code(
    project_path: str,
    file_path: str,
    relationship_type: str = "all",
    limit: int = 20
) -> dict:
    """Find related code for workflow context."""
    analyzer = CodeGraphAnalyzer(Path(project_path))
    related = await analyzer.find_related_files(file_path, relationship_type)

    return {
        "success": True,
        "related_files": related[:limit]
    }
```

### Cross-Project Usage

Mahavishnu can call Session Buddy's code graph tools:

```python
# In Mahavishnu workflow execution
from mahavishnu.core.session_buddy_client import SessionBuddyMCPClient

sb_client = SessionBuddyMCPClient()

# Query Session Buddy's code graph
context = await sb_client.call_tool(
    "get_function_context",
    {
        "project_path": "/path/to/session/buddy/project",
        "function_name": "authenticate_user"
    }
)

# Use context in workflow execution
```

______________________________________________________________________

## Version History

- 0.4.0 (2025-01-24): Initial version with code graph tools
- Planned: Documentation indexing tools
- Planned: Complexity analysis tools

______________________________________________________________________

Contract Status: ✅ Ready for implementation
Implement by: End of Phase 0 (Week 2)
Consumed by: Session Buddy (Phase 1), Mahavishnu (Phase 2)

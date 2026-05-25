"""RestrictedPython sandbox for secure function execution.

This module provides a secure sandbox using RestrictedPython to execute
custom user-defined functions with restricted capabilities.

Phase 1: RestrictedPython (current)
Phase 2: Pyodide (WebAssembly)
Phase 3: gVisor container
"""

import asyncio
import json
import logging
from typing import Any

from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Guards import safe_iter_unpack_sequence, guarded_getattr, full_write_guard

logger = logging.getLogger(__name__)

# Allowed built-in functions for sandboxed code
ALLOWED_BUILTINS = {
    # Safe builtins from RestrictedPython
    **safe_globals.get("__builtins__", {}),
    # Math and data structure operations
    "len": len,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "sorted": sorted,
    "all": all,
    "any": any,
    # Type constructors
    "list": list,
    "dict": dict,
    "set": set,
    "tuple": tuple,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "type": type,
    "isinstance": isinstance,
    "hasattr": hasattr,
    "getattr": getattr,
    # String methods (safe)
    "repr": repr,
    "format": format,
    "chr": chr,
    "ord": ord,
    # JSON
    "json": json,
}

# Explicitly forbidden functions (defense in depth)
FORBIDDEN_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "input",
    "os", "sys", "subprocess", "socket", "urllib", "http",
    "requests", "importlib", "module", "builtins", "__builtins__",
    "__class__", "__bases__", "__subclasses__", "__mro__",
}


class SecurityError(Exception):
    """Raised when sandboxed code attempts a forbidden operation."""
    pass


class FunctionResult:
    """Result of sandboxed function execution."""
    def __init__(self, success: bool, output: Any = None, error: str = ""):
        self.success = success
        self.output = output
        self.error = error
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
        }


def _check_forbidden_names(code: str) -> list[str]:
    """Scan code for forbidden import/function names."""
    import ast
    
    found = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    
    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split('.')[0] in FORBIDDEN_NAMES:
                    found.append(f"Forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split('.')[0] in FORBIDDEN_NAMES:
                found.append(f"Forbidden import from: {node.module}")
        # Check attribute access like os.system
        elif isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN_NAMES:
                found.append(f"Forbidden attribute: {node.attr}")
        # Check name references
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES:
                found.append(f"Forbidden name: {node.id}")
    
    return found


async def execute_restricted(
    code: str,
    input_data: dict,
    timeout: float = 30.0,
) -> FunctionResult:
    """
    Execute Python code in RestrictedPython sandbox.
    
    Args:
        code: Python source code to execute
        input_data: Data available as 'input' variable in sandbox
        timeout: Maximum execution time in seconds
    
    Returns:
        FunctionResult with success status, output, and error message
    """
    # Phase 0: Scan for forbidden names
    forbidden = _check_forbidden_names(code)
    if forbidden:
        return FunctionResult(
            success=False,
            error=f"SecurityError: Forbidden operations detected: {', '.join(forbidden)}"
        )
    
    # Phase 1: Compile with RestrictedPython
    try:
        byte_code = compile_restricted(code, "<sandbox>", "exec")
    except SyntaxError as e:
        return FunctionResult(success=False, error=f"SyntaxError: {e}")
    except Exception as e:
        return FunctionResult(success=False, error=f"Compilation error: {e}")
    
    # Phase 2: Prepare restricted globals
    restricted_globals = {
        "__builtins__": ALLOWED_BUILTINS,
        "_getattr_": guarded_getattr,
        "_iter_unpack_sequence_": safe_iter_unpack_sequence,
        "_write_": full_write_guard,
        "input": input_data,
        "result": None,
    }
    
    # Phase 3: Execute with timeout
    def _exec():
        local_vars = {}
        exec(byte_code, restricted_globals, local_vars)
        return restricted_globals.get("result", local_vars.get("result"))
    
    try:
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, _exec),
            timeout=timeout
        )
        return FunctionResult(success=True, output=result)
    except asyncio.TimeoutError:
        return FunctionResult(success=False, error=f"Execution timeout (limit {timeout}s)")
    except SecurityError as e:
        return FunctionResult(success=False, error=f"SecurityError: {e}")
    except Exception as e:
        return FunctionResult(success=False, error=f"RuntimeError: {type(e).__name__}: {e}")

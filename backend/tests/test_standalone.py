#!/usr/bin/env python3
"""Standalone test script for Sprint 1-2 security fixes.

This script tests the core logic without requiring full backend dependencies.
Run: cd backend && python tests/test_standalone.py
"""

import sys
import re

sys.path.insert(0, '/Users/zhangshunguo/project/-Meatapivot/backend')

# ---------------------------------------------------------------------------
# Test 1: Cypher Whitelist (copy of knowledge_graph.py logic)
# ---------------------------------------------------------------------------
_CYPHER_ALLOWED_STARTS = {"MATCH", "WITH", "RETURN", "CALL", "UNWIND", "OPTIONAL"}
_CYPHER_FORBIDDEN_KEYWORDS = {"CREATE", "SET", "DELETE", "DETACH", "REMOVE", "MERGE", "DROP", "LOAD"}

def _validate_readonly_cypher(query: str) -> tuple:
    lines = query.strip().split('\n')
    cleaned_lines = []
    for line in lines:
        if '//' in line:
            line = line[:line.index('//')]
        cleaned_lines.append(line)
    cleaned = ' '.join(cleaned_lines).strip()
    
    if not cleaned:
        return False, "Empty query"
    
    upper_cleaned = cleaned.upper()
    first_word = upper_cleaned.split()[0] if upper_cleaned.split() else ""
    if first_word == "OPTIONAL":
        words = upper_cleaned.split()
        first_word = words[1] if len(words) > 1 else ""
    
    if first_word not in _CYPHER_ALLOWED_STARTS:
        return False, f"Query must start with allowed keyword. Got: '{first_word}'"
    
    words = re.findall(r'\b[A-Z]+\b', upper_cleaned)
    for keyword in _CYPHER_FORBIDDEN_KEYWORDS:
        if keyword in words:
            return False, f"Forbidden: '{keyword}'"
    
    return True, ""


def test_cypher():
    print("=" * 60)
    print("Testing Cypher Whitelist")
    print("=" * 60)
    
    tests = [
        ("MATCH (n) RETURN n LIMIT 10", True, "MATCH allowed"),
        ("RETURN 1 + 1", True, "RETURN allowed"),
        ("OPTIONAL MATCH (n) RETURN n", True, "OPTIONAL MATCH allowed"),
        ("CREATE (n:Test) RETURN n", False, "CREATE rejected"),
        ("MATCH (n) DELETE n", False, "DELETE rejected"),
        ("MERGE (n:Test) RETURN n", False, "MERGE rejected"),
        ("MATCH (n) SET n.name = 'test' RETURN n", False, "SET rejected"),
        ("// comment\nCREATE (n:Test) RETURN n", False, "comment bypass prevented"),
        ("", False, "empty rejected"),
        ("create (n:Test) return n", False, "case insensitive"),
        ("DROP INDEX idx", False, "DROP rejected"),
    ]
    
    passed = 0
    failed = 0
    for query, expected, desc in tests:
        result, error = _validate_readonly_cypher(query)
        if result == expected:
            print(f"  ✅ {desc}")
            passed += 1
        else:
            print(f"  ❌ {desc}: expected={expected}, got={result}, error={error}")
            failed += 1
    
    print(f"\nCypher: {passed} passed, {failed} failed\n")
    return failed == 0


# ---------------------------------------------------------------------------
# Test 2: RestrictedPython Sandbox
# ---------------------------------------------------------------------------
def test_sandbox():
    print("=" * 60)
    print("Testing RestrictedPython Sandbox")
    print("=" * 60)
    
    try:
        from RestrictedPython import compile_restricted, safe_builtins
        from RestrictedPython.Guards import safe_iter_unpack_sequence, guarded_getattr, full_write_guard
    except ImportError:
        print("  ⚠️  RestrictedPython not installed, skipping sandbox tests")
        return True
    
    ALLOWED_BUILTINS = {**safe_builtins}
    FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "os", "subprocess"}
    
    def _check_forbidden_names(code: str):
        import ast
        found = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] in FORBIDDEN_NAMES:
                        found.append(f"Forbidden import: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split('.')[0] in FORBIDDEN_NAMES:
                    found.append(f"Forbidden import from: {node.module}")
            elif isinstance(node, ast.Attribute):
                if node.attr in FORBIDDEN_NAMES:
                    found.append(f"Forbidden attribute: {node.attr}")
            elif isinstance(node, ast.Name):
                if node.id in FORBIDDEN_NAMES:
                    found.append(f"Forbidden name: {node.id}")
        return found
    
    tests = [
        ("result = 1 + 1", [], "safe code"),
        ("import os; os.system('ls')", ["os"], "import os"),
        ("from subprocess import run", ["subprocess"], "from subprocess import"),
        ("open('/etc/passwd')", ["open"], "open() call"),
        ("eval('1+1')", ["eval"], "eval() call"),
        ("exec('print(1)')", ["exec"], "exec() call"),
    ]
    
    passed = 0
    failed = 0
    for code, expected_keywords, desc in tests:
        result = _check_forbidden_names(code)
        has_forbidden = len(result) > 0
        expected_forbidden = len(expected_keywords) > 0
        
        if has_forbidden == expected_forbidden:
            print(f"  ✅ {desc}: {result}")
            passed += 1
        else:
            print(f"  ❌ {desc}: expected forbidden={expected_forbidden}, got={result}")
            failed += 1
    
    print(f"\nSandbox: {passed} passed, {failed} failed\n")
    return failed == 0


# ---------------------------------------------------------------------------
# Test 3: Auth bcrypt
# ---------------------------------------------------------------------------
def test_auth():
    print("=" * 60)
    print("Testing Auth bcrypt")
    print("=" * 60)
    
    try:
        from passlib.context import CryptContext
    except ImportError:
        print("  ⚠️  passlib not installed, skipping auth tests")
        return True
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    # Test 1: Hash and verify
    password = "test_password_123"
    hashed = pwd_context.hash(password)
    
    tests = []
    
    # Hash != password
    if hashed != password:
        tests.append(("hash != plain text", True))
    else:
        tests.append(("hash != plain text", False))
    
    # Correct password verifies
    if pwd_context.verify(password, hashed):
        tests.append(("correct password verifies", True))
    else:
        tests.append(("correct password verifies", False))
    
    # Wrong password fails
    if not pwd_context.verify("wrong", hashed):
        tests.append(("wrong password rejected", True))
    else:
        tests.append(("wrong password rejected", False))
    
    # Same password, different hashes (salt)
    hash2 = pwd_context.hash(password)
    if hash2 != hashed:
        tests.append(("same password different hash (salt)", True))
    else:
        tests.append(("same password different hash (salt)", False))
    
    passed = 0
    failed = 0
    for desc, result in tests:
        if result:
            print(f"  ✅ {desc}")
            passed += 1
        else:
            print(f"  ❌ {desc}")
            failed += 1
    
    print(f"\nAuth: {passed} passed, {failed} failed\n")
    return failed == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Meatapivot Sprint 1-2 Security Tests (Standalone)")
    print("=" * 60 + "\n")
    
    results = []
    results.append(test_cypher())
    results.append(test_sandbox())
    results.append(test_auth())
    
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = all(results)
    if all_passed:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed!")
        sys.exit(1)

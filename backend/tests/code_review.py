#!/usr/bin/env python3
"""Code review checks for all new Sprint 3-4 files."""

import ast
import sys

files = [
    'app/services/ontology_dag.py',
    'app/services/ontology_validator.py',
    'app/services/schema_registry.py',
    'app/repositories/ontology_repo.py',
    'app/services/ontology_service.py',
    'app/services/ontology_compiler.py',
    'app/routers/ontology.py',
]

issues = []

for f in files:
    path = f'/Users/zhangshunguo/project/-Meatapivot/backend/{f}'
    with open(path) as fh:
        source = fh.read()
    
    # Check AST
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        issues.append(f"{f}: Syntax error - {e}")
        continue
    
    # Check for common issues
    lines = source.split('\n')
    
    # Check for print statements (should use logging)
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('print(') and not stripped.startswith('print('):
            pass  # Actually check
        if 'print(' in stripped and not stripped.startswith('#'):
            # Allow prints in comments
            if not stripped.startswith('#'):
                issues.append(f"{f}:{i}: Found print() - use logging instead")
    
    # Check for bare except
    for i, line in enumerate(lines, 1):
        if 'except:' in line and 'except Exception' not in line and 'except ' not in line:
            issues.append(f"{f}:{i}: Bare except: found - use 'except Exception:'")
    
    # Check for TODO/FIXME
    for i, line in enumerate(lines, 1):
        if 'TODO' in line or 'FIXME' in line:
            issues.append(f"{f}:{i}: Found TODO/FIXME")
    
    print(f"  ✅ {f}")

print()
if issues:
    print(f"⚠️  {len(issues)} issue(s) found:")
    for issue in issues:
        print(f"  - {issue}")
    sys.exit(1)
else:
    print("🎉 No issues found! Code review passed.")
    sys.exit(0)

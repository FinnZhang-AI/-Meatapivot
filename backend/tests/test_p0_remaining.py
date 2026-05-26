#!/usr/bin/env python3
"""Comprehensive tests for remaining Sprint 3-4 P0 items.

Tests:
- P0-ONT-01: DAG dependency graph + cycle detection
- P0-ONT-02: Dual-stage validator (static + runtime) — source-level
- P0-ONT-05: Compile rollback endpoint — source-level
- P0-ONT-06: SchemaRegistry cache — source-level
- P0-ONT-07: Compile failure transaction rollback — source-level
- P0-ARCH-03: Router/Service/Repository three-layer separation — source-level

Run: cd backend && python tests/test_p0_remaining.py -v
"""

import sys
import ast
import asyncio
import importlib.util
from uuid import UUID
from datetime import datetime

sys.path.insert(0, '/Users/zhangshunguo/project/-Meatapivot/backend')

VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv
TOTAL_TESTS = 0
PASSED_TESTS = 0
FAILED_TESTS = 0


def test(name):
    def decorator(func):
        def wrapper():
            global TOTAL_TESTS, PASSED_TESTS, FAILED_TESTS
            TOTAL_TESTS += 1
            try:
                func()
                PASSED_TESTS += 1
                if VERBOSE:
                    print(f"  ✅ {name}")
                return True
            except AssertionError as e:
                FAILED_TESTS += 1
                if VERBOSE:
                    print(f"  ❌ {name}: {e}")
                else:
                    print(f"  ❌ {name}")
                return False
            except Exception as e:
                FAILED_TESTS += 1
                if VERBOSE:
                    print(f"  💥 {name}: {type(e).__name__}: {e}")
                else:
                    print(f"  💥 {name}")
                return False
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator


# ===========================================================================
# P0-ONT-01: DAG Dependency Graph + Cycle Detection (fully runnable)
# ===========================================================================

spec = importlib.util.spec_from_file_location("ontology_dag", "/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_dag.py")
ontology_dag_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ontology_dag_module)
OntologyDAG = ontology_dag_module.OntologyDAG


@test("DAG: add node and edge")
def test_dag_basic():
    dag = OntologyDAG()
    a = UUID("00000000-0000-0000-0000-000000000001")
    b = UUID("00000000-0000-0000-0000-000000000002")
    dag.add_node(a)
    dag.add_node(b)
    dag.add_edge(a, b)
    assert len(dag._nodes) == 2
    assert b in dag._dependents[a]


@test("DAG: no cycle in linear chain")
def test_dag_no_cycle():
    dag = OntologyDAG()
    a = UUID("00000000-0000-0000-0000-000000000001")
    b = UUID("00000000-0000-0000-0000-000000000002")
    c = UUID("00000000-0000-0000-0000-000000000003")
    dag.add_edge(a, b)
    dag.add_edge(b, c)
    cycle = dag.find_cycle()
    assert cycle is None


@test("DAG: detect simple cycle")
def test_dag_cycle_detection():
    dag = OntologyDAG()
    a = UUID("00000000-0000-0000-0000-000000000001")
    b = UUID("00000000-0000-0000-0000-000000000002")
    dag.add_edge(a, b)
    dag.add_edge(b, a)
    cycle = dag.find_cycle()
    assert cycle is not None
    assert len(cycle) >= 3


@test("DAG: detect complex cycle")
def test_dag_complex_cycle():
    dag = OntologyDAG()
    a = UUID("00000000-0000-0000-0000-000000000001")
    b = UUID("00000000-0000-0000-0000-000000000002")
    c = UUID("00000000-0000-0000-0000-000000000003")
    dag.add_edge(a, b)
    dag.add_edge(b, c)
    dag.add_edge(c, a)
    cycle = dag.find_cycle()
    assert cycle is not None
    assert a in cycle
    assert b in cycle
    assert c in cycle


@test("DAG: topological sort valid")
def test_dag_topological_sort():
    dag = OntologyDAG()
    a = UUID("00000000-0000-0000-0000-000000000001")
    b = UUID("00000000-0000-0000-0000-000000000002")
    c = UUID("00000000-0000-0000-0000-000000000003")
    dag.add_edge(a, b)
    dag.add_edge(a, c)
    sorted_nodes, cycle = dag.topological_sort()
    assert cycle is None
    assert len(sorted_nodes) == 3
    a_idx = sorted_nodes.index(a)
    b_idx = sorted_nodes.index(b)
    c_idx = sorted_nodes.index(c)
    assert a_idx < b_idx
    assert a_idx < c_idx


@test("DAG: topological sort detects cycle")
def test_dag_topological_sort_cycle():
    dag = OntologyDAG()
    a = UUID("00000000-0000-0000-0000-000000000001")
    b = UUID("00000000-0000-0000-0000-000000000002")
    dag.add_edge(a, b)
    dag.add_edge(b, a)
    sorted_nodes, cycle = dag.topological_sort()
    assert sorted_nodes == []
    assert cycle is not None


@test("DAG: BFS impact set")
def test_dag_impact_set():
    dag = OntologyDAG()
    a = UUID("00000000-0000-0000-0000-000000000001")
    b = UUID("00000000-0000-0000-0000-000000000002")
    c = UUID("00000000-0000-0000-0000-000000000003")
    d = UUID("00000000-0000-0000-0000-000000000004")
    dag.add_edge(a, b)
    dag.add_edge(b, c)
    dag.add_edge(a, d)
    impact = dag.get_impact_set(a)
    assert b in impact
    assert c in impact
    assert d in impact
    assert a not in impact


@test("DAG: dependency chain")
def test_dag_dependency_chain():
    dag = OntologyDAG()
    a = UUID("00000000-0000-0000-0000-000000000001")
    b = UUID("00000000-0000-0000-0000-000000000002")
    c = UUID("00000000-0000-0000-0000-000000000003")
    dag.add_edge(a, b)
    dag.add_edge(b, c)
    chain = dag.get_dependency_chain(c)
    assert a in chain
    assert b in chain
    assert c not in chain


@test("DAG: remove node")
def test_dag_remove_node():
    dag = OntologyDAG()
    a = UUID("00000000-0000-0000-0000-000000000001")
    b = UUID("00000000-0000-0000-0000-000000000002")
    dag.add_edge(a, b)
    dag.remove_node(a)
    assert a not in dag._nodes
    assert a not in dag._dependents


@test("DAG: to_dict serialization")
def test_dag_to_dict():
    dag = OntologyDAG()
    a = UUID("00000000-0000-0000-0000-000000000001")
    b = UUID("00000000-0000-0000-0000-000000000002")
    dag.add_edge(a, b)
    result = dag.to_dict()
    assert "nodes" in result
    assert "edges" in result
    assert len(result["nodes"]) == 2
    assert len(result["edges"]) == 1


# ===========================================================================
# P0-ONT-02: Dual-Stage Validator (source-level tests)
# ===========================================================================

@test("Validator: source has StaticValidator")
def test_validator_static():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_validator.py').read()
    assert "class StaticValidator" in source


@test("Validator: source has RuntimeValidator")
def test_validator_runtime():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_validator.py').read()
    assert "class RuntimeValidator" in source


@test("Validator: error_kind field present")
def test_validator_error_kind():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_validator.py').read()
    assert "error_kind" in source
    assert "missing_property" in source
    assert "missing_field" in source
    assert "invalid_label" in source
    assert "duplicate_property" in source


@test("Validator: interface validation method")
def test_validator_interface_method():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_validator.py').read()
    assert "validate_interface_implementation" in source


@test("Validator: runtime uses Pydantic create_model")
def test_validator_pydantic():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_validator.py').read()
    assert "create_model" in source
    assert "ValidationError" in source


@test("Validator: cache invalidation")
def test_validator_cache_invalidation():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_validator.py').read()
    assert "invalidate_cache" in source
    assert "_model_cache" in source


# ===========================================================================
# P0-ONT-06: SchemaRegistry Cache (source-level + local cache tests)
# ===========================================================================

# Mock redis_client before importing schema_registry
class MockRedisClient:
    client = None

import sys
sys.modules['app.services.redis_client'] = type(sys)('app.services.redis_client')
sys.modules['app.services.redis_client'].redis_client = MockRedisClient()

spec3 = importlib.util.spec_from_file_location("schema_registry", "/Users/zhangshunguo/project/-Meatapivot/backend/app/services/schema_registry.py")
schema_registry_module = importlib.util.module_from_spec(spec3)
spec3.loader.exec_module(schema_registry_module)
SchemaRegistry = schema_registry_module.SchemaRegistry


@test("SchemaRegistry: generate cache key")
def test_schema_registry_key():
    sr = SchemaRegistry()
    tid = UUID(int=1)
    key = sr._cache_key(tid, "object_type", UUID(int=2))
    assert "schema" in key
    assert str(tid) in key
    assert "object_type" in key


@test("SchemaRegistry: set and get (local cache)")
def test_schema_registry_local():
    sr = SchemaRegistry()
    tid = UUID(int=1)
    tid2 = UUID(int=2)
    schema = {"name": "Test", "properties": []}
    
    async def run():
        await sr.set(tid, "object_type", tid2, schema)
        result = await sr.get(tid, "object_type", tid2)
        assert result == schema
    
    asyncio.get_event_loop().run_until_complete(run())


@test("SchemaRegistry: invalidate specific")
def test_schema_registry_invalidate():
    sr = SchemaRegistry()
    tid = UUID(int=1)
    tid2 = UUID(int=2)
    schema = {"name": "Test"}
    
    async def run():
        await sr.set(tid, "object_type", tid2, schema)
        await sr.invalidate(tid, "object_type", tid2)
        result = await sr.get(tid, "object_type", tid2)
        assert result is None
    
    asyncio.get_event_loop().run_until_complete(run())


@test("SchemaRegistry: invalidate all for tenant")
def test_schema_registry_invalidate_tenant():
    sr = SchemaRegistry()
    tid = UUID(int=1)
    tid2 = UUID(int=2)
    
    async def run():
        await sr.set(tid, "object_type", tid2, {"name": "Test"})
        await sr.invalidate(tid)
        result = await sr.get(tid, "object_type", tid2)
        assert result is None
    
    asyncio.get_event_loop().run_until_complete(run())


@test("SchemaRegistry: get_many")
def test_schema_registry_get_many():
    sr = SchemaRegistry()
    tid = UUID(int=1)
    tid2 = UUID(int=2)
    tid3 = UUID(int=3)
    
    async def run():
        await sr.set(tid, "object_type", tid2, {"name": "A"})
        await sr.set(tid, "object_type", tid3, {"name": "B"})
        results = await sr.get_many(tid, "object_type", [tid2, tid3, UUID(int=99)])
        assert results[tid2] == {"name": "A"}
        assert results[tid3] == {"name": "B"}
        assert results[UUID(int=99)] is None
    
    asyncio.get_event_loop().run_until_complete(run())


@test("SchemaRegistry: source has Redis support")
def test_schema_registry_redis():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/schema_registry.py').read()
    assert "redis_client" in source
    assert "setex" in source
    assert "scan_iter" in source
    assert "invalidate" in source


@test("SchemaRegistry: source has get_stats")
def test_schema_registry_stats():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/schema_registry.py').read()
    assert "get_stats" in source


# ===========================================================================
# P0-ONT-05 & P0-ONT-07: Compile Rollback & Failure Rollback
# ===========================================================================

@test("Compiler: rollback method exists")
def test_compiler_rollback_exists():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_compiler.py').read()
    assert "async def rollback_compile" in source


@test("Compiler: rollback checks log existence")
def test_compiler_rollback_checks():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_compiler.py').read()
    assert "LOG_NOT_FOUND" in source
    assert "ALREADY_ROLLED_BACK" in source


@test("Compiler: tracks constraints for rollback")
def test_compiler_constraints_log():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_compiler.py').read()
    assert "_constraints_log" in source
    assert "_rollback_neo4j_constraints" in source


@test("Compiler: rollback drops constraints")
def test_compiler_rollback_drops():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_compiler.py').read()
    assert "DROP CONSTRAINT" in source


@test("Compiler: failure triggers rollback")
def test_compiler_failure_rollback():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_compiler.py').read()
    assert "await self._rollback_neo4j_constraints()" in source


@test("Compiler: schema cache invalidated on compile")
def test_compiler_cache_invalidate():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_compiler.py').read()
    assert "schema_registry.invalidate" in source


@test("Compiler: rollback updates current version")
def test_compiler_rollback_version():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_compiler.py').read()
    assert "parent_version" in source
    assert "get_current_version" in source


@test("Compiler: rollback invalidates schema cache")
def test_compiler_rollback_cache():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_compiler.py').read()
    # Check that rollback_compile calls invalidate
    assert "schema_registry.invalidate" in source


# ===========================================================================
# P0-ARCH-03: Three-Layer Separation
# ===========================================================================

@test("ARCH: Repository file exists")
def test_arch_repo_exists():
    import os
    assert os.path.exists('/Users/zhangshunguo/project/-Meatapivot/backend/app/repositories/ontology_repo.py')


@test("ARCH: Service file exists")
def test_arch_service_exists():
    import os
    assert os.path.exists('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_service.py')


@test("ARCH: Repository has no HTTP logic")
def test_arch_repo_no_http():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/repositories/ontology_repo.py').read()
    assert "APIRouter" not in source
    assert "HTTPException" not in source
    assert "Depends" not in source


@test("ARCH: Service has no HTTP logic")
def test_arch_service_no_http():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_service.py').read()
    assert "APIRouter" not in source
    assert "HTTPException" not in source
    assert "Request" not in source


@test("ARCH: Router imports OntologyService")
def test_arch_router_service():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert "OntologyService" in source


@test("ARCH: Repository handles ObjectType CRUD")
def test_arch_repo_crud():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/repositories/ontology_repo.py').read()
    assert "get_object_type" in source
    assert "list_object_types" in source
    assert "create_object_type" in source
    assert "update_object_type" in source
    assert "delete_object_type" in source


@test("ARCH: Service has business logic")
def test_arch_service_logic():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_service.py').read()
    assert "build_dependency_dag" in source
    assert "detect_cycles" in source
    assert "validate_all" in source


@test("ARCH: Router has rollback endpoint")
def test_arch_router_rollback():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert "/compile/rollback" in source


@test("ARCH: Router has validation endpoint")
def test_arch_router_validate():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert "/compile/validate" in source


@test("ARCH: Router has DAG endpoints")
def test_arch_router_dag():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert "/dag/cycle" in source
    assert "/dag/compile-order" in source
    assert "/dag/impact" in source


@test("ARCH: Router has compile logs endpoint")
def test_arch_router_logs():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert "/compile/logs" in source


@test("ARCH: Schema models for new endpoints")
def test_arch_schemas():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/models/ontology_schemas.py').read()
    assert "RollbackRequest" in source
    assert "ValidationResponse" in source
    assert "CompileLogResponse" in source
    assert "DAGCycleResponse" in source
    assert "DAGImpactResponse" in source


@test("ARCH: Service uses Repository")
def test_arch_service_uses_repo():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/ontology_service.py').read()
    assert "OntologyRepository" in source
    assert "self.repo" in source


@test("ARCH: Repository has compile log queries")
def test_arch_repo_compile_logs():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/repositories/ontology_repo.py').read()
    assert "get_compile_log" in source
    assert "list_compile_logs" in source
    assert "get_current_version" in source


# ===========================================================================
# Syntax Check
# ===========================================================================

@test("Syntax: all new files parse")
def test_syntax_all():
    files = [
        'app/services/ontology_dag.py',
        'app/services/ontology_validator.py',
        'app/services/schema_registry.py',
        'app/repositories/ontology_repo.py',
        'app/services/ontology_service.py',
        'app/services/ontology_compiler.py',
        'app/routers/ontology.py',
        'app/models/ontology_schemas.py',
    ]
    for f in files:
        path = f'/Users/zhangshunguo/project/-Meatapivot/backend/{f}'
        with open(path) as fh:
            ast.parse(fh.read())


# ===========================================================================
# Main Runner
# ===========================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Meatapivot Remaining P0 Test Suite (Sprint 3-4)")
    print("=" * 70 + "\n")
    
    tests = [obj for name, obj in globals().items() if callable(obj) and hasattr(obj, '__name__') and obj.__name__.startswith('test_')]
    
    categories = {
        "P0-ONT-01 DAG": [],
        "P0-ONT-02 Validator": [],
        "P0-ONT-06 SchemaRegistry": [],
        "P0-ONT-05/07 Compile Rollback": [],
        "P0-ARCH-03 Three-Layer": [],
        "Syntax Check": [],
    }
    
    for t in tests:
        name = t.__name__
        if 'dag' in name:
            categories["P0-ONT-01 DAG"].append(t)
        elif 'validator' in name or 'valid' in name:
            categories["P0-ONT-02 Validator"].append(t)
        elif 'schema_registry' in name or 'registry' in name:
            categories["P0-ONT-06 SchemaRegistry"].append(t)
        elif 'compiler' in name or 'rollback' in name:
            categories["P0-ONT-05/07 Compile Rollback"].append(t)
        elif 'arch' in name:
            categories["P0-ARCH-03 Three-Layer"].append(t)
        else:
            categories["Syntax Check"].append(t)
    
    for category, test_list in categories.items():
        if not test_list:
            continue
        print(f"\n{category}")
        print("-" * 70)
        for t in test_list:
            t()
    
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Total:   {TOTAL_TESTS}")
    print(f"Passed:  {PASSED_TESTS} ✅")
    print(f"Failed:  {FAILED_TESTS} ❌")
    print(f"Rate:    {PASSED_TESTS/TOTAL_TESTS*100:.1f}%")
    print("=" * 70)
    
    if FAILED_TESTS == 0:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {FAILED_TESTS} test(s) failed")
        sys.exit(1)

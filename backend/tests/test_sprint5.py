#!/usr/bin/env python3
"""Sprint 5 tests: Prometheus metrics, Nginx config, OIDC, Dashboard.

Run: cd backend && python tests/test_sprint5.py -v
"""

import sys
import ast
import os

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
# S5-1: PATCH ObjectType
# ===========================================================================

@test("S5-1: PATCH /object-types/{id} endpoint exists")
def test_patch_endpoint():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert '@router.patch("/object-types/{id}"' in source


@test("S5-1: PATCH uses model_dump exclude_unset")
def test_patch_exclude_unset():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert "exclude_unset=True" in source


@test("S5-1: PATCH returns ObjectTypeResponse")
def test_patch_response_model():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert "@router.patch" in source and "ObjectTypeResponse" in source.split("@router.patch")[1].split("\n")[0]


@test("S5-1: PATCH increments version")
def test_patch_version():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert "ot.version = (ot.version or 1) + 1" in source


# ===========================================================================
# S5-2: Prometheus Custom Metrics
# ===========================================================================

@test("S5-2: metrics.py exists with 5 histograms")
def test_metrics_file():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/core/metrics.py').read()
    assert "COMPILE_FULL_DURATION" in source
    assert "COMPILE_INCREMENTAL_DURATION" in source
    assert "VALIDATION_DURATION" in source
    assert "DAG_DETECT_DURATION" in source
    assert "FUNCTION_EXEC_DURATION" in source


@test("S5-2: histograms have buckets")
def test_metrics_buckets():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/core/metrics.py').read()
    assert "buckets=" in source
    assert "ontology_compile_full_duration_seconds" in source
    assert "ontology_compile_incremental_duration_seconds" in source
    assert "ontology_validation_duration_seconds" in source
    assert "ontology_dag_detect_duration_seconds" in source
    assert "ontology_function_exec_duration_seconds" in source


@test("S5-2: compile endpoint observes histogram")
def test_compile_metrics():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert "COMPILE_FULL_DURATION.observe" in source
    assert "COMPILE_INCREMENTAL_DURATION.observe" in source


@test("S5-2: validate endpoint observes histogram")
def test_validate_metrics():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert "VALIDATION_DURATION.observe" in source


@test("S5-2: dag endpoint observes histogram")
def test_dag_metrics():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert "DAG_DETECT_DURATION.observe" in source
    assert "DAG_CYCLES_DETECTED.inc()" in source


@test("S5-2: action execute endpoint observes histogram")
def test_action_metrics():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert "FUNCTION_EXEC_DURATION.observe" in source


@test("S5-2: metrics imports in router")
def test_metrics_imports():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert "COMPILE_FULL_DURATION" in source
    assert "COMPILE_INCREMENTAL_DURATION" in source
    assert "VALIDATION_DURATION" in source
    assert "DAG_DETECT_DURATION" in source
    assert "FUNCTION_EXEC_DURATION" in source


# ===========================================================================
# S5-3: Nginx API Gateway
# ===========================================================================

@test("S5-3: nginx.conf exists")
def test_nginx_exists():
    assert os.path.exists('/Users/zhangshunguo/project/-Meatapivot/docker/nginx/nginx.conf')


@test("S5-3: nginx has rate limiting")
def test_nginx_rate_limit():
    source = open('/Users/zhangshunguo/project/-Meatapivot/docker/nginx/nginx.conf').read()
    assert "limit_req" in source
    assert "rate=" in source


@test("S5-3: nginx proxies to backend")
def test_nginx_backend():
    source = open('/Users/zhangshunguo/project/-Meatapivot/docker/nginx/nginx.conf').read()
    assert "proxy_pass http://backend" in source


@test("S5-3: nginx proxies to frontend")
def test_nginx_frontend():
    source = open('/Users/zhangshunguo/project/-Meatapivot/docker/nginx/nginx.conf').read()
    assert "proxy_pass http://frontend" in source


@test("S5-3: nginx protects /metrics")
def test_nginx_metrics_acl():
    source = open('/Users/zhangshunguo/project/-Meatapivot/docker/nginx/nginx.conf').read()
    assert "/metrics" in source
    assert "allow" in source
    assert "deny all" in source


@test("S5-3: nginx passes real IP headers")
def test_nginx_headers():
    source = open('/Users/zhangshunguo/project/-Meatapivot/docker/nginx/nginx.conf').read()
    assert "X-Real-IP" in source
    assert "X-Forwarded-For" in source


# ===========================================================================
# S5-4: Keycloak OIDC
# ===========================================================================

@test("S5-4: python-keycloak in requirements")
def test_keycloak_requirements():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/requirements.txt').read()
    assert "python-keycloak" in source


@test("S5-4: keycloak_client.py exists")
def test_keycloak_file():
    assert os.path.exists('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/keycloak_client.py')


@test("S5-4: KeycloakClient class exists")
def test_keycloak_class():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/keycloak_client.py').read()
    assert "class KeycloakClient" in source


@test("S5-4: Keycloak has exchange_code method")
def test_keycloak_exchange():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/keycloak_client.py').read()
    assert "exchange_code" in source


@test("S5-4: Keycloak has userinfo method")
def test_keycloak_userinfo():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/keycloak_client.py').read()
    assert "get_userinfo" in source


@test("S5-4: Keycloak has logout method")
def test_keycloak_logout():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/services/keycloak_client.py').read()
    assert "logout" in source


@test("S5-4: OIDC router exists")
def test_oidc_router():
    assert os.path.exists('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/oidc.py')


@test("S5-4: OIDC has login endpoint")
def test_oidc_login():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/oidc.py').read()
    assert "/login" in source


@test("S5-4: OIDC has callback endpoint")
def test_oidc_callback():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/oidc.py').read()
    assert "/callback" in source


@test("S5-4: OIDC has userinfo endpoint")
def test_oidc_userinfo():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/oidc.py').read()
    assert "/userinfo" in source


@test("S5-4: OIDC returns 503 when disabled")
def test_oidc_disabled():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/oidc.py').read()
    assert "503" in source
    assert "not configured" in source.lower() or "not enabled" in source.lower()


@test("S5-4: config has KEYCLOAK settings")
def test_keycloak_config():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/core/config.py').read()
    assert "KEYCLOAK_SERVER_URL" in source
    assert "KEYCLOAK_REALM" in source
    assert "KEYCLOAK_CLIENT_ID" in source


@test("S5-4: OIDC router registered in main.py")
def test_oidc_main():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/main.py').read()
    assert "oidc" in source


# ===========================================================================
# S5-5: Dashboard Real API
# ===========================================================================

@test("S5-5: Dashboard stats endpoint exists")
def test_dashboard_endpoint():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert '"/stats"' in source


@test("S5-5: Dashboard queries real DB")
def test_dashboard_db():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert "func.count()" in source
    assert "OntologyObjectType" in source
    assert "ActionExecutionLog" in source


@test("S5-5: Dashboard returns DashboardStats")
def test_dashboard_schema():
    source = open('/Users/zhangshunguo/project/-Meatapivot/backend/app/routers/ontology.py').read()
    assert "DashboardStats" in source


# ===========================================================================
# Syntax Check
# ===========================================================================

@test("Syntax: all Sprint 5 files parse")
def test_syntax():
    files = [
        'app/core/metrics.py',
        'app/services/keycloak_client.py',
        'app/routers/oidc.py',
        'app/routers/ontology.py',
        'app/main.py',
        'app/core/config.py',
    ]
    for f in files:
        path = f'/Users/zhangshunguo/project/-Meatapivot/backend/{f}'
        with open(path) as fh:
            ast.parse(fh.read())


# ===========================================================================
# Main
# ===========================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Meatapivot Sprint 5 Test Suite")
    print("=" * 70 + "\n")
    
    tests = [obj for name, obj in globals().items() if callable(obj) and hasattr(obj, '__name__') and obj.__name__.startswith('test_')]
    
    categories = {
        "S5-1 PATCH ObjectType": [],
        "S5-2 Prometheus Metrics": [],
        "S5-3 Nginx Gateway": [],
        "S5-4 Keycloak OIDC": [],
        "S5-5 Dashboard API": [],
        "Syntax": [],
    }
    
    for t in tests:
        name = t.__name__
        if 'patch' in name:
            categories["S5-1 PATCH ObjectType"].append(t)
        elif 'metrics' in name or 'histogram' in name or 'compile' in name and 'endpoint' not in name:
            categories["S5-2 Prometheus Metrics"].append(t)
        elif 'nginx' in name:
            categories["S5-3 Nginx Gateway"].append(t)
        elif 'keycloak' in name or 'oidc' in name:
            categories["S5-4 Keycloak OIDC"].append(t)
        elif 'dashboard' in name:
            categories["S5-5 Dashboard API"].append(t)
        else:
            categories["Syntax"].append(t)
    
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

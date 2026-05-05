#!/usr/bin/env python3
"""
Meatapivot Security Scanner
Comprehensive SAST + secret detection + dependency check
"""

import os
import re
import json
import ast
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("D:/project/meatapivot")
REPORTS_DIR = BASE_DIR / "security-reports"
REPORTS_DIR.mkdir(exist_ok=True)

# =============================================================================
# 1. SAST RULES (Bandit-like checks)
# =============================================================================

SAST_RULES = [
    {
        "id": "B102",
        "name": "exec_used",
        "severity": "HIGH",
        "pattern": re.compile(r'\bexec\s*\('),
        "description": "Use of exec() detected. This is dangerous and should be avoided.",
        "files": [".py"],
    },
    {
        "id": "B307",
        "name": "eval_used",
        "severity": "HIGH",
        "pattern": re.compile(r'\beval\s*\('),
        "description": "Use of eval() detected. This is dangerous and should be avoided.",
        "files": [".py"],
    },
    {
        "id": "B605",
        "name": "shell_true",
        "severity": "HIGH",
        "pattern": re.compile(r'shell\s*=\s*True'),
        "description": "shell=True in subprocess calls is dangerous. Use shell=False and pass list of args.",
        "files": [".py"],
    },
    {
        "id": "B301",
        "name": "pickle_load",
        "severity": "MEDIUM",
        "pattern": re.compile(r'\bpickle\.loads?\s*\('),
        "description": "pickle.load/loads can execute arbitrary code. Use json or yaml instead.",
        "files": [".py"],
    },
    {
        "id": "B108",
        "name": "hardcoded_tmp_path",
        "severity": "LOW",
        "pattern": re.compile(r'["\']/(tmp|temp|var/tmp)/[^"\']*["\']'),
        "description": "Hardcoded temp directory path detected.",
        "files": [".py"],
    },
    {
        "id": "B105",
        "name": "hardcoded_password",
        "severity": "MEDIUM",
        "pattern": re.compile(r'(?i)password\s*=\s*["\'][^"\']+["\']'),
        "description": "Possible hardcoded password assignment.",
        "files": [".py", ".ts", ".tsx", ".js", ".yml", ".yaml", ".sh", ".env"],
    },
    {
        "id": "B106",
        "name": "hardcoded_secret",
        "severity": "MEDIUM",
        "pattern": re.compile(r'(?i)(secret|api_?key|token)\s*=\s*["\'][^"\']{8,}["\']'),
        "description": "Possible hardcoded secret/key/token assignment.",
        "files": [".py", ".ts", ".tsx", ".js", ".yml", ".yaml", ".sh", ".env"],
    },
    {
        "id": "B109",
        "name": "insecure_hash",
        "severity": "MEDIUM",
        "pattern": re.compile(r'\bhashlib\.(md5|sha1)\s*\('),
        "description": "Weak hash function (MD5/SHA1) used. Use SHA-256 or better.",
        "files": [".py"],
    },
    {
        "id": "B110",
        "name": "sql_injection_format",
        "severity": "HIGH",
        "pattern": re.compile(r'(?i)(execute|query|run)\s*\(\s*["\'].*%s.*["\']'),
        "description": "Possible SQL/Cypher injection via string formatting.",
        "files": [".py"],
    },
    {
        "id": "B111",
        "name": "debug_mode_true",
        "severity": "LOW",
        "pattern": re.compile(r'DEBUG\s*=\s*True'),
        "description": "DEBUG=True in production configuration.",
        "files": [".py", ".env"],
    },
    {
        "id": "B112",
        "name": "dangerous_input",
        "severity": "HIGH",
        "pattern": re.compile(r'(?i)input\s*\(\s*\)'),
        "description": "Use of built-in input() in Python 2 is dangerous (eval behavior).",
        "files": [".py"],
    },
    {
        "id": "B113",
        "name": "yaml_load_unsafe",
        "severity": "MEDIUM",
        "pattern": re.compile(r'yaml\.load\s*\([^,)]*\)'),
        "description": "yaml.load without Loader=yaml.SafeLoader can execute arbitrary code.",
        "files": [".py"],
    },
    {
        "id": "B114",
        "name": "assert_in_production",
        "severity": "LOW",
        "pattern": re.compile(r'^\s*assert\s+'),
        "description": "assert statements are removed when compiling to optimized bytecode.",
        "files": [".py"],
    },
]

# =============================================================================
# 2. SECRET DETECTION PATTERNS
# =============================================================================

SECRET_PATTERNS = [
    (re.compile(r'AKIA[0-9A-Z]{16}'), 'aws_access_key_id'),
    (re.compile(r'sk-[a-zA-Z0-9]{20,}'), 'openai_api_key'),
    (re.compile(r'ghp_[a-zA-Z0-9]{36}'), 'github_pat'),
    (re.compile(r'glpat-[a-zA-Z0-9\-]{20}'), 'gitlab_pat'),
    (re.compile(r'gho_[a-zA-Z0-9]{36}'), 'github_oauth'),
    (re.compile(r'ghu_[a-zA-Z0-9]{36}'), 'github_user_token'),
    (re.compile(r'ghs_[a-zA-Z0-9]{36}'), 'github_server_token'),
    (re.compile(r'dapi[a-f0-9]{32}'), 'databricks_token'),
    (re.compile(r'-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----'), 'private_key'),
    (re.compile(r'ya29\.[a-zA-Z0-9_\-]{50,}'), 'google_oauth'),
    (re.compile(r'basic [a-zA-Z0-9+/]{20,}={0,2}', re.IGNORECASE), 'basic_auth'),
    (re.compile(r'bearer [a-zA-Z0-9_\-\.]{20,}', re.IGNORECASE), 'bearer_token'),
]

# Values to ignore (placeholders, examples, defaults)
IGNORE_PATTERNS = [
    'change-in-production',
    'your-secret',
    'your-',
    'example',
    'placeholder',
    'default',
    'localhost',
    'inscode',
    'knowledge123',
    'neo4j123',
    'admin123',
    'minioadmin',
    'minioadmin123',
    'guest',
    'password',
    'secret',
    'token',
    'true',
    'false',
    'none',
    'null',
    'undefined',
    'http://',
    'https://',
]

# =============================================================================
# 3. FILE WALKER
# =============================================================================

def get_files(base_dir, extensions):
    skip_dirs = {'node_modules', '.git', '__pycache__', '.venv', 'venv', '.pytest_cache', '.mypy_cache', 'dist', 'build'}
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            if any(f.endswith(ext) for ext in extensions):
                yield Path(root) / f

# =============================================================================
# 4. SAST SCANNER
# =============================================================================

def run_sast():
    findings = []
    for rule in SAST_RULES:
        for fp in get_files(BASE_DIR / "backend" / "app", rule["files"]):
            try:
                content = fp.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            for m in rule["pattern"].finditer(content):
                line_num = content[:m.start()].count('\n') + 1
                line_content = content.splitlines()[line_num - 1].strip()
                # Skip false positives
                if any(ign in line_content.lower() for ign in IGNORE_PATTERNS):
                    continue
                # Skip comments
                if line_content.startswith('#') or line_content.startswith('//'):
                    continue
                findings.append({
                    "rule_id": rule["id"],
                    "rule_name": rule["name"],
                    "severity": rule["severity"],
                    "file": str(fp.relative_to(BASE_DIR)).replace('\\', '/'),
                    "line": line_num,
                    "column": m.start() - content.rfind('\n', 0, m.start()),
                    "message": rule["description"],
                    "snippet": line_content[:120],
                })
    return findings

# =============================================================================
# 5. SECRET SCANNER
# =============================================================================

def run_secret_scan():
    findings = []
    scan_files = list(get_files(BASE_DIR, ['.py', '.ts', '.tsx', '.js', '.yml', '.yaml', '.json', '.sh', '.env', '.env.example', '.md']))
    # Also scan config files
    scan_files += [BASE_DIR / 'docker-compose.yml']
    for fp in set(scan_files):
        if not fp.exists():
            continue
        try:
            content = fp.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        for pattern, secret_type in SECRET_PATTERNS:
            for m in pattern.finditer(content):
                line_num = content[:m.start()].count('\n') + 1
                snippet = m.group(0)
                if len(snippet) > 80:
                    snippet = snippet[:80] + '...'
                # Check ignore patterns
                lower_snippet = snippet.lower()
                if any(ign in lower_snippet for ign in IGNORE_PATTERNS):
                    continue
                findings.append({
                    "type": secret_type,
                    "file": str(fp.relative_to(BASE_DIR)).replace('\\', '/'),
                    "line": line_num,
                    "snippet": snippet,
                })
    return findings

# =============================================================================
# 6. DEPENDENCY VULNERABILITY SCAN (simple regex-based)
# =============================================================================

def run_dependency_scan():
    findings = []
    req_file = BASE_DIR / "backend" / "requirements.txt"
    if not req_file.exists():
        return findings

    # Known vulnerable package patterns (simplified check)
    vuln_patterns = {
        r'^requests[<]2\.20': ('CVE-2018-18074', 'HIGH', 'requests < 2.20.0 has session fixation vulnerability'),
        r'^flask[<]1\.0': ('CVE-2018-1000656', 'HIGH', 'Flask < 1.0 has JSON encoding vulnerability'),
        r'^django[<]2\.2': ('CVE-2019-19844', 'HIGH', 'Django < 2.2 has account takeover vulnerability'),
        r'^urllib3[<]1\.24': ('CVE-2019-11324', 'MEDIUM', 'urllib3 < 1.24 has certificate validation issue'),
        r'^jinja2[<]2\.10\.1': ('CVE-2019-10906', 'HIGH', 'Jinja2 < 2.10.1 has sandbox escape'),
        r'^pillow[<]8\.2': ('CVE-2021-34552', 'HIGH', 'Pillow < 8.2 has buffer overflow'),
        r'^fastapi[<]0\.109': ('CVE-2024-XXXX', 'MEDIUM', 'FastAPI < 0.109.2 recommended for security fixes'),
        r'^starlette[<]0\.36': ('CVE-2024-XXXX', 'MEDIUM', 'Starlette < 0.36.2 has path traversal fix'),
        r'^uvicorn[<]0\.27': ('CVE-2024-XXXX', 'LOW', 'Uvicorn < 0.27 has DoS fix'),
    }

    lines = req_file.read_text().splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        for pattern, (cve, severity, desc) in vuln_patterns.items():
            if re.search(pattern, line, re.IGNORECASE):
                findings.append({
                    "package": line,
                    "cve": cve,
                    "severity": severity,
                    "description": desc,
                })
    return findings

# =============================================================================
# 7. CONFIG SECURITY CHECKS
# =============================================================================

def run_config_checks():
    findings = []
    config_file = BASE_DIR / "backend" / "app" / "core" / "config.py"
    if config_file.exists():
        content = config_file.read_text()
        # Check for weak JWT defaults
        if 'jwt-secret-key-change-in-production' in content.lower() or 'your-secret-key-change-in-production' in content.lower():
            findings.append({
                "check": "weak_default_secret",
                "file": "backend/app/core/config.py",
                "severity": "HIGH",
                "message": "Default JWT/SECRET_KEY detected. Must be overridden in production.",
            })
        # Check for DEBUG default
        if re.search(r'DEBUG\s*:\s*bool\s*=\s*True', content):
            findings.append({
                "check": "debug_default_true",
                "file": "backend/app/core/config.py",
                "severity": "MEDIUM",
                "message": "DEBUG defaults to True. Should default to False for safety.",
            })

    env_file = BASE_DIR / ".env"
    if env_file.exists():
        content = env_file.read_text()
        # Check for default passwords in .env
        weak_passwords = ['knowledge123', 'neo4j123', 'admin123', 'minioadmin123', 'guest', 'inscode']
        for pw in weak_passwords:
            if pw in content:
                for i, line in enumerate(content.splitlines(), 1):
                    if pw in line:
                        findings.append({
                            "check": "weak_password_in_env",
                            "file": ".env",
                            "line": i,
                            "severity": "MEDIUM",
                            "message": f"Weak/default password '{pw}' found in .env file.",
                        })

    # Check docker-compose for default passwords
    dc_file = BASE_DIR / "docker-compose.yml"
    if dc_file.exists():
        content = dc_file.read_text()
        for pw in weak_passwords:
            if pw in content:
                for i, line in enumerate(content.splitlines(), 1):
                    if pw in line:
                        findings.append({
                            "check": "weak_password_in_docker_compose",
                            "file": "docker-compose.yml",
                            "line": i,
                            "severity": "MEDIUM",
                            "message": f"Weak/default password '{pw}' found in docker-compose.yml.",
                        })

    return findings

# =============================================================================
# 8. MAIN
# =============================================================================

def main():
    print("=" * 70)
    print(" Meatapivot Security Scanner")
    print(f" Started: {datetime.utcnow().isoformat()}")
    print("=" * 70)

    results = {
        "scan_time": datetime.utcnow().isoformat(),
        "project": "meatapivot",
        "sast": run_sast(),
        "secrets": run_secret_scan(),
        "dependencies": run_dependency_scan(),
        "config": run_config_checks(),
    }

    # Write JSON report
    report_path = REPORTS_DIR / f"security-scan-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2)

    # Print summary
    total = sum(len(v) for v in results.values() if isinstance(v, list))
    high = sum(1 for v in results.values() if isinstance(v, list) for item in v if item.get('severity') == 'HIGH')
    medium = sum(1 for v in results.values() if isinstance(v, list) for item in v if item.get('severity') == 'MEDIUM')
    low = sum(1 for v in results.values() if isinstance(v, list) for item in v if item.get('severity') == 'LOW')

    print(f"\n{'='*70}")
    print(" SCAN SUMMARY")
    print(f"{'='*70}")
    print(f"  SAST Findings:        {len(results['sast'])}")
    print(f"  Secret Findings:      {len(results['secrets'])}")
    print(f"  Dependency Issues:    {len(results['dependencies'])}")
    print(f"  Config Issues:        {len(results['config'])}")
    print(f"{'-'*70}")
    print(f"  Total: {total}  |  HIGH: {high}  |  MEDIUM: {medium}  |  LOW: {low}")
    print(f"{'='*70}")

    # Print details
    if results['sast']:
        print("\n[SAST FINDINGS]")
        for f in results['sast']:
            print(f"  [{f['severity']}] {f['file']}:{f['line']} {f['rule_name']}")
            print(f"    {f['message']}")
            print(f"    >> {f['snippet'][:80]}")

    if results['secrets']:
        print("\n[SECRET FINDINGS]")
        for f in results['secrets']:
            print(f"  {f['file']}:{f['line']} [{f['type']}] {f['snippet'][:60]}")

    if results['dependencies']:
        print("\n[DEPENDENCY ISSUES]")
        for f in results['dependencies']:
            print(f"  [{f['severity']}] {f['package']} - {f['cve']}")
            print(f"    {f['description']}")

    if results['config']:
        print("\n[CONFIG ISSUES]")
        for f in results['config']:
            line = f":{f.get('line','?')}" if 'line' in f else ""
            print(f"  [{f['severity']}] {f['file']}{line} - {f['check']}")
            print(f"    {f['message']}")

    print(f"\nFull report saved to: {report_path}")
    return results

if __name__ == "__main__":
    main()

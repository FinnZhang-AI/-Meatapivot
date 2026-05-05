# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | :white_check_mark: |
| < 2.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability within Meatapivot, please send an email to **security@meatapivot.io**.

Please include:
- A description of the vulnerability
- Steps to reproduce
- Possible impact
- Suggested fix (if any)

We will respond within 48 hours and aim to release a patch within 7 days for critical issues.

## Security Scanning

This project uses automated security scanning:

- **SAST**: Bandit / Semgrep for static analysis
- **Dependency Audit**: pip-audit / Safety for vulnerable packages
- **Secret Detection**: Custom scanner for hardcoded credentials

Run locally:
```bash
python scripts/security-scan.py
```

## Known Security Considerations

### 1. Default Credentials (Development Only)

The `docker-compose.yml` and `.env` files contain default passwords for local development:
- `knowledge123`, `neo4j123`, `admin123`, `minioadmin123`

**⚠️ These MUST be changed before deploying to production.**

### 2. DEBUG Mode

`DEBUG=True` is set by default in development. Always set `DEBUG=False` in production.

### 3. JWT Secret Keys

Default JWT secrets are provided for local development. In production, generate strong random keys:
```bash
openssl rand -hex 32
```

### 4. Cypher Query Injection

The `/knowledge-graph/query` endpoint accepts raw Cypher queries. In production:
- Restrict to read-only operations
- Use the Ontology layer's parameterized queries instead

### 5. Action Rule Expressions

Action rules use a sandboxed AST-based expression evaluator (`SafeExprEvaluator`). Arbitrary Python code execution is not allowed. For complex logic, use Function-backed Actions with the sandboxed subprocess executor.

## Security Hardening Checklist

Before production deployment:

- [ ] Change all default passwords in `.env`
- [ ] Set `DEBUG=false`
- [ ] Generate new `JWT_SECRET_KEY` and `SECRET_KEY`
- [ ] Enable HTTPS/TLS
- [ ] Configure CORS to specific origins only
- [ ] Restrict file upload types and sizes
- [ ] Enable rate limiting (Redis-backed)
- [ ] Set up audit log retention
- [ ] Run `python scripts/security-scan.py` and resolve all findings
- [ ] Review and harden Neo4j / PostgreSQL / MinIO access controls

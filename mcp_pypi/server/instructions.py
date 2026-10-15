"""Server-level instructions sent to the model on connect."""

INSTRUCTIONS = """\
PyPI package intelligence: search, inspect, vet and audit Python dependencies.

Choosing a tool:
- Finding a package: search_packages, then get_package for details.
- Before suggesting or adding dependencies: check_packages (existence,
  latest version, summary) on every candidate.
- Known vulnerabilities for specific versions: check_vulnerabilities.
- Auditing a repository: audit_project (reads its dependency files).
- Auditing a virtual environment: scan_installed_packages.
- All tools are read-only lookups; they never modify files or environments.

Dependency file authority (highest first):
1. pyproject.toml is the primary source of truth for dependencies.
2. requirements*.txt are secondary or generated; treat them as derived.
3. setup.py and setup.cfg are legacy; read them but do not prefer them.
When changing dependencies, update the primary file first and keep
constraints consistent across the other files.

Errors are returned as tool errors with a short actionable message; names
that do not exist come with a "did you mean" hint when one is close.
"""

"""Security audit tools for PyPI MCP Server.

Contains tools for comprehensive security auditing of Python projects,
including quick security checks and detailed security reports.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from mcp.types import ToolAnnotations

from mcp_pypi.utils.common.validation import make_error_response, validate_file_path

if TYPE_CHECKING:
    from mcp_pypi.server import PyPIMCPServer

logger = logging.getLogger("mcp-pypi.server")

# Safety limits for glob operations
MAX_GLOB_FILES = 100
MAX_GLOB_DEPTH = 5


def safe_glob(root: Path, pattern: str, max_files: int = MAX_GLOB_FILES, max_depth: int = MAX_GLOB_DEPTH) -> list:
    """
    Safely glob files with limits to prevent resource exhaustion.

    Args:
        root: Root directory to search from
        pattern: Glob pattern to match
        max_files: Maximum number of files to return (default: 100)
        max_depth: Maximum directory depth to search (default: 5)

    Returns:
        List of matching Path objects, limited by max_files
    """
    results = []
    root_depth = len(root.parts)

    try:
        for path in root.glob(pattern):
            # Check depth limit
            path_depth = len(path.parts) - root_depth
            if path_depth > max_depth:
                continue

            results.append(path)

            # Check file count limit
            if len(results) >= max_files:
                logger.warning(
                    f"Glob limit reached: found {max_files} files for pattern '{pattern}'. "
                    f"Additional matches may exist."
                )
                break
    except (PermissionError, OSError) as e:
        logger.warning(f"Error during glob operation: {e}")

    return results


def register_audit_tools(server: "PyPIMCPServer") -> None:
    """Register security audit tools with the MCP server.

    Args:
        server: The PyPIMCPServer instance to register tools with.
    """
    from mcp_pypi.server.tools.file_tools import (
        _check_requirements_txt_impl,
        _check_pyproject_toml_impl,
    )
    from mcp_pypi.server.tools.vulnerability_tools import (
        register_vulnerability_tools,
    )

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        tags={"security", "quick"},
    )
    async def quick_security_check(
        project_path: Optional[str] = None,
        fail_on_critical: bool = True,
        fail_on_high: bool = True,
    ) -> Dict[str, Any]:
        """Quick security check with pass/fail status.

        Perfect for CI/CD pipelines and pre-commit hooks. Returns a simple
        pass/fail status based on vulnerability thresholds.

        Args:
            project_path: Absolute path to project root directory
                        (e.g., /home/user/myproject)
                        Auto-detects current directory if not provided
            fail_on_critical: Fail if any CRITICAL vulnerabilities (default: True)
            fail_on_high: Fail if any HIGH vulnerabilities (default: True)

        Returns:
            Dictionary with:
            - passed: Boolean indicating if security check passed
            - status: Human-readable status (PASSED, FAILED)
            - reason: Why it failed (if applicable)
            - summary: Brief vulnerability count
            - security_score: 0-100 score
        """
        try:
            audit_result = await security_audit_project(
                project_path=project_path,
                check_files=True,
                check_installed=False,
                check_transitive=False,
                max_depth=1,
            )

            if audit_result.get("error"):
                return {
                    "passed": False,
                    "status": "ERROR",
                    "reason": audit_result["error"],
                    "summary": "Audit failed",
                    "security_score": 0,
                }

            severity = audit_result.get("severity_breakdown", {})
            critical = severity.get("critical", 0)
            high = severity.get("high", 0)
            total = audit_result.get("total_vulnerabilities", 0)
            score = audit_result.get("security_score", 0)

            passed = True
            reason = ""

            if fail_on_critical and critical > 0:
                passed = False
                reason = f"Found {critical} CRITICAL vulnerabilities"
            elif fail_on_high and high > 0:
                passed = False
                reason = f"Found {high} HIGH vulnerabilities"

            return {
                "passed": passed,
                "status": "PASSED" if passed else "FAILED",
                "reason": reason if not passed else "No critical issues found",
                "summary": f"{total} total vulnerabilities ({critical} critical, {high} high)",
                "security_score": score,
                "details": {
                    "critical": critical,
                    "high": high,
                    "medium": severity.get("medium", 0),
                    "low": severity.get("low", 0),
                },
            }

        except Exception as e:
            return {
                "passed": False,
                "status": "ERROR",
                "reason": str(e),
                "summary": "Check failed",
                "security_score": 0,
            }

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True),
        tags={"security", "report"},
    )
    async def get_security_report(
        project_path: Optional[str] = None,
        check_files: bool = True,
        check_installed: bool = True,
        check_transitive: bool = True,
        max_depth: int = 2,
    ) -> str:
        """Get a beautiful, color-coded security report for your Python project.

        Returns a formatted report with:
        - Color-coded severity levels (RED=Critical, ORANGE=High, etc.)
        - ASCII tables showing vulnerability distribution
        - Visual progress bars for each severity level
        - Prioritized fix recommendations with clear actions
        - Security score (0-100) with color indicators

        Perfect for:
        - Quick security assessments
        - CI/CD pipeline reports
        - Team security reviews
        - Management presentations

        The report includes executive summary, vulnerability breakdown,
        priority fixes, and actionable remediation steps.

        Args:
            project_path: Absolute path to project root directory
                        (e.g., /home/user/myproject)
                        Auto-detects current directory if not provided
            check_files: Analyze dependency files (default: True)
            check_installed: Scan virtual environments (default: True)
            check_transitive: Deep dependency analysis (default: True)
            max_depth: Dependency tree depth (default: 2)

        Returns:
            Formatted security report with colors and tables
        """
        audit_result = await security_audit_project(
            project_path=project_path,
            check_files=check_files,
            check_installed=check_installed,
            check_transitive=check_transitive,
            max_depth=max_depth,
        )

        if audit_result.get("error"):
            return f"Security audit failed: {audit_result['error']}"

        return audit_result.get("formatted_report", "No report generated")

    @server.mcp_server.tool(
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        tags={"security", "audit"},
    )
    async def security_audit_project(
        project_path: Optional[str] = None,
        check_files: bool = True,
        check_installed: bool = True,
        check_transitive: bool = True,
        max_depth: int = 2,
    ) -> Dict[str, Any]:
        """Comprehensive security audit of an entire Python project.

        The most thorough security check available - analyzes every aspect of your
        project's dependencies to provide a complete security assessment with actionable insights.

        Unified analysis includes:
        - All dependency files:
          - requirements*.txt files
          - pyproject.toml (PEP 517/518)
          - setup.py / setup.cfg
          - Pipfile / Pipfile.lock
          - poetry.lock
          - environment.yml / conda.yml
          - constraints.txt
        - Installed packages in detected environments
        - Transitive dependencies (dependencies of dependencies)
        - Version constraints and compatibility
        - Prioritized remediation recommendations

        Perfect for critical checkpoints:
        - Pre-deployment security verification
        - Pull request security reviews
        - Periodic security audits
        - Compliance documentation

        Args:
            project_path: Absolute path to project root directory
                        (e.g., /home/user/myproject)
                        Auto-detects current directory if not provided
            check_files: Analyze dependency files (default: True)
            check_installed: Scan virtual environments (default: True)
            check_transitive: Deep dependency analysis (default: True)
            max_depth: Dependency tree depth (default: 2)

        Returns:
            Executive summary with:
            - overall_risk_level: Your security posture (CRITICAL/HIGH/MEDIUM/LOW/SECURE)
            - security_score: 0-100 rating for quick assessment
            - priority_fixes: What to fix first for maximum impact
            - remediation_plan: Step-by-step security improvements
            - estimated_fix_time: Realistic time to resolve issues

        Pro tip: Run monthly or before major releases. The security score helps track
        improvement over time. Export results for compliance records.

        POST-AUDIT ACTION CHECKLIST:
        If vulnerabilities are found, you MUST follow this ORDER:
        1. UPDATE pyproject.toml FIRST (if it exists - it's the primary source)
        2. TRICKLE DOWN changes to requirements.txt, setup.py, setup.cfg
        3. VERIFY all files have IDENTICAL version constraints
        4. Test that updates don't break functionality
        5. Commit with message: "chore: Update dependencies for security (all files)"

        CORRECT UPDATE ORDER:
        pyproject.toml (PRIMARY) -> requirements.txt -> setup.py -> setup.cfg

        COMMON MISTAKES TO AVOID:
        - Only updating requirements.txt (wrong - it's secondary!)
        - Having different versions in different files (breaks consistency)
        - Not checking if pyproject.toml exists (it's the modern standard)
        """
        try:
            if not project_path:
                project_path = os.getcwd()

            # Validate project path for security (prevent path traversal attacks)
            is_valid, error_msg = validate_file_path(project_path)
            if not is_valid:
                return make_error_response(
                    error_msg or "Invalid project path", "invalid_path"
                )

            project_root = Path(project_path)

            results: Dict[str, Any] = {
                "project_path": str(project_root),
                "scan_timestamp": datetime.now().isoformat(),
                "checks_performed": [],
                "vulnerabilities_by_source": {},
                "all_vulnerable_packages": {},
                "total_vulnerabilities": 0,
                "severity_breakdown": {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                },
            }

            if check_files:
                req_files = safe_glob(project_root, "**/requirements*.txt")
                for req_file in req_files:
                    results["checks_performed"].append(
                        f"requirements.txt: {req_file.name}"
                    )
                    req_result = await _check_requirements_txt_impl(
                        server, str(req_file)
                    )

                    if not req_result.get("error"):
                        vulns = []
                        all_packages = req_result.get("outdated", []) + req_result.get(
                            "up_to_date", []
                        )
                        for req in all_packages:
                            pkg_name = req.get("package", "")
                            current_version = req.get("current_version", "")
                            if pkg_name and current_version:
                                vuln_check = await server.client.check_vulnerabilities(
                                    pkg_name, current_version
                                )
                                logger.debug(
                                    f"Checking {pkg_name}=={current_version}: vulnerable={vuln_check.get('vulnerable')}, count={vuln_check.get('total_vulnerabilities', 0)}"
                                )
                                if vuln_check.get("vulnerable"):
                                    vulns.append(
                                        {
                                            "package": pkg_name,
                                            "version": current_version,
                                            "vulnerabilities": vuln_check.get(
                                                "total_vulnerabilities", 0
                                            ),
                                            "critical": vuln_check.get(
                                                "critical_count", 0
                                            ),
                                            "high": vuln_check.get("high_count", 0),
                                        }
                                    )

                                    if pkg_name not in results["all_vulnerable_packages"]:
                                        results["all_vulnerable_packages"][pkg_name] = {
                                            "versions_affected": set(),
                                            "sources": [],
                                            "max_severity": "low",
                                        }
                                    results["all_vulnerable_packages"][pkg_name][
                                        "versions_affected"
                                    ].add(current_version)
                                    results["all_vulnerable_packages"][pkg_name][
                                        "sources"
                                    ].append(req_file.name)

                        results["vulnerabilities_by_source"][req_file.name] = vulns

            if check_files:
                pyproject_files = safe_glob(project_root, "**/pyproject.toml")
                for pyproject in pyproject_files:
                    results["checks_performed"].append(
                        f"pyproject.toml: {pyproject.name}"
                    )
                    pyp_result = await _check_pyproject_toml_impl(
                        server, str(pyproject)
                    )

                    if not pyp_result.get("error"):
                        vulns = []
                        for req in pyp_result.get("requirements", []):
                            pkg_name = req.get("package", "")
                            current_version = req.get("current_version", "")
                            if pkg_name and current_version:
                                vuln_check = await server.client.check_vulnerabilities(
                                    pkg_name, current_version
                                )
                                logger.debug(
                                    f"Checking {pkg_name}=={current_version}: vulnerable={vuln_check.get('vulnerable')}, count={vuln_check.get('total_vulnerabilities', 0)}"
                                )
                                if vuln_check.get("vulnerable"):
                                    vulns.append(
                                        {
                                            "package": pkg_name,
                                            "version": current_version,
                                            "vulnerabilities": vuln_check.get(
                                                "total_vulnerabilities", 0
                                            ),
                                            "critical": vuln_check.get(
                                                "critical_count", 0
                                            ),
                                            "high": vuln_check.get("high_count", 0),
                                        }
                                    )

                                    if pkg_name not in results["all_vulnerable_packages"]:
                                        results["all_vulnerable_packages"][pkg_name] = {
                                            "versions_affected": set(),
                                            "sources": [],
                                            "max_severity": "low",
                                        }
                                    results["all_vulnerable_packages"][pkg_name][
                                        "versions_affected"
                                    ].add(current_version)
                                    results["all_vulnerable_packages"][pkg_name][
                                        "sources"
                                    ].append("pyproject.toml")

                        results["vulnerabilities_by_source"]["pyproject.toml"] = vulns

            if check_files:
                setup_py_files = safe_glob(project_root, "**/setup.py")
                for setup_file in setup_py_files:
                    results["checks_performed"].append(f"setup.py: {setup_file.name}")
                    vulns = await server._check_setup_py(setup_file, results)
                    if vulns:
                        results["vulnerabilities_by_source"][
                            f"setup.py:{setup_file.name}"
                        ] = vulns

                setup_cfg_files = safe_glob(project_root, "**/setup.cfg")
                for setup_cfg in setup_cfg_files:
                    results["checks_performed"].append(f"setup.cfg: {setup_cfg.name}")
                    vulns = await server._check_setup_cfg(setup_cfg, results)
                    if vulns:
                        results["vulnerabilities_by_source"][
                            f"setup.cfg:{setup_cfg.name}"
                        ] = vulns

            if check_files:
                pipfiles = safe_glob(project_root, "**/Pipfile")
                for pipfile in pipfiles:
                    results["checks_performed"].append(f"Pipfile: {pipfile.name}")
                    vulns = await server._check_pipfile(pipfile, results)
                    if vulns:
                        results["vulnerabilities_by_source"][
                            f"Pipfile:{pipfile.name}"
                        ] = vulns

                pipfile_locks = safe_glob(project_root, "**/Pipfile.lock")
                for pipfile_lock in pipfile_locks:
                    results["checks_performed"].append(
                        f"Pipfile.lock: {pipfile_lock.name}"
                    )
                    vulns = await server._check_pipfile_lock(pipfile_lock, results)
                    if vulns:
                        results["vulnerabilities_by_source"][
                            f"Pipfile.lock:{pipfile_lock.name}"
                        ] = vulns

            if check_files:
                poetry_locks = safe_glob(project_root, "**/poetry.lock")
                for poetry_lock in poetry_locks:
                    results["checks_performed"].append(
                        f"poetry.lock: {poetry_lock.name}"
                    )
                    vulns = await server._check_poetry_lock(poetry_lock, results)
                    if vulns:
                        results["vulnerabilities_by_source"][
                            f"poetry.lock:{poetry_lock.name}"
                        ] = vulns

            if check_files:
                conda_files = (
                    safe_glob(project_root, "**/environment.yml")
                    + safe_glob(project_root, "**/environment.yaml")
                    + safe_glob(project_root, "**/conda.yml")
                    + safe_glob(project_root, "**/conda.yaml")
                )
                for conda_file in conda_files:
                    results["checks_performed"].append(f"conda: {conda_file.name}")
                    vulns = await server._check_conda_file(conda_file, results)
                    if vulns:
                        results["vulnerabilities_by_source"][
                            f"conda:{conda_file.name}"
                        ] = vulns

            if check_files:
                constraints_files = safe_glob(project_root, "**/constraints.txt")
                for constraints_file in constraints_files:
                    results["checks_performed"].append(
                        f"constraints.txt: {constraints_file.name}"
                    )
                    req_result = await _check_requirements_txt_impl(
                        server, str(constraints_file)
                    )
                    if not req_result.get("error"):
                        vulns = []
                        all_packages = req_result.get("outdated", []) + req_result.get(
                            "up_to_date", []
                        )
                        for req in all_packages:
                            pkg_name = req.get("package", "")
                            current_version = req.get("current_version", "")
                            if pkg_name and current_version:
                                vuln_check = await server.client.check_vulnerabilities(
                                    pkg_name, current_version
                                )
                                logger.debug(
                                    f"Checking {pkg_name}=={current_version}: vulnerable={vuln_check.get('vulnerable')}, count={vuln_check.get('total_vulnerabilities', 0)}"
                                )
                                if vuln_check.get("vulnerable"):
                                    vulns.append(
                                        {
                                            "package": pkg_name,
                                            "version": current_version,
                                            "vulnerabilities": vuln_check.get(
                                                "total_vulnerabilities", 0
                                            ),
                                            "critical": vuln_check.get(
                                                "critical_count", 0
                                            ),
                                            "high": vuln_check.get("high_count", 0),
                                        }
                                    )

                                    if pkg_name not in results["all_vulnerable_packages"]:
                                        results["all_vulnerable_packages"][pkg_name] = {
                                            "versions_affected": set(),
                                            "sources": [],
                                            "max_severity": "low",
                                        }
                                    results["all_vulnerable_packages"][pkg_name][
                                        "versions_affected"
                                    ].add(current_version)
                                    results["all_vulnerable_packages"][pkg_name][
                                        "sources"
                                    ].append(constraints_file.name)

                        if vulns:
                            results["vulnerabilities_by_source"][
                                constraints_file.name
                            ] = vulns

            if check_installed:
                from mcp_pypi.server.tools.vulnerability_tools import (
                    register_vulnerability_tools,
                )

                results["checks_performed"].append("installed packages")

                env_result = await _scan_installed_packages_impl(
                    server, output_format="detailed"
                )

                if not env_result.get("error"):
                    results["installed_scan"] = {
                        "environment": env_result.get("environment_type"),
                        "total_packages": env_result.get("total_packages"),
                        "vulnerable_count": len(
                            env_result.get("vulnerable_packages", [])
                        ),
                        "vulnerabilities": env_result.get("vulnerability_summary"),
                    }

                    for vuln_pkg in env_result.get("vulnerable_packages", []):
                        pkg_name = vuln_pkg["package"]
                        if pkg_name not in results["all_vulnerable_packages"]:
                            results["all_vulnerable_packages"][pkg_name] = {
                                "versions_affected": set(),
                                "sources": [],
                                "max_severity": "low",
                            }
                        results["all_vulnerable_packages"][pkg_name][
                            "versions_affected"
                        ].add(vuln_pkg["installed_version"])
                        results["all_vulnerable_packages"][pkg_name]["sources"].append(
                            "installed"
                        )

            if check_transitive and results["all_vulnerable_packages"]:
                results["checks_performed"].append("transitive dependencies")
                top_packages = list(results["all_vulnerable_packages"].keys())[:3]
                transitive_vulns = {}

                for pkg in top_packages:
                    trans_result = await _scan_dependency_vulnerabilities_impl(
                        server, pkg, max_depth=max_depth
                    )
                    if not trans_result.get("error"):
                        transitive_vulns[pkg] = trans_result.get(
                            "vulnerable_packages", []
                        )

                results["transitive_scan"] = transitive_vulns

            total_critical = 0
            total_high = 0
            total_medium = 0
            total_low = 0

            for source, vulns in results["vulnerabilities_by_source"].items():
                for v in vulns:
                    total_critical += v.get("critical", 0)
                    total_high += v.get("high", 0)
                    other_vulns = (
                        v.get("vulnerabilities", 0)
                        - v.get("critical", 0)
                        - v.get("high", 0)
                    )
                    total_medium += other_vulns // 2
                    total_low += other_vulns - (other_vulns // 2)

            if "installed_scan" in results:
                inst_vulns = results["installed_scan"]["vulnerabilities"]
                total_critical += inst_vulns.get("critical", 0)
                total_high += inst_vulns.get("high", 0)
                total_medium += inst_vulns.get("medium", 0)
                total_low += inst_vulns.get("low", 0)

            results["severity_breakdown"] = {
                "critical": total_critical,
                "high": total_high,
                "medium": total_medium,
                "low": total_low,
            }
            results["total_vulnerabilities"] = sum(results["severity_breakdown"].values())

            if total_critical > 0:
                risk_level = "CRITICAL"
            elif total_high > 5:
                risk_level = "HIGH"
            elif total_high > 0 or total_medium > 10:
                risk_level = "MEDIUM"
            elif results["total_vulnerabilities"] > 0:
                risk_level = "LOW"
            else:
                risk_level = "SECURE"

            security_score = 100
            security_score -= total_critical * 20
            security_score -= total_high * 10
            security_score -= total_medium * 3
            security_score -= total_low * 1
            security_score = max(0, security_score)

            remediation_steps = []
            if total_critical > 0:
                remediation_steps.append(
                    "1. IMMEDIATELY update packages with CRITICAL vulnerabilities"
                )
            if total_high > 0:
                remediation_steps.append(
                    "2. Update packages with HIGH vulnerabilities within 24 hours"
                )
            if total_medium > 0:
                remediation_steps.append(
                    "3. Plan updates for MEDIUM vulnerabilities this week"
                )
            if total_low > 0:
                remediation_steps.append(
                    "4. Review LOW vulnerabilities in next maintenance window"
                )

            fix_time_minutes = (
                (total_critical * 15)
                + (total_high * 10)
                + (total_medium * 5)
                + (total_low * 2)
            )
            if fix_time_minutes < 60:
                estimated_fix_time = f"{fix_time_minutes} minutes"
            else:
                estimated_fix_time = (
                    f"{fix_time_minutes // 60} hours {fix_time_minutes % 60} minutes"
                )

            priority_fixes = []
            for pkg_name, pkg_info in results["all_vulnerable_packages"].items():
                pkg_vulns = {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                    "total": 0,
                }
                for source, vulns in results["vulnerabilities_by_source"].items():
                    for v in vulns:
                        if v.get("package") == pkg_name:
                            pkg_vulns["critical"] += v.get("critical", 0)
                            pkg_vulns["high"] += v.get("high", 0)
                            other = (
                                v.get("vulnerabilities", 0)
                                - v.get("critical", 0)
                                - v.get("high", 0)
                            )
                            pkg_vulns["medium"] += other // 2
                            pkg_vulns["low"] += other - (other // 2)
                            pkg_vulns["total"] += v.get("vulnerabilities", 0)

                pkg_info["versions_affected"] = list(pkg_info["versions_affected"])
                priority_fixes.append(
                    {
                        "package": pkg_name,
                        "versions": pkg_info["versions_affected"],
                        "found_in": pkg_info["sources"],
                        "total_vulnerabilities": pkg_vulns["total"],
                        "critical": pkg_vulns["critical"],
                        "high": pkg_vulns["high"],
                        "medium": pkg_vulns["medium"],
                        "low": pkg_vulns["low"],
                    }
                )

            priority_fixes.sort(
                key=lambda x: (
                    x["critical"] * 1000
                    + x["high"] * 100
                    + x["medium"] * 10
                    + x["low"]
                    + len(x["found_in"]) * 0.1
                ),
                reverse=True,
            )

            # Convert all sets to lists for JSON serialization
            # This ensures any remaining sets in all_vulnerable_packages are converted
            for pkg_name, pkg_info in results["all_vulnerable_packages"].items():
                if isinstance(pkg_info.get("versions_affected"), set):
                    pkg_info["versions_affected"] = list(pkg_info["versions_affected"])

            audit_data = {
                "overall_risk_level": risk_level,
                "security_score": security_score,
                "total_vulnerabilities": results["total_vulnerabilities"],
                "severity_breakdown": results["severity_breakdown"],
                "checks_performed": results["checks_performed"],
                "priority_fixes": priority_fixes[:10],
                "vulnerabilities_by_source": results["vulnerabilities_by_source"],
                "installed_environment": results.get("installed_scan", {}),
                "estimated_fix_time": estimated_fix_time,
                "remediation_plan": remediation_steps,
                "recommendation": (
                    f"{risk_level}: Found {results['total_vulnerabilities']} vulnerabilities across your project. "
                    f"Security Score: {security_score}/100. "
                    f"Estimated fix time: {estimated_fix_time}. "
                    + (
                        "URGENT ACTION REQUIRED!"
                        if total_critical > 0
                        else "Please review and update."
                    )
                ),
                "scan_timestamp": results["scan_timestamp"],
                "project_path": str(project_root),
            }

            audit_data["formatted_report"] = server._format_security_report(audit_data)

            return audit_data

        except Exception as e:
            logger.error(f"Error in project security audit: {e}")
            return make_error_response(
                f"Security audit failed: {str(e)}", "security_audit_error"
            )


async def _scan_installed_packages_impl(
    server: "PyPIMCPServer",
    environment_path: Optional[str] = None,
    include_system: bool = False,
    output_format: str = "summary",
) -> Dict[str, Any]:
    """Internal implementation of scan_installed_packages for use by audit tools."""
    import json
    import subprocess
    from datetime import datetime
    from pathlib import Path

    try:
        if not environment_path:
            for venv_name in [".venv", "venv", "env", ".env", "virtualenv"]:
                venv_path = Path.cwd() / venv_name
                if venv_path.exists() and (venv_path / "bin" / "pip").exists():
                    environment_path = str(venv_path)
                    break
                elif (
                    venv_path.exists()
                    and (venv_path / "Scripts" / "pip.exe").exists()
                ):
                    environment_path = str(venv_path)
                    break

        if environment_path:
            if os.name == "nt":
                pip_cmd = os.path.join(environment_path, "Scripts", "pip.exe")
            else:
                pip_cmd = os.path.join(environment_path, "bin", "pip")
            env_type = "virtualenv"

            conda_meta = Path(environment_path) / "conda-meta"
            if conda_meta.exists():
                env_type = "conda"
        else:
            pip_cmd = "pip"
            env_type = "system"

        try:
            result = subprocess.run(
                [pip_cmd, "list", "--format=json"],
                capture_output=True,
                text=True,
                check=True,
            )
            installed_packages = json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            return {
                "error": {
                    "message": f"Failed to get package list: {str(e)}",
                    "code": "pip_list_error",
                }
            }

        vulnerable_packages = []
        total_packages = len(installed_packages)
        critical_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0

        for pkg in installed_packages:
            pkg_name = pkg["name"]
            pkg_version = pkg["version"]

            vuln_result = await server.client.check_vulnerabilities(
                pkg_name, pkg_version
            )

            if vuln_result.get("vulnerable", False):
                vuln_count = vuln_result.get("total_vulnerabilities", 0)
                critical = vuln_result.get("critical_count", 0)
                high = vuln_result.get("high_count", 0)
                medium = vuln_result.get("medium_count", 0)
                low = vuln_result.get("low_count", 0)

                critical_count += critical
                high_count += high
                medium_count += medium
                low_count += low

                latest_version_info = await server.client.get_latest_version(pkg_name)
                latest_version = latest_version_info.get("version", "unknown")

                vulnerable_packages.append(
                    {
                        "package": pkg_name,
                        "installed_version": pkg_version,
                        "latest_version": latest_version,
                        "vulnerabilities": vuln_count,
                        "critical": critical,
                        "high": high,
                        "medium": medium,
                        "low": low,
                        "summary": (
                            vuln_result.get("vulnerabilities", [])[0].get("summary", "")
                            if vuln_result.get("vulnerabilities")
                            else "Multiple vulnerabilities found"
                        ),
                    }
                )

        vulnerable_packages.sort(
            key=lambda p: (
                p["critical"],
                p["high"],
                p["medium"],
                p["vulnerabilities"],
            ),
            reverse=True,
        )

        total_vulnerabilities = critical_count + high_count + medium_count + low_count

        return {
            "environment_type": env_type,
            "environment_path": environment_path or "system",
            "total_packages": total_packages,
            "vulnerable_packages": (
                vulnerable_packages
                if output_format == "detailed"
                else len(vulnerable_packages)
            ),
            "vulnerability_summary": {
                "total": total_vulnerabilities,
                "critical": critical_count,
                "high": high_count,
                "medium": medium_count,
                "low": low_count,
            },
            "all_clear": len(vulnerable_packages) == 0,
        }

    except Exception as e:
        return make_error_response(
            f"Error scanning environment: {str(e)}", "environment_scan_error"
        )


async def _scan_dependency_vulnerabilities_impl(
    server: "PyPIMCPServer",
    package_name: str,
    version: Optional[str] = None,
    max_depth: int = 2,
    include_dev: bool = False,
) -> Dict[str, Any]:
    """Internal implementation of scan_dependency_vulnerabilities for use by audit tools."""
    from typing import cast

    try:
        tree_result = await server.client.get_dependency_tree(
            package_name, version, max_depth
        )
        if "error" in tree_result:
            return cast(Dict[str, Any], tree_result)

        packages_to_scan: set = set()
        vulnerable_packages = []
        total_vulnerabilities = 0
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        def extract_packages(node: Dict[str, Any], depth: int = 0) -> None:
            if depth > max_depth:
                return

            pkg_name = node.get("name", "")
            pkg_version = node.get("version", "")
            if pkg_name:
                packages_to_scan.add((pkg_name, pkg_version))

            for dep in node.get("dependencies", []):
                extract_packages(dep, depth + 1)

            if include_dev:
                for dep in node.get("dev_dependencies", []):
                    extract_packages(dep, depth + 1)

        extract_packages(tree_result)

        packages_list = [
            (pkg_name, pkg_version or None)
            for pkg_name, pkg_version in packages_to_scan
        ]

        batch_result = await server.client.check_vulnerabilities_batch(
            packages_list, batch_size=100
        )

        for pkg_key, vuln_result in batch_result.get("results", {}).items():
            if vuln_result.get("vulnerable", False):
                vuln_count = vuln_result.get("total_vulnerabilities", 0)
                total_vulnerabilities += vuln_count

                severity_counts["critical"] += vuln_result.get("critical_count", 0)
                severity_counts["high"] += vuln_result.get("high_count", 0)
                severity_counts["medium"] += vuln_result.get("medium_count", 0)
                severity_counts["low"] += vuln_result.get("low_count", 0)

                pkg_name_extracted = vuln_result.get("package", pkg_key.split(":")[0])
                pkg_version_extracted = vuln_result.get("version", "latest")

                vulnerable_packages.append(
                    {
                        "package": pkg_name_extracted,
                        "version": pkg_version_extracted,
                        "vulnerabilities": vuln_count,
                        "critical": vuln_result.get("critical_count", 0),
                        "high": vuln_result.get("high_count", 0),
                    }
                )

        vulnerable_packages.sort(
            key=lambda p: (p["critical"], p["high"], p["vulnerabilities"]),
            reverse=True,
        )

        return {
            "package": f"{package_name} {version or 'latest'}",
            "total_packages_scanned": len(packages_to_scan),
            "vulnerable_packages": vulnerable_packages,
            "total_vulnerabilities": total_vulnerabilities,
            "severity_summary": severity_counts,
            "all_clear": len(vulnerable_packages) == 0,
        }

    except Exception as e:
        return make_error_response(
            f"Error scanning dependencies: {str(e)}", "dependency_scan_error"
        )

"""Helper methods for PyPI MCP Server.

Contains helper methods for parsing various dependency file formats
and formatting security reports.
"""

from __future__ import annotations

import configparser
import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from mcp_pypi.server import PyPIMCPServer

logger = logging.getLogger("mcp-pypi.server")


async def check_setup_py(
    server: "PyPIMCPServer", setup_file: Path, results: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Parse setup.py for dependencies.

    Args:
        server: The PyPIMCPServer instance for API calls.
        setup_file: Path to setup.py file.
        results: Results dictionary to update with vulnerable packages.

    Returns:
        List of vulnerability dictionaries found.
    """
    vulns = []
    try:
        content = setup_file.read_text()
        install_requires_match = re.search(
            r"install_requires\s*=\s*\[(.*?)\]", content, re.DOTALL
        )
        if install_requires_match:
            requires_text = install_requires_match.group(1)
            requirements = re.findall(r'["\']([^"\']+)["\']', requires_text)

            for req in requirements:
                parts = re.split(r"[<>=!~]", req)
                pkg_name = parts[0].strip()

                if pkg_name:
                    latest_info = await server.client.get_latest_version(pkg_name)
                    if latest_info and not latest_info.get("error"):
                        version = latest_info.get("version")
                        vuln_check = await server.client.check_vulnerabilities(
                            pkg_name, version
                        )
                        if vuln_check.get("vulnerable"):
                            vulns.append(
                                {
                                    "package": pkg_name,
                                    "version": version,
                                    "vulnerabilities": vuln_check.get(
                                        "total_vulnerabilities", 0
                                    ),
                                    "critical": vuln_check.get("critical_count", 0),
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
                            ].add(version)
                            results["all_vulnerable_packages"][pkg_name][
                                "sources"
                            ].append(f"setup.py:{setup_file.name}")
    except Exception as e:
        logger.warning(f"Error parsing setup.py: {e}")

    return vulns


async def check_setup_cfg(
    server: "PyPIMCPServer", setup_cfg: Path, results: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Parse setup.cfg for dependencies.

    Args:
        server: The PyPIMCPServer instance for API calls.
        setup_cfg: Path to setup.cfg file.
        results: Results dictionary to update with vulnerable packages.

    Returns:
        List of vulnerability dictionaries found.
    """
    vulns = []
    try:
        config = configparser.ConfigParser()
        config.read(setup_cfg)

        if "options" in config and "install_requires" in config["options"]:
            requirements = config["options"]["install_requires"].strip().split("\n")

            for req in requirements:
                req = req.strip()
                if req:
                    parts = re.split(r"[<>=!~]", req)
                    pkg_name = parts[0].strip()

                    if pkg_name:
                        latest_info = await server.client.get_latest_version(pkg_name)
                        if latest_info and not latest_info.get("error"):
                            version = latest_info.get("version")
                            vuln_check = await server.client.check_vulnerabilities(
                                pkg_name, version
                            )
                            if vuln_check.get("vulnerable"):
                                vulns.append(
                                    {
                                        "package": pkg_name,
                                        "version": version,
                                        "vulnerabilities": vuln_check.get(
                                            "total_vulnerabilities", 0
                                        ),
                                        "critical": vuln_check.get("critical_count", 0),
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
                                ].add(version)
                                results["all_vulnerable_packages"][pkg_name][
                                    "sources"
                                ].append(f"setup.cfg:{setup_cfg.name}")
    except Exception as e:
        logger.warning(f"Error parsing setup.cfg: {e}")

    return vulns


async def check_pipfile(
    server: "PyPIMCPServer", pipfile: Path, results: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Parse Pipfile for dependencies.

    Args:
        server: The PyPIMCPServer instance for API calls.
        pipfile: Path to Pipfile.
        results: Results dictionary to update with vulnerable packages.

    Returns:
        List of vulnerability dictionaries found.
    """
    vulns = []
    try:
        import toml

        data = toml.load(pipfile)

        for section in ["packages", "dev-packages"]:
            if section in data:
                for pkg_name, version_spec in data[section].items():
                    if pkg_name == "python_version":
                        continue

                    if isinstance(version_spec, dict) and "version" in version_spec:
                        version_spec = version_spec["version"]

                    latest_info = await server.client.get_latest_version(pkg_name)
                    if latest_info and not latest_info.get("error"):
                        version = latest_info.get("version")
                        vuln_check = await server.client.check_vulnerabilities(
                            pkg_name, version
                        )
                        if vuln_check.get("vulnerable"):
                            vulns.append(
                                {
                                    "package": pkg_name,
                                    "version": version,
                                    "vulnerabilities": vuln_check.get(
                                        "total_vulnerabilities", 0
                                    ),
                                    "critical": vuln_check.get("critical_count", 0),
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
                            ].add(version)
                            results["all_vulnerable_packages"][pkg_name][
                                "sources"
                            ].append(f"Pipfile:{pipfile.name}:{section}")
    except Exception as e:
        logger.warning(f"Error parsing Pipfile: {e}")

    return vulns


async def check_pipfile_lock(
    server: "PyPIMCPServer", pipfile_lock: Path, results: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Parse Pipfile.lock for exact versions.

    Args:
        server: The PyPIMCPServer instance for API calls.
        pipfile_lock: Path to Pipfile.lock.
        results: Results dictionary to update with vulnerable packages.

    Returns:
        List of vulnerability dictionaries found.
    """
    vulns = []
    try:
        data = json.loads(pipfile_lock.read_text())

        for section in ["default", "develop"]:
            if section in data:
                for pkg_name, pkg_info in data[section].items():
                    if "version" in pkg_info:
                        version = pkg_info["version"].lstrip("==")
                        vuln_check = await server.client.check_vulnerabilities(
                            pkg_name, version
                        )
                        if vuln_check.get("vulnerable"):
                            vulns.append(
                                {
                                    "package": pkg_name,
                                    "version": version,
                                    "vulnerabilities": vuln_check.get(
                                        "total_vulnerabilities", 0
                                    ),
                                    "critical": vuln_check.get("critical_count", 0),
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
                            ].add(version)
                            results["all_vulnerable_packages"][pkg_name][
                                "sources"
                            ].append(f"Pipfile.lock:{pipfile_lock.name}:{section}")
    except Exception as e:
        logger.warning(f"Error parsing Pipfile.lock: {e}")

    return vulns


async def check_poetry_lock(
    server: "PyPIMCPServer", poetry_lock: Path, results: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Parse poetry.lock for exact versions.

    Args:
        server: The PyPIMCPServer instance for API calls.
        poetry_lock: Path to poetry.lock.
        results: Results dictionary to update with vulnerable packages.

    Returns:
        List of vulnerability dictionaries found.
    """
    vulns = []
    try:
        import toml

        data = toml.load(poetry_lock)

        if "package" in data:
            for pkg in data["package"]:
                pkg_name = pkg.get("name", "")
                version = pkg.get("version", "")

                if pkg_name and version:
                    vuln_check = await server.client.check_vulnerabilities(
                        pkg_name, version
                    )
                    if vuln_check.get("vulnerable"):
                        vulns.append(
                            {
                                "package": pkg_name,
                                "version": version,
                                "vulnerabilities": vuln_check.get(
                                    "total_vulnerabilities", 0
                                ),
                                "critical": vuln_check.get("critical_count", 0),
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
                        ].add(version)
                        results["all_vulnerable_packages"][pkg_name]["sources"].append(
                            f"poetry.lock:{poetry_lock.name}"
                        )
    except Exception as e:
        logger.warning(f"Error parsing poetry.lock: {e}")

    return vulns


async def check_conda_file(
    server: "PyPIMCPServer", conda_file: Path, results: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Parse conda environment files.

    Args:
        server: The PyPIMCPServer instance for API calls.
        conda_file: Path to conda environment file.
        results: Results dictionary to update with vulnerable packages.

    Returns:
        List of vulnerability dictionaries found.
    """
    vulns = []
    try:
        import yaml

        data = yaml.safe_load(conda_file.read_text())

        if "dependencies" in data:
            for dep in data["dependencies"]:
                if isinstance(dep, str):
                    parts = dep.split("=")
                    pkg_name = parts[0]
                    version = parts[1] if len(parts) > 1 else None

                    if pkg_name.startswith("python") or pkg_name in ["pip"]:
                        continue

                    if version:
                        vuln_check = await server.client.check_vulnerabilities(
                            pkg_name, version
                        )
                    else:
                        latest_info = await server.client.get_latest_version(pkg_name)
                        if latest_info and not latest_info.get("error"):
                            version = latest_info.get("version")
                            vuln_check = await server.client.check_vulnerabilities(
                                pkg_name, version
                            )
                        else:
                            continue

                    if vuln_check.get("vulnerable"):
                        vulns.append(
                            {
                                "package": pkg_name,
                                "version": version,
                                "vulnerabilities": vuln_check.get(
                                    "total_vulnerabilities", 0
                                ),
                                "critical": vuln_check.get("critical_count", 0),
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
                        ].add(version)
                        results["all_vulnerable_packages"][pkg_name]["sources"].append(
                            f"conda:{conda_file.name}"
                        )

                elif isinstance(dep, dict) and "pip" in dep:
                    for pip_dep in dep["pip"]:
                        parts = re.split(r"[<>=!~]", pip_dep)
                        pkg_name = parts[0].strip()

                        if pkg_name:
                            latest_info = await server.client.get_latest_version(
                                pkg_name
                            )
                            if latest_info and not latest_info.get("error"):
                                version = latest_info.get("version")
                                vuln_check = await server.client.check_vulnerabilities(
                                    pkg_name, version
                                )
                                if vuln_check.get("vulnerable"):
                                    vulns.append(
                                        {
                                            "package": pkg_name,
                                            "version": version,
                                            "vulnerabilities": vuln_check.get(
                                                "total_vulnerabilities", 0
                                            ),
                                            "critical": vuln_check.get(
                                                "critical_count", 0
                                            ),
                                            "high": vuln_check.get("high_count", 0),
                                        }
                                    )

                                    if (
                                        pkg_name
                                        not in results["all_vulnerable_packages"]
                                    ):
                                        results["all_vulnerable_packages"][pkg_name] = {
                                            "versions_affected": set(),
                                            "sources": [],
                                            "max_severity": "low",
                                        }
                                    results["all_vulnerable_packages"][pkg_name][
                                        "versions_affected"
                                    ].add(version)
                                    results["all_vulnerable_packages"][pkg_name][
                                        "sources"
                                    ].append(f"conda:{conda_file.name}:pip")
    except Exception as e:
        logger.warning(f"Error parsing conda file: {e}")

    return vulns


def format_security_report(audit_result: Dict[str, Any]) -> str:
    """Format the security audit results into a beautiful colored report with tables.

    Args:
        audit_result: The audit result dictionary from security_audit_project.

    Returns:
        Formatted string with ANSI color codes for terminal display.
    """
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    ORANGE = "\033[38;5;208m"
    GRAY = "\033[90m"

    H_LINE = "-"
    V_LINE = "|"
    TL_CORNER = "+"
    TR_CORNER = "+"
    BL_CORNER = "+"
    BR_CORNER = "+"
    T_JOINT = "+"
    B_JOINT = "+"
    L_JOINT = "+"
    R_JOINT = "+"
    CROSS = "+"

    report_lines = []

    report_lines.append(f"\n{BOLD}PYTHON PROJECT SECURITY AUDIT REPORT{RESET}")
    report_lines.append(f"{GRAY}{'=' * 60}{RESET}")
    report_lines.append(f"Project: {audit_result.get('project_path', 'Unknown')}")
    report_lines.append(f"Scan Date: {audit_result.get('scan_timestamp', 'Unknown')}")
    report_lines.append("")

    risk_level = audit_result.get("overall_risk_level", "UNKNOWN")
    security_score = audit_result.get("security_score", 0)
    total_vulns = audit_result.get("total_vulnerabilities", 0)

    if "CRITICAL" in risk_level:
        risk_color = RED
    elif "HIGH" in risk_level:
        risk_color = ORANGE
    elif "MEDIUM" in risk_level:
        risk_color = YELLOW
    elif "LOW" in risk_level:
        risk_color = BLUE
    elif "SECURE" in risk_level:
        risk_color = GREEN
    else:
        risk_color = GRAY

    report_lines.append(f"{BOLD}EXECUTIVE SUMMARY{RESET}")
    report_lines.append(f"{TL_CORNER}{H_LINE * 58}{TR_CORNER}")
    report_lines.append(
        f"{V_LINE} Risk Level: {risk_color}{BOLD}{risk_level}{RESET}{'':>30}{V_LINE}"
    )
    report_lines.append(
        f"{V_LINE} Security Score: {_color_score(security_score)}{BOLD}{security_score}/100{RESET}{'':>28}{V_LINE}"
    )
    report_lines.append(
        f"{V_LINE} Total Vulnerabilities: {BOLD}{total_vulns}{RESET}{'':>32}{V_LINE}"
    )
    report_lines.append(f"{BL_CORNER}{H_LINE * 58}{BR_CORNER}")
    report_lines.append("")

    severity = audit_result.get("severity_breakdown", {})
    critical = severity.get("critical", 0)
    high = severity.get("high", 0)
    medium = severity.get("medium", 0)
    low = severity.get("low", 0)

    report_lines.append(f"{BOLD}VULNERABILITY DISTRIBUTION{RESET}")
    report_lines.append(
        f"{TL_CORNER}{H_LINE * 20}{T_JOINT}{H_LINE * 10}{T_JOINT}{H_LINE * 27}{TR_CORNER}"
    )
    report_lines.append(
        f"{V_LINE} {'Severity':<18} {V_LINE} {'Count':>8} {V_LINE} {'Visual':<25} {V_LINE}"
    )
    report_lines.append(
        f"{L_JOINT}{H_LINE * 20}{CROSS}{H_LINE * 10}{CROSS}{H_LINE * 27}{R_JOINT}"
    )

    bar = _make_bar(critical, max(total_vulns, 1), 20, RED)
    report_lines.append(
        f"{V_LINE} {RED}CRITICAL{RESET}{'':>11} {V_LINE} {RED}{critical:>8}{RESET} {V_LINE} {bar:<25} {V_LINE}"
    )

    bar = _make_bar(high, max(total_vulns, 1), 20, ORANGE)
    report_lines.append(
        f"{V_LINE} {ORANGE}HIGH{RESET}{'':>15} {V_LINE} {ORANGE}{high:>8}{RESET} {V_LINE} {bar:<25} {V_LINE}"
    )

    bar = _make_bar(medium, max(total_vulns, 1), 20, YELLOW)
    report_lines.append(
        f"{V_LINE} {YELLOW}MEDIUM{RESET}{'':>13} {V_LINE} {YELLOW}{medium:>8}{RESET} {V_LINE} {bar:<25} {V_LINE}"
    )

    bar = _make_bar(low, max(total_vulns, 1), 20, BLUE)
    report_lines.append(
        f"{V_LINE} {BLUE}LOW{RESET}{'':>16} {V_LINE} {BLUE}{low:>8}{RESET} {V_LINE} {bar:<25} {V_LINE}"
    )

    report_lines.append(
        f"{BL_CORNER}{H_LINE * 20}{B_JOINT}{H_LINE * 10}{B_JOINT}{H_LINE * 27}{BR_CORNER}"
    )
    report_lines.append("")

    priority_fixes = audit_result.get("priority_fixes", [])
    if priority_fixes:
        report_lines.append(f"{BOLD}TOP PRIORITY FIXES{RESET}")
        report_lines.append(
            f"{TL_CORNER}{H_LINE * 25}{T_JOINT}{H_LINE * 12}{T_JOINT}{H_LINE * 10}{T_JOINT}{H_LINE * 25}{TR_CORNER}"
        )
        report_lines.append(
            f"{V_LINE} {'Package':<23} {V_LINE} {'Version':<10} {V_LINE} {'Vulns':>8} {V_LINE} {'Action Required':<23} {V_LINE}"
        )
        report_lines.append(
            f"{L_JOINT}{H_LINE * 25}{CROSS}{H_LINE * 12}{CROSS}{H_LINE * 10}{CROSS}{H_LINE * 25}{R_JOINT}"
        )

        for fix in priority_fixes[:10]:
            pkg_name = fix.get("package", "Unknown")[:23]
            versions = fix.get("versions", fix.get("affected_versions", []))
            if not isinstance(versions, list):
                versions = list(versions) if versions else []
            version = versions[0][:10] if versions else "Unknown"
            vuln_count = fix.get("total_vulnerabilities", 0)

            if fix.get("critical", 0) > 0:
                action = f"{RED}IMMEDIATE UPDATE!{RESET}"
            elif fix.get("high", 0) > 0:
                action = f"{ORANGE}Update Strongly Advised{RESET}"
            elif fix.get("medium", 0) > 0:
                action = f"{YELLOW}Update Recommended{RESET}"
            else:
                action = f"{BLUE}Monitor for Updates{RESET}"

            if vuln_count >= 10:
                vuln_color = RED
            elif vuln_count >= 5:
                vuln_color = ORANGE
            elif vuln_count >= 2:
                vuln_color = YELLOW
            else:
                vuln_color = BLUE

            report_lines.append(
                f"{V_LINE} {pkg_name:<23} {V_LINE} {version:<10} {V_LINE} {vuln_color}{vuln_count:>8}{RESET} {V_LINE} {action:<40} {V_LINE}"
            )

        report_lines.append(
            f"{BL_CORNER}{H_LINE * 25}{B_JOINT}{H_LINE * 12}{B_JOINT}{H_LINE * 10}{B_JOINT}{H_LINE * 25}{BR_CORNER}"
        )
        report_lines.append("")

    checks = audit_result.get("checks_performed", [])
    if checks:
        report_lines.append(f"{BOLD}FILES SCANNED{RESET}")
        for check in checks:
            report_lines.append(f"  {GREEN}+{RESET} {check}")
        report_lines.append("")

    remediation = audit_result.get("remediation_plan", [])
    if remediation:
        report_lines.append(f"{BOLD}REMEDIATION PLAN{RESET}")
        for step in remediation:
            if "CRITICAL" in step or "IMMEDIATELY" in step:
                report_lines.append(f"  {RED}{step}{RESET}")
            elif "HIGH" in step:
                report_lines.append(f"  {ORANGE}{step}{RESET}")
            else:
                report_lines.append(f"  {step}")
        report_lines.append("")

    recommendation = audit_result.get("recommendation", "")
    if recommendation:
        report_lines.append(f"{BOLD}RECOMMENDATION{RESET}")
        report_lines.append(f"{GRAY}{'-' * 60}{RESET}")
        if "URGENT" in recommendation:
            report_lines.append(f"{RED}{BOLD}{recommendation}{RESET}")
        else:
            report_lines.append(recommendation)
        report_lines.append(f"{GRAY}{'-' * 60}{RESET}")

    return "\n".join(report_lines)


def _color_score(score: int) -> str:
    """Return appropriate color for security score."""
    if score >= 90:
        return "\033[92m"
    elif score >= 70:
        return "\033[94m"
    elif score >= 50:
        return "\033[93m"
    elif score >= 30:
        return "\033[38;5;208m"
    else:
        return "\033[91m"


def _make_bar(value: int, total: int, width: int, color: str) -> str:
    """Create a colored progress bar."""
    if total == 0:
        return ""
    percentage = value / total
    filled = int(width * percentage)
    bar = color + "#" * filled + "\033[90m" + "." * (width - filled) + "\033[0m"
    return bar

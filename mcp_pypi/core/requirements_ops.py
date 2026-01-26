"""
Requirements file operations mixin for PyPI client.
"""

import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from packaging.requirements import Requirement
from packaging.version import Version

from mcp_pypi.core.models import (
    ErrorCode,
    PackageRequirement,
    PackageRequirementsResult,
    format_error,
)
from mcp_pypi.utils.common.validation import validate_file_path
from mcp_pypi.utils.helpers import sanitize_package_name

# For Python < 3.11, use tomli for parsing TOML files
if sys.version_info < (3, 11):
    import tomli as tomllib  # type: ignore[import-not-found]
else:
    import tomllib

logger = logging.getLogger("mcp-pypi.client")


class RequirementsOpsMixin:
    """Mixin providing requirements file operations."""

    async def check_requirements_file(
        self, file_path: str
    ) -> PackageRequirementsResult:
        """Check a requirements file for outdated packages."""
        try:
            # Validate file path for security (prevent path traversal attacks)
            is_valid, error_msg = validate_file_path(file_path)
            if not is_valid:
                return cast(
                    PackageRequirementsResult,
                    format_error(ErrorCode.INVALID_INPUT, error_msg or "Invalid file path"),
                )

            path = Path(file_path).resolve()

            # Check if file exists
            if not path.exists():
                return cast(
                    PackageRequirementsResult,
                    format_error(ErrorCode.FILE_ERROR, f"File not found: {file_path}"),
                )

            # Check file extension
            if path.name.endswith((".toml")):
                return await self._check_pyproject_toml(path)
            elif path.name.endswith((".txt", ".pip")):
                return await self._check_requirements_txt(path)
            else:
                return cast(
                    PackageRequirementsResult,
                    format_error(
                        ErrorCode.INVALID_INPUT,
                        f"File must be a .txt, .pip, or .toml file: {file_path}",
                    ),
                )
        except Exception as e:
            logger.exception(f"Error checking requirements file: {e}")
            return cast(
                PackageRequirementsResult,
                format_error(
                    ErrorCode.UNKNOWN_ERROR,
                    f"Error checking requirements file: {str(e)}",
                ),
            )

    async def _check_requirements_txt(self, path: Path) -> PackageRequirementsResult:
        """Check a requirements.txt file for outdated packages."""
        try:
            # Read file
            try:
                with path.open("r") as f:
                    requirements = f.readlines()
            except PermissionError:
                return cast(
                    PackageRequirementsResult,
                    format_error(
                        ErrorCode.PERMISSION_ERROR,
                        f"Permission denied when reading file: {str(path)}",
                    ),
                )
            except Exception as e:
                return cast(
                    PackageRequirementsResult,
                    format_error(ErrorCode.FILE_ERROR, f"Error reading file: {str(e)}"),
                )

            outdated: List[PackageRequirement] = []
            up_to_date: List[PackageRequirement] = []

            for req_line in requirements:
                req_line = req_line.strip()
                if not req_line or req_line.startswith("#"):
                    continue

                # Remove inline comments before parsing
                if "#" in req_line:
                    req_line = req_line.split("#", 1)[0].strip()

                # Parse requirement
                try:
                    # Use packaging.requirements for accurate parsing
                    req = Requirement(req_line)
                    pkg_name = req.name

                    # Get latest version
                    latest_version_info = await self.get_latest_version(pkg_name)

                    if "error" in latest_version_info:
                        # Skip packages we can't find
                        continue

                    latest_version = latest_version_info["version"]

                    # Compare versions
                    latest_ver = Version(latest_version)

                    # Check if up to date
                    is_outdated = False
                    current_version = None
                    security_recommendation = None

                    if req.specifier:
                        # Extract the version from the specifier
                        for spec in req.specifier:  # type: ignore[assignment]
                            if spec.operator in ("==", "==="):
                                current_version = str(spec.version)
                                req_ver = Version(current_version)
                                is_outdated = latest_ver > req_ver
                            elif spec.operator == ">=":
                                # For >= constraints, check if minimum version has vulnerabilities
                                min_version = str(spec.version)
                                current_version = f"{spec.operator}{spec.version}"

                                # Check vulnerabilities for minimum allowed version
                                vuln_check = await self.check_vulnerabilities(
                                    pkg_name, min_version
                                )

                                if vuln_check.get("vulnerable", False):
                                    # Find the earliest safe version
                                    safe_version = (
                                        await self._find_earliest_safe_version(
                                            pkg_name, min_version, latest_version
                                        )
                                    )

                                    if safe_version and safe_version != min_version:
                                        is_outdated = True
                                        security_recommendation = (
                                            f"Security: Update constraint to >={safe_version} "
                                            f"(current allows vulnerable {min_version})"
                                        )
                            else:
                                # For other operators (>, <=, <, ~=), still capture the constraint
                                # but don't mark as outdated
                                if (
                                    not current_version
                                ):  # Only take the first constraint if multiple
                                    current_version = f"{spec.operator}{spec.version}"

                    # If no version info could be determined, set to latest
                    if not current_version:
                        current_version = "unspecified (latest)"

                    pkg_info = {
                        "package": pkg_name,
                        "current_version": current_version,
                        "latest_version": latest_version,
                        "constraint": str(req.specifier),
                    }

                    if security_recommendation:
                        pkg_info["recommendation"] = security_recommendation

                    if is_outdated:
                        outdated.append(pkg_info)
                    else:
                        up_to_date.append(pkg_info)
                except Exception as e:
                    logger.warning(f"Error parsing requirement '{req_line}': {e}")
                    # Try a simple extraction for unparseable requirements
                    try:
                        # Extract package name using regex
                        match = re.match(
                            r"^([a-zA-Z0-9_.-]+)(?:[<>=~!]=?|@)(.+)?", req_line
                        )

                        if match:
                            pkg_name = match.group(1)
                            version_spec = (
                                match.group(2).strip() if match.group(2) else None
                            )

                            # Get latest version
                            latest_version_info = await self.get_latest_version(
                                pkg_name
                            )

                            if "error" not in latest_version_info:
                                latest_version = latest_version_info["version"]

                                if version_spec:
                                    # Add as potentially outdated
                                    outdated.append(
                                        {
                                            "package": pkg_name,
                                            "current_version": version_spec,
                                            "latest_version": latest_version,
                                            "constraint": version_spec,
                                        }
                                    )
                                else:
                                    # No specific version required
                                    up_to_date.append(
                                        {
                                            "package": pkg_name,
                                            "current_version": "unspecified (latest)",
                                            "latest_version": latest_version,
                                            "constraint": "",
                                        }
                                    )
                        else:
                            # Raw package name without version specifier
                            pkg_name = req_line

                            # Get latest version
                            latest_version_info = await self.get_latest_version(
                                pkg_name
                            )

                            if "error" not in latest_version_info:
                                latest_version = latest_version_info["version"]
                                up_to_date.append(
                                    {
                                        "package": pkg_name,
                                        "current_version": "unspecified (latest)",
                                        "latest_version": latest_version,
                                        "constraint": "",
                                    }
                                )
                    except Exception:
                        # Skip lines we can't parse at all
                        continue

            # Check if other dependency files exist in the same directory
            req_path = Path(str(path))
            project_dir = req_path.parent

            other_dep_files = []
            for pattern in ["pyproject.toml", "setup.py", "setup.cfg", "Pipfile"]:
                if (project_dir / pattern).exists() and pattern != req_path.name:
                    other_dep_files.append(str(project_dir / pattern))

            result = {"outdated": outdated, "up_to_date": up_to_date}

            # Add actionable next steps if vulnerabilities found
            if outdated and any("recommendation" in pkg for pkg in outdated):
                result["action_required"] = True

                # Check if pyproject.toml exists (it's the primary source)
                has_pyproject = any("pyproject.toml" in f for f in other_dep_files)

                if has_pyproject:
                    # requirements.txt is secondary - suggest updating pyproject.toml first
                    result["next_steps"] = [
                        "CHECK pyproject.toml FIRST - it's the primary dependency source",
                        "UPDATE pyproject.toml with the recommended secure versions",
                        "THEN update this requirements.txt to match pyproject.toml",
                        f"VERIFY consistency with other files: {', '.join(f for f in other_dep_files if 'pyproject.toml' not in f)}" if any(f for f in other_dep_files if 'pyproject.toml' not in f) else None,
                        "COMMIT changes with message: 'chore: Update dependencies for security (all files)'"
                    ]
                else:
                    # No pyproject.toml - requirements.txt is primary
                    result["next_steps"] = [
                        "UPDATE this file with the recommended secure versions",
                        f"CHECK other dependency files for consistency: {', '.join(other_dep_files)}" if other_dep_files else None,
                        "COMMIT changes with message mentioning all updated files"
                    ]

                result["next_steps"] = [step for step in result["next_steps"] if step]

            return result
        except Exception as e:
            logger.exception(f"Error checking requirements.txt file: {e}")
            return cast(
                PackageRequirementsResult,
                format_error(
                    ErrorCode.UNKNOWN_ERROR,
                    f"Error checking requirements file: {str(e)}",
                ),
            )

    def _extract_dependencies_from_pyproject(
        self, pyproject_data: Dict[str, Any]
    ) -> List[str]:
        """Extract dependencies from various pyproject.toml formats.

        Args:
            pyproject_data: Parsed pyproject.toml data

        Returns:
            List of dependency strings
        """
        dependencies = []

        # 1. PEP 621 format - project.dependencies
        if "project" in pyproject_data and "dependencies" in pyproject_data["project"]:
            dependencies.extend(pyproject_data["project"]["dependencies"])

        # 2. Poetry format - tool.poetry.dependencies
        if "tool" in pyproject_data and "poetry" in pyproject_data["tool"]:
            if "dependencies" in pyproject_data["tool"]["poetry"]:
                poetry_deps = pyproject_data["tool"]["poetry"]["dependencies"]
                for name, constraint in poetry_deps.items():
                    if name == "python":  # Skip python dependency
                        continue
                    if isinstance(constraint, str):
                        dependencies.append(f"{name}{constraint}")
                    elif isinstance(constraint, dict) and "version" in constraint:
                        dependencies.append(f"{name}{constraint['version']}")

        # 3. PDM format - tool.pdm.dependencies
        if "tool" in pyproject_data and "pdm" in pyproject_data["tool"]:
            if "dependencies" in pyproject_data["tool"]["pdm"]:
                pdm_deps = pyproject_data["tool"]["pdm"]["dependencies"]
                for name, constraint in pdm_deps.items():
                    if isinstance(constraint, str):
                        dependencies.append(f"{name}{constraint}")
                    elif isinstance(constraint, dict) and "version" in constraint:
                        dependencies.append(f"{name}{constraint['version']}")

        # 4. Flit format - tool.flit.metadata.requires
        if "tool" in pyproject_data and "flit" in pyproject_data["tool"]:
            if (
                "metadata" in pyproject_data["tool"]["flit"]
                and "requires" in pyproject_data["tool"]["flit"]["metadata"]
            ):
                dependencies.extend(
                    pyproject_data["tool"]["flit"]["metadata"]["requires"]
                )

        return dependencies

    def _load_toml_module(self):
        """Load the appropriate TOML parsing module.

        Returns:
            The tomllib or tomli module, or None if not available
        """
        try:
            import tomllib

            return tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[import-not-found]

                return tomllib
            except ImportError:
                return None

    async def _check_pyproject_toml(self, path: Path) -> PackageRequirementsResult:
        """Check a pyproject.toml file for outdated packages."""
        # Load TOML module
        toml_module = self._load_toml_module()
        if not toml_module:
            return cast(
                PackageRequirementsResult,
                format_error(
                    ErrorCode.MISSING_DEPENDENCY,
                    "Parsing pyproject.toml requires tomli package. Please install with: pip install tomli",
                ),
            )

        # Read and parse the TOML file
        try:
            with path.open("rb") as f:
                pyproject_data = toml_module.load(f)
        except PermissionError:
            return cast(
                PackageRequirementsResult,
                format_error(
                    ErrorCode.PERMISSION_ERROR,
                    f"Permission denied when reading file: {str(path)}",
                ),
            )
        except Exception as e:
            return cast(
                PackageRequirementsResult,
                format_error(
                    ErrorCode.FILE_ERROR, f"Error reading TOML file: {str(e)}"
                ),
            )

        # Extract dependencies using helper method
        dependencies = self._extract_dependencies_from_pyproject(pyproject_data)

        # Process dependencies
        outdated = []
        up_to_date = []

        for req_str in dependencies:
            try:
                req = Requirement(req_str)
                package_name = sanitize_package_name(req.name)

                # Get package info from PyPI
                info_result = await self.get_latest_version(package_name)

                # Check if we got a valid result
                if "error" in info_result:
                    logger.warning(
                        f"Could not get latest version for {package_name}: {info_result['error']['message']}"
                    )
                    continue

                latest_version = info_result.get("version", "")
                if not latest_version:
                    logger.warning(f"No version information found for {package_name}")
                    continue

                # Get current version from requirement specifier
                current_version = ""
                is_outdated = False
                security_recommendation = None

                # Handle different types of version specifiers
                if req.specifier:
                    for spec in req.specifier:
                        if spec.operator in ("==", "==="):
                            # Exact version match
                            current_version = str(spec.version)

                            # Check if outdated
                            try:
                                current_ver = Version(current_version)
                                latest_ver = Version(latest_version)
                                is_outdated = latest_ver > current_ver
                            except Exception as e:
                                logger.warning(
                                    f"Error comparing versions for {package_name}: {e}"
                                )
                                continue
                        else:
                            # For other operators (>=, >, etc.) use as constraint but don't mark as outdated
                            if not current_version:
                                current_version = f"{spec.operator}{spec.version}"

                # If no version info could be determined, set to latest
                if not current_version:
                    current_version = "unspecified (latest)"

                # Add to appropriate list
                pkg_info = {
                    "package": req.name,
                    "current_version": current_version,
                    "latest_version": latest_version,
                    "constraint": str(req.specifier),
                }

                if security_recommendation:
                    pkg_info["recommendation"] = security_recommendation

                if is_outdated:
                    outdated.append(pkg_info)
                else:
                    up_to_date.append(pkg_info)

            except Exception as e:
                logger.warning(f"Error processing dependency {req_str}: {e}")
                continue

        # Check if other dependency files exist in the same directory
        toml_path = Path(str(path))
        project_dir = toml_path.parent

        other_dep_files = []
        for pattern in ["requirements.txt", "requirements-*.txt", "setup.py", "setup.cfg", "Pipfile"]:
            if pattern.startswith("requirements-"):
                # Handle wildcard pattern
                for req_file in project_dir.glob(pattern):
                    if req_file.exists() and req_file.name != toml_path.name:
                        other_dep_files.append(str(req_file))
            else:
                if (project_dir / pattern).exists() and pattern != toml_path.name:
                    other_dep_files.append(str(project_dir / pattern))

        result = {"outdated": outdated, "up_to_date": up_to_date}

        # Add actionable next steps if vulnerabilities found
        if outdated and any("recommendation" in pkg for pkg in outdated):
            result["action_required"] = True
            result["file_priority"] = "PRIMARY - This is the modern Python standard"

            # pyproject.toml is primary - changes should trickle down
            result["next_steps"] = [
                "UPDATE this pyproject.toml FIRST with the recommended secure versions",
                f"TRICKLE DOWN changes to secondary files: {', '.join(other_dep_files)}" if other_dep_files else None,
                "ENSURE all files have IDENTICAL version constraints",
                "REGENERATE requirements.txt if using pip-tools: pip-compile pyproject.toml",
                "COMMIT changes with message: 'chore: Update dependencies for security (all files)'"
            ]
            result["next_steps"] = [step for step in result["next_steps"] if step]

        return result

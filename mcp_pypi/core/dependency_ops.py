"""
Dependency operations mixin for PyPI client.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, cast

from packaging.requirements import Requirement
from packaging.version import Version

from mcp_pypi.core.models import (
    DependenciesResult,
    DependencyTreeResult,
    ErrorCode,
    TreeNode,
    format_error,
)
from mcp_pypi.utils.helpers import sanitize_package_name, sanitize_version

logger = logging.getLogger("mcp-pypi.client")


class DependencyOpsMixin:
    """Mixin providing dependency-related operations."""

    async def get_dependencies(
        self, package_name: str, version: Optional[str] = None
    ) -> DependenciesResult:
        """Get the dependencies for a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)

            if version:
                sanitized_version = sanitize_version(version)
                url = f"https://pypi.org/pypi/{sanitized_name}/{sanitized_version}/json"
            else:
                url = f"https://pypi.org/pypi/{sanitized_name}/json"

            result = await self.http.fetch(url)

            # Check for error in result
            if isinstance(result, dict) and "error" in result:
                return cast(DependenciesResult, result)

            # Handle the new format where raw data might be returned
            if isinstance(result, dict) and "raw_data" in result:
                content_type = result.get("content_type", "")
                raw_data = result["raw_data"]

                # If we got JSON content, parse it
                if "application/json" in content_type and isinstance(raw_data, str):
                    try:
                        parsed_data = json.loads(raw_data)
                        parsed_result = parsed_data
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from raw_data: {e}")
                        return cast(
                            DependenciesResult,
                            format_error(
                                ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"
                            ),
                        )
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(
                        DependenciesResult,
                        format_error(
                            ErrorCode.PARSE_ERROR,
                            f"Unexpected content type: {content_type}",
                        ),
                    )
            else:
                # Already parsed JSON data
                parsed_result = result

            requires_dist = parsed_result["info"].get("requires_dist", []) or []
            dependencies = []

            # Parse using packaging.requirements for better accuracy
            for req_str in requires_dist:
                try:
                    req = Requirement(req_str)
                    dep = {
                        "name": req.name,
                        "version_spec": str(req.specifier) if req.specifier else "",
                        "extras": list(req.extras) if req.extras else [],
                        "marker": str(req.marker) if req.marker else None,
                    }
                    dependencies.append(dep)
                except Exception as e:
                    logger.warning(f"Couldn't parse requirement '{req_str}': {e}")
                    # Add a simplified entry for unparseable requirements
                    if ":" in req_str:
                        name = req_str.split(":")[0].strip()
                    elif ";" in req_str:
                        name = req_str.split(";")[0].strip()
                    else:
                        name = req_str.split()[0].strip()

                    dependencies.append(
                        {
                            "name": name,
                            "version_spec": "",
                            "extras": [],
                            "marker": "Parse error",
                        }
                    )

            return {"dependencies": dependencies}
        except ValueError as e:
            return cast(
                DependenciesResult, format_error(ErrorCode.INVALID_INPUT, str(e))
            )
        except Exception as e:
            logger.exception(f"Error getting dependencies: {e}")
            return cast(
                DependenciesResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e))
            )

    async def get_dependency_tree(
        self,
        package_name: str,
        version: Optional[str] = None,
        depth: int = 3,
        max_width: int = 50,
    ) -> DependencyTreeResult:
        """Get the dependency tree for a package.

        Args:
            package_name: Name of the package
            version: Specific version (optional, defaults to latest)
            depth: Maximum depth to traverse (default: 3)
            max_width: Maximum dependencies to include per level (default: 50)
        """
        try:
            sanitized_name = sanitize_package_name(package_name)
            if version:
                sanitized_version = sanitize_version(version)
            else:
                # Get latest version if not specified
                version_info = await self.get_latest_version(sanitized_name)
                if isinstance(version_info, dict) and "error" in version_info:
                    return cast(DependencyTreeResult, version_info)
                sanitized_version = version_info["version"]

            # Use iterative approach to avoid stack overflows with deep trees
            # Track visited packages to avoid cycles
            visited: Dict[str, Optional[str]] = {}
            flat_list: List[str] = []

            # Build dependency tree iteratively
            async def build_tree() -> TreeNode:
                queue: List[Tuple[str, Optional[str], int, Optional[str]]] = [
                    (sanitized_name, sanitized_version, 0, None)
                ]
                nodes: Dict[str, TreeNode] = {}

                # Root node
                root: TreeNode = {
                    "name": sanitized_name,
                    "version": sanitized_version,
                    "dependencies": [],
                }
                nodes[f"{sanitized_name}:{sanitized_version}"] = root

                while queue:
                    pkg_name, pkg_version, level, parent_key = queue.pop(0)

                    # Skip if too deep
                    if level > depth:
                        continue

                    # Generate a unique key for this package+version
                    pkg_key = f"{pkg_name}:{pkg_version}"

                    # Check for cycles
                    if pkg_key in visited:
                        if parent_key:
                            parent = nodes.get(parent_key)
                            if parent:
                                node: TreeNode = {
                                    "name": pkg_name,
                                    "version": pkg_version,
                                    "dependencies": [],
                                    "cycle": True,
                                }
                                parent["dependencies"].append(node)
                        continue

                    # Mark as visited
                    visited[pkg_key] = pkg_version

                    # Add to flat list
                    display_version = f" ({pkg_version})" if pkg_version else ""
                    flat_list.append(f"{pkg_name}{display_version}")

                    # Create node if not exists
                    if pkg_key not in nodes:
                        nodes[pkg_key] = {
                            "name": pkg_name,
                            "version": pkg_version,
                            "dependencies": [],
                        }

                    # Connect to parent
                    if parent_key and parent_key in nodes:
                        parent = nodes[parent_key]
                        if nodes[pkg_key] not in parent["dependencies"]:
                            parent["dependencies"].append(nodes[pkg_key])

                    # Get dependencies if not at max depth
                    if level < depth:
                        deps_result = await self.get_dependencies(pkg_name, pkg_version)

                        if isinstance(deps_result, dict) and "error" in deps_result:
                            # Skip this dependency if there was an error
                            continue

                        if "dependencies" in deps_result:
                            # Apply max_width limit to dependencies
                            deps_list = deps_result["dependencies"][:max_width]
                            for dep in deps_list:
                                # Extract the package name without version specifiers
                                dep_name = dep["name"]

                                # Get the version for this dependency
                                dep_version_info = await self.get_latest_version(
                                    dep_name
                                )
                                dep_version = (
                                    dep_version_info.get("version")
                                    if "error" not in dep_version_info
                                    else None
                                )

                                # Add to queue
                                queue.append(
                                    (dep_name, dep_version, level + 1, pkg_key)
                                )

                            # Note if dependencies were truncated
                            if len(deps_result["dependencies"]) > max_width:
                                truncated_count = len(deps_result["dependencies"]) - max_width
                                logger.info(
                                    f"Truncated {truncated_count} dependencies for {pkg_name} "
                                    f"(max_width={max_width})"
                                )

                return root

            # Build the tree
            tree = await build_tree()

            # Generate visualization if Plotly is available
            visualization_url = None
            if self._has_plotly:
                try:
                    import plotly.graph_objects as go
                    import plotly.io as pio

                    # Create a simple tree visualization
                    labels = [f"{node.split(' ')[0]}" for node in flat_list]
                    parents = [""] + ["Root"] * (len(flat_list) - 1)

                    fig = go.Figure(
                        go.Treemap(
                            labels=labels, parents=parents, root_color="lightgrey"
                        )
                    )

                    fig.update_layout(
                        title=f"Dependency Tree for {sanitized_name} {sanitized_version}",
                        margin=dict(t=50, l=25, r=25, b=25),
                    )

                    # Save to temp file
                    viz_file = os.path.join(
                        self.config.cache_dir,
                        f"deptree_{sanitized_name}_{sanitized_version}.html",
                    )
                    pio.write_html(fig, viz_file)
                    visualization_url = f"file://{viz_file}"
                except Exception as e:
                    logger.warning(f"Failed to generate visualization: {e}")

            result: DependencyTreeResult = {"tree": tree, "flat_list": flat_list}

            if visualization_url:
                result["visualization_url"] = visualization_url

            return result
        except ValueError as e:
            return cast(
                DependencyTreeResult, format_error(ErrorCode.INVALID_INPUT, str(e))
            )
        except Exception as e:
            logger.exception(f"Error getting dependency tree: {e}")
            return cast(
                DependencyTreeResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e))
            )

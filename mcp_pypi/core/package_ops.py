"""
Package operations mixin for PyPI client.
"""

import json
import logging
from typing import Any, Dict, Optional, cast

from mcp_pypi.core.models import (
    ErrorCode,
    ExistsResult,
    MetadataResult,
    PackageInfo,
    PackageMetadata,
    ReleasesInfo,
    UrlResult,
    UrlsInfo,
    VersionInfo,
    format_error,
)
from mcp_pypi.utils.helpers import sanitize_package_name, sanitize_version

logger = logging.getLogger("mcp-pypi.client")


class PackageOpsMixin:
    """Mixin providing package information operations."""

    async def get_package_info(self, package_name: str) -> PackageInfo:
        """Get detailed package information from PyPI."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            url = f"https://pypi.org/pypi/{sanitized_name}/json"

            result = await self.http.fetch(url)

            # Check for error in result
            if isinstance(result, dict) and "error" in result:
                return cast(PackageInfo, result)

            # Handle the new format where raw data might be returned
            if isinstance(result, dict) and "raw_data" in result:
                content_type = result.get("content_type", "")
                raw_data = result["raw_data"]

                # Handle empty response
                if not raw_data:
                    logger.warning(f"Received empty response for {url}")
                    return cast(
                        PackageInfo,
                        format_error(ErrorCode.PARSE_ERROR, "Received empty response"),
                    )

                # If we got JSON content, parse it
                if "application/json" in content_type and isinstance(raw_data, str):
                    try:
                        parsed_data = json.loads(raw_data)
                        return cast(PackageInfo, parsed_data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from raw_data: {e}")
                        return cast(
                            PackageInfo,
                            format_error(
                                ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"
                            ),
                        )
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(
                        PackageInfo,
                        format_error(
                            ErrorCode.PARSE_ERROR,
                            f"Unexpected content type: {content_type}",
                        ),
                    )

            # Already parsed JSON data
            return cast(PackageInfo, result)
        except ValueError as e:
            return cast(PackageInfo, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Unexpected error getting package info: {e}")
            return cast(PackageInfo, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def get_latest_version(self, package_name: str) -> VersionInfo:
        """Get the latest version of a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            url = f"https://pypi.org/pypi/{sanitized_name}/json"

            data = await self.http.fetch(url)

            # Check for error in result
            if isinstance(data, dict) and "error" in data:
                return cast(VersionInfo, data)

            # Handle the new format where raw data might be returned
            if isinstance(data, dict) and "raw_data" in data:
                content_type = data.get("content_type", "")
                raw_data = data["raw_data"]

                # If we got JSON content, parse it
                if "application/json" in content_type and isinstance(raw_data, str):
                    try:
                        parsed_data = json.loads(raw_data)
                        version = parsed_data.get("info", {}).get("version", "")
                        return {"version": version}
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from raw_data: {e}")
                        return cast(
                            VersionInfo,
                            format_error(
                                ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"
                            ),
                        )
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(
                        VersionInfo,
                        format_error(
                            ErrorCode.PARSE_ERROR,
                            f"Unexpected content type: {content_type}",
                        ),
                    )

            # Already parsed JSON data
            version = data.get("info", {}).get("version", "")
            return {"version": version}
        except ValueError as e:
            return cast(VersionInfo, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Unexpected error getting latest version: {e}")
            return cast(VersionInfo, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def get_package_releases(self, package_name: str) -> ReleasesInfo:
        """Get all releases for a package."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            url = f"https://pypi.org/pypi/{sanitized_name}/json"

            data = await self.http.fetch(url)

            # Check for error in result
            if isinstance(data, dict) and "error" in data:
                return cast(ReleasesInfo, data)

            # Handle the new format where raw data might be returned
            if isinstance(data, dict) and "raw_data" in data:
                content_type = data.get("content_type", "")
                raw_data = data["raw_data"]

                # If we got JSON content, parse it
                if "application/json" in content_type and isinstance(raw_data, str):
                    try:
                        parsed_data = json.loads(raw_data)
                        releases = list(parsed_data.get("releases", {}).keys())
                        return {"releases": releases}
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from raw_data: {e}")
                        return cast(
                            ReleasesInfo,
                            format_error(
                                ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"
                            ),
                        )
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(
                        ReleasesInfo,
                        format_error(
                            ErrorCode.PARSE_ERROR,
                            f"Unexpected content type: {content_type}",
                        ),
                    )

            # Already parsed JSON data
            releases = list(data.get("releases", {}).keys())
            return {"releases": releases}
        except ValueError as e:
            return cast(ReleasesInfo, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Unexpected error getting package releases: {e}")
            return cast(ReleasesInfo, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def get_release_urls(self, package_name: str, version: str) -> UrlsInfo:
        """Get download URLs for a specific release version."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            sanitized_version = sanitize_version(version)
            url = f"https://pypi.org/pypi/{sanitized_name}/{sanitized_version}/json"

            result = await self.http.fetch(url)

            # Check for error in result
            if isinstance(result, dict) and "error" in result:
                return cast(UrlsInfo, result)

            # Handle the new format where raw data might be returned
            if isinstance(result, dict) and "raw_data" in result:
                content_type = result.get("content_type", "")
                raw_data = result["raw_data"]

                # If we got JSON content, parse it
                if "application/json" in content_type and isinstance(raw_data, str):
                    try:
                        parsed_data = json.loads(raw_data)
                        return {"urls": parsed_data["urls"]}
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"Error processing JSON from raw_data: {e}")
                        return cast(
                            UrlsInfo,
                            format_error(
                                ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"
                            ),
                        )
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(
                        UrlsInfo,
                        format_error(
                            ErrorCode.PARSE_ERROR,
                            f"Unexpected content type: {content_type}",
                        ),
                    )

            # Already parsed JSON data
            return {"urls": result["urls"]}
        except ValueError as e:
            return cast(UrlsInfo, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Unexpected error getting release URLs: {e}")
            return cast(UrlsInfo, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    def get_source_url(self, package_name: str, version: str) -> UrlResult:
        """Generate a predictable source package URL."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            sanitized_version = sanitize_version(version)

            first_letter = sanitized_name[0]
            url = f"https://files.pythonhosted.org/packages/source/{first_letter}/{sanitized_name}/{sanitized_name}-{sanitized_version}.tar.gz"

            return {"url": url}
        except ValueError as e:
            return cast(UrlResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Unexpected error generating source URL: {e}")
            return cast(UrlResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    def get_wheel_url(
        self,
        package_name: str,
        version: str,
        python_tag: str,
        abi_tag: str,
        platform_tag: str,
        build_tag: Optional[str] = None,
    ) -> UrlResult:
        """Generate a predictable wheel package URL."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            sanitized_version = sanitize_version(version)

            # Clean tags according to PEP 491
            wheel_parts = {
                "name": sanitized_name,
                "version": sanitized_version,
                "python_tag": python_tag.replace(".", "_"),
                "abi_tag": abi_tag.replace(".", "_"),
                "platform_tag": platform_tag.replace(".", "_"),
            }

            # Add build tag if provided
            build_suffix = ""
            if build_tag:
                build_suffix = f"-{build_tag.replace('.', '_')}"

            # Format wheel filename
            filename = f"{wheel_parts['name']}-{wheel_parts['version']}{build_suffix}-{wheel_parts['python_tag']}-{wheel_parts['abi_tag']}-{wheel_parts['platform_tag']}.whl"

            first_letter = sanitized_name[0]
            url = f"https://files.pythonhosted.org/packages/{wheel_parts['python_tag']}/{first_letter}/{sanitized_name}/{filename}"

            return {"url": url}
        except ValueError as e:
            return cast(UrlResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Unexpected error generating wheel URL: {e}")
            return cast(UrlResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def check_package_exists(self, package_name: str) -> ExistsResult:
        """Check if a package exists on PyPI."""
        try:
            sanitized_name = sanitize_package_name(package_name)
            url = f"https://pypi.org/pypi/{sanitized_name}/json"

            result = await self.http.fetch(url)

            # Check for error in result
            if isinstance(result, dict) and "error" in result:
                if result["error"]["code"] == ErrorCode.NOT_FOUND:
                    return {"exists": False}
                return cast(ExistsResult, result)

            # If we got a raw_data response, parse it if needed
            if isinstance(result, dict) and "raw_data" in result:
                # Simply the fact that we got a response means the package exists
                return {"exists": True}

            return {"exists": True}
        except ValueError as e:
            return cast(ExistsResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Error checking if package exists: {e}")
            return cast(ExistsResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

    async def get_package_metadata(
        self, package_name: str, version: Optional[str] = None
    ) -> MetadataResult:
        """Get detailed metadata for a package."""
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
                return cast(MetadataResult, result)

            # Handle the new format where raw data might be returned
            if isinstance(result, dict) and "raw_data" in result:
                content_type = result.get("content_type", "")
                raw_data = result["raw_data"]

                # If we got JSON content, parse it
                if "application/json" in content_type and isinstance(raw_data, str):
                    try:
                        parsed_data = json.loads(raw_data)
                        info = parsed_data.get("info", {})
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from raw_data: {e}")
                        return cast(
                            MetadataResult,
                            format_error(
                                ErrorCode.PARSE_ERROR, f"Invalid JSON response: {e}"
                            ),
                        )
                else:
                    logger.warning(f"Received non-JSON content: {content_type}")
                    return cast(
                        MetadataResult,
                        format_error(
                            ErrorCode.PARSE_ERROR,
                            f"Unexpected content type: {content_type}",
                        ),
                    )
            else:
                # Already parsed JSON data
                info = result.get("info", {})

            metadata: PackageMetadata = {
                "name": info.get("name", ""),
                "version": info.get("version", ""),
                "summary": info.get("summary", ""),
                "description": info.get("description", ""),
                "author": info.get("author", ""),
                "author_email": info.get("author_email", ""),
                "license": info.get("license", ""),
                "project_url": info.get("project_url", ""),
                "homepage": info.get("home_page", ""),
                "requires_python": info.get("requires_python", ""),
                "classifiers": info.get("classifiers", []),
                "keywords": (
                    info.get("keywords", "").split(",") if info.get("keywords") else []
                ),
            }

            return {"metadata": metadata}
        except ValueError as e:
            return cast(MetadataResult, format_error(ErrorCode.INVALID_INPUT, str(e)))
        except Exception as e:
            logger.exception(f"Error getting package metadata: {e}")
            return cast(MetadataResult, format_error(ErrorCode.UNKNOWN_ERROR, str(e)))

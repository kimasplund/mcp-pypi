"""Pydantic output schemas shared by the tools."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class VulnerabilityItem(BaseModel):
    id: str
    summary: str = ""
    severity: str | None = None
    aliases: list[str] = Field(default_factory=list)
    affected_versions: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)

    @classmethod
    def from_core(cls, v: dict) -> VulnerabilityItem:
        refs = [
            r.get("url", "") if isinstance(r, dict) else str(r) for r in v.get("references") or []
        ]
        cve = v.get("cve")
        aliases = [cve] if isinstance(cve, str) and cve else list(cve or [])
        return cls(
            id=str(v.get("id", "")),
            summary=v.get("summary") or "",
            severity=v.get("severity"),
            aliases=aliases,
            affected_versions=list(v.get("affected_versions") or []),
            references=[r for r in refs if r],
        )


class SearchHit(BaseModel):
    name: str
    version: str | None = None
    summary: str | None = None
    package_url: str
    popularity_rank: int | None = None


class SearchResults(BaseModel):
    query: str
    results: list[SearchHit] = Field(default_factory=list)
    total_candidates: int
    note: str | None = None


class PackageDetails(BaseModel):
    package_name: str
    version: str
    latest_version: str
    summary: str | None = None
    requires_python: str | None = None
    license: str | None = None
    author: str | None = None
    maintainer: str | None = None
    homepage_url: str | None = None
    documentation_url: str | None = None
    source_url: str | None = None
    changelog_url: str | None = None
    project_urls: dict[str, str] = Field(default_factory=dict)
    classifiers: list[str] = Field(default_factory=list)
    yanked: bool = False
    yanked_reason: str | None = None
    release_count: int
    latest_upload_time: str | None = None
    package_url: str


class VersionEntry(BaseModel):
    version: str
    upload_time: str | None = None
    yanked: bool = False
    yanked_reason: str | None = None
    file_types: list[str] = Field(default_factory=list)


class PackageVersions(BaseModel):
    package_name: str
    versions: list[VersionEntry] = Field(default_factory=list)
    total: int
    offset: int
    limit: int
    has_more: bool


class VersionComparison(BaseModel):
    package_name: str
    version1: str
    version2: str
    newer: Literal["version1", "version2", "equal"]
    comparison: str


class Changelog(BaseModel):
    package_name: str
    version: str | None = None
    changelog: str


class DownloadStats(BaseModel):
    package_name: str
    last_day: int | None = None
    last_week: int | None = None
    last_month: int | None = None
    source: str = "pypistats.org"


class DependencyEntry(BaseModel):
    name: str
    specifier: str = ""
    extras: list[str] = Field(default_factory=list)
    marker: str | None = None


class DependencyNode(BaseModel):
    name: str
    version: str | None = None
    cycle: bool = False
    dependencies: list[DependencyNode] = Field(default_factory=list)


DependencyNode.model_rebuild()


class Dependencies(BaseModel):
    package_name: str
    version: str | None = None
    depth: int
    dependencies: list[DependencyEntry] = Field(default_factory=list)
    tree: DependencyNode | None = None


class PackageCheck(BaseModel):
    name: str
    normalized_name: str
    exists: bool
    latest_version: str | None = None
    summary: str | None = None
    error: str | None = None


class PackageChecks(BaseModel):
    results: list[PackageCheck] = Field(default_factory=list)
    total: int
    missing: list[str] = Field(default_factory=list)


class PackageVulnerabilities(BaseModel):
    package: str
    version: str | None = None
    vulnerable: bool = False
    vulnerabilities: list[VulnerabilityItem] = Field(default_factory=list)
    introduced_via: list[str] = Field(default_factory=list)
    error: str | None = None


class VulnerabilityReport(BaseModel):
    results: list[PackageVulnerabilities] = Field(default_factory=list)
    total_packages: int
    vulnerable_packages: int
    total_vulnerabilities: int
    severity_counts: dict[str, int] = Field(default_factory=dict)
    transitive_checked: bool = False


class InstalledScan(BaseModel):
    environment_path: str | None = None
    packages_scanned: int
    vulnerable: list[PackageVulnerabilities] = Field(default_factory=list)
    all_clear: bool
    update_commands: list[str] = Field(default_factory=list)
    recommendation: str

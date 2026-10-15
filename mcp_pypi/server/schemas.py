"""Pydantic output schemas shared by the tools."""

from __future__ import annotations

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

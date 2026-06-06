from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class SkillSpec(BaseModel):
    prompt: str
    tools: list[str] = Field(default_factory=list)
    temperature: float = 0.4
    max_tokens: int = 1200
    critic: bool = False
    internal_successors: list[str] = Field(default_factory=list)


class SkillCatalog(BaseModel):
    root: Path
    skills: dict[str, SkillSpec]

    @classmethod
    def load(cls, path: str | Path) -> "SkillCatalog":
        config_path = Path(path)
        data = yaml.safe_load(config_path.read_text()) or {}
        raw_skills = data.get("skills", {})
        return cls(
            root=config_path.parent,
            skills={name: SkillSpec.model_validate(spec) for name, spec in raw_skills.items()},
        )

    def get(self, name: str) -> SkillSpec:
        try:
            return self.skills[name]
        except KeyError as exc:
            known = ", ".join(sorted(self.skills))
            raise KeyError(f"unknown skill {name!r}; known skills: {known}") from exc

    def prompt_text(self, name: str) -> str:
        spec = self.get(name)
        return (self.root / spec.prompt).read_text()


def render_prompt(
    catalog: SkillCatalog,
    skill_name: str,
    *,
    query: str,
    inputs: dict[str, Any],
    memory_hits: list[dict[str, Any]] | None = None,
) -> str:
    """Render a skill prompt for traceability.

    The deterministic demo runner does not call an LLM, but persisting this
    text keeps the same inspectable boundary the class architecture describes.
    """

    prompt = catalog.prompt_text(skill_name).strip()
    sections = [prompt, f"USER QUERY:\n{query.strip()}"]
    if memory_hits:
        hit_lines = []
        for hit in memory_hits:
            label = hit.get("source") or hit.get("id") or "memory"
            preview = str(hit.get("preview") or hit.get("text") or "")[:400]
            hit_lines.append(f"- {label}: {preview}")
        sections.append("MEMORY HITS:\n" + "\n".join(hit_lines))

    if inputs:
        rendered = []
        for key, value in inputs.items():
            rendered.append(f"{key}:\n{value}")
        sections.append("INPUTS:\n" + "\n\n".join(rendered))

    return "\n\n---\n\n".join(sections)

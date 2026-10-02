import re
from pathlib import Path

from service.config import PROJECT_ROOT


AUTHORITATIVE_SKILLS = {
    "claw-quant-data",
    "claw-quant-fundamental-research",
    "claw-quant-technical-research",
    "claw-quant-macro-research",
    "claw-quant-industry-research",
    "claw-quant-event-research",
    "claw-quant-cross-asset-research",
    "claw-quant-etf-flow-research",
}

HIBRO_SKILLS = {
    "claw-quant-data",
    "fundamental-research",
    "technical-research",
    "macro-research",
    "industry-research",
    "event-research",
    "cross-asset-research",
    "etf-flow-research",
}


def _read_skill(root: Path, name: str) -> str:
    return (root / name / "SKILL.md").read_text(encoding="utf-8")


def test_distributed_agent_skills_use_only_research_contract():
    skill_files = sorted((PROJECT_ROOT / ".agents" / "skills").glob("*/SKILL.md"))
    assert skill_files

    skills = "\n".join(path.read_text(encoding="utf-8") for path in skill_files)
    commands = re.findall(r"(?:`|^)(\./clawq [^`\n]*)", skills, flags=re.MULTILINE)

    assert commands
    assert all(
        command.startswith(
            ("./clawq research ", "./clawq stock ", "./clawq sector ")
        )
        for command in commands
    )
    assert not any(
        namespace in skills
        for namespace in ("/api/v1/data/", "/api/v1/ops/", "/api/v1/audit/")
    )


def test_authoritative_and_hibro_skill_domains_stay_aligned():
    authoritative_root = PROJECT_ROOT / ".agents" / "skills"
    hibro_root = (
        PROJECT_ROOT / "deploy" / "hibro" / "agents" / "claw-quant-research" / "skills"
    )

    assert {
        path.parent.name for path in authoritative_root.glob("*/SKILL.md")
    } == AUTHORITATIVE_SKILLS
    assert {path.parent.name for path in hibro_root.glob("*/SKILL.md")} == HIBRO_SKILLS

    for name in AUTHORITATIVE_SKILLS - {"claw-quant-data"}:
        content = _read_skill(authoritative_root, name)
        assert "./clawq research readiness" in content
        assert "./clawq research capabilities" in content


def test_research_skill_responsibilities_and_source_semantics():
    authoritative_root = PROJECT_ROOT / ".agents" / "skills"
    hibro_root = (
        PROJECT_ROOT / "deploy" / "hibro" / "agents" / "claw-quant-research" / "skills"
    )

    fundamental = _read_skill(authoritative_root, "claw-quant-fundamental-research")
    technical = _read_skill(authoritative_root, "claw-quant-technical-research")
    macro = _read_skill(authoritative_root, "claw-quant-macro-research")
    hibro_fundamental = _read_skill(hibro_root, "fundamental-research")
    hibro_technical = _read_skill(hibro_root, "technical-research")
    hibro_macro = _read_skill(hibro_root, "macro-research")

    assert "./clawq research repurchase-progress" in fundamental
    assert "./clawq research repurchase-progress" not in technical
    assert "/repurchase-progress" in hibro_fundamental
    assert "/repurchase-progress" not in hibro_technical

    for content in (macro, hibro_macro):
        assert "cn_lpr" in content
        assert "ChinaMoney" in content
        assert "shibor_lpr" in content

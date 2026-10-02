import re
from pathlib import Path

from service.config import PROJECT_ROOT


AUTHORITATIVE_SKILLS = {
    "claw-quant-data",
    "claw-quant-cross-asset-research",
    "claw-quant-disclosure-governance-research",
    "claw-quant-etf-flow-research",
    "claw-quant-event-research",
    "claw-quant-financial-quality-research",
    "claw-quant-fundamental-research",
    "claw-quant-industry-research",
    "claw-quant-levels-risk-research",
    "claw-quant-macro-research",
    "claw-quant-market-charting",
    "claw-quant-price-trend-research",
    "claw-quant-technical-research",
    "claw-quant-valuation-shareholder-research",
    "claw-quant-volume-flow-research",
    "claw-quant-wave-chan-research",
}

FUNDAMENTAL_AGENT_SKILLS = {
    "claw-quant-data",
    "disclosure-governance-research",
    "event-research",
    "financial-quality-research",
    "fundamental-research",
    "industry-research",
    "macro-research",
    "market-charting",
    "valuation-shareholder-research",
}

TECHNICAL_AGENT_SKILLS = {
    "claw-quant-data",
    "cross-asset-research",
    "etf-flow-research",
    "levels-risk-research",
    "market-charting",
    "price-trend-research",
    "technical-research",
    "volume-flow-research",
    "wave-chan-research",
}


def _read_skill(root: Path, name: str) -> str:
    return (root / name / "SKILL.md").read_text(encoding="utf-8")


def _declared_agent_skills(agent_root: Path) -> set[str]:
    manifest = (agent_root / "agent.yaml").read_text(encoding="utf-8")
    pairs = re.findall(
        r"^    - name: ([^\n]+)\n      path: skills/([^\n]+)$",
        manifest,
        flags=re.MULTILINE,
    )
    assert pairs
    assert all(name == path for name, path in pairs)
    return {name for name, _path in pairs}


def test_distributed_agent_skills_use_only_research_contract():
    skill_files = sorted((PROJECT_ROOT / ".agents" / "skills").glob("*/SKILL.md"))
    skill_files += sorted(
        (PROJECT_ROOT / "deploy" / "hibro" / "agents").glob("*/skills/*/SKILL.md")
    )
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


def test_authoritative_skills_are_packaged_by_research_agent():
    authoritative_root = PROJECT_ROOT / ".agents" / "skills"
    fundamental_agent_root = (
        PROJECT_ROOT
        / "deploy"
        / "hibro"
        / "agents"
        / "claw-quant-fundamental-research"
    )
    technical_agent_root = (
        PROJECT_ROOT
        / "deploy"
        / "hibro"
        / "agents"
        / "claw-quant-technical-research"
    )
    fundamental_root = (
        fundamental_agent_root / "skills"
    )
    technical_root = (
        technical_agent_root / "skills"
    )

    assert {
        path.parent.name for path in authoritative_root.glob("*/SKILL.md")
    } == AUTHORITATIVE_SKILLS
    assert {
        path.parent.name for path in fundamental_root.glob("*/SKILL.md")
    } == FUNDAMENTAL_AGENT_SKILLS
    assert {
        path.parent.name for path in technical_root.glob("*/SKILL.md")
    } == TECHNICAL_AGENT_SKILLS
    assert _declared_agent_skills(fundamental_agent_root) == FUNDAMENTAL_AGENT_SKILLS
    assert _declared_agent_skills(technical_agent_root) == TECHNICAL_AGENT_SKILLS

    packaged = FUNDAMENTAL_AGENT_SKILLS | TECHNICAL_AGENT_SKILLS
    expected_without_prefix = {
        name if name == "claw-quant-data" else name.removeprefix("claw-quant-")
        for name in AUTHORITATIVE_SKILLS
    }
    assert packaged == expected_without_prefix
    assert FUNDAMENTAL_AGENT_SKILLS & TECHNICAL_AGENT_SKILLS == {
        "claw-quant-data",
        "market-charting",
    }


def test_research_skill_responsibilities_and_source_semantics():
    authoritative_root = PROJECT_ROOT / ".agents" / "skills"
    fundamental_root = (
        PROJECT_ROOT
        / "deploy"
        / "hibro"
        / "agents"
        / "claw-quant-fundamental-research"
        / "skills"
    )
    technical_root = (
        PROJECT_ROOT
        / "deploy"
        / "hibro"
        / "agents"
        / "claw-quant-technical-research"
        / "skills"
    )

    valuation = _read_skill(
        authoritative_root, "claw-quant-valuation-shareholder-research"
    )
    technical = _read_skill(authoritative_root, "claw-quant-technical-research")
    macro = _read_skill(authoritative_root, "claw-quant-macro-research")
    hibro_valuation = _read_skill(
        fundamental_root, "valuation-shareholder-research"
    )
    hibro_technical = _read_skill(technical_root, "technical-research")
    hibro_macro = _read_skill(fundamental_root, "macro-research")

    assert "./clawq research repurchase-progress" in valuation
    assert "./clawq research repurchase-progress" not in technical
    assert "repurchase-progress" in hibro_valuation
    assert "/repurchase-progress" not in hibro_technical

    for content in (macro, hibro_macro):
        assert "cn_lpr" in content
        assert "ChinaMoney" in content
        assert "shibor_lpr" in content

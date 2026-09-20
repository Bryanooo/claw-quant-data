import re

from service.config import PROJECT_ROOT


def test_distributed_agent_skill_uses_only_research_contract():
    skill = (
        PROJECT_ROOT / ".agents" / "skills" / "claw-quant-data" / "SKILL.md"
    ).read_text(encoding="utf-8")
    commands = re.findall(r"`(\./clawq [^`]*)`", skill)

    assert commands
    assert all(
        command.startswith(
            ("./clawq research ", "./clawq stock ", "./clawq sector ")
        )
        for command in commands
    )
    assert "/api/v1/research/*" in skill
    assert not any(
        namespace in skill
        for namespace in ("/api/v1/data/", "/api/v1/ops/", "/api/v1/audit/")
    )

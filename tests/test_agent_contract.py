import re

from service.config import PROJECT_ROOT


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

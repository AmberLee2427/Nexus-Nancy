from nexus_nancy.config import Config
from nexus_nancy.context import build_native_openai_context, build_universal_context


def test_universal_context_keeps_text_protocol(tmp_path) -> None:
    agents = tmp_path / ".agents"
    agents.mkdir()
    (agents / "instructions.txt").write_text(
        "Tools:\n{{tools}}\n[RESPONSE]\n[/RESPONSE]\n[EOT]", encoding="utf-8"
    )
    for name in ["relay_instructions.txt", "hand-off_instructions.txt"]:
        (agents / name).write_text("template", encoding="utf-8")

    prompt = build_universal_context(Config(), tmp_path)

    assert "bash" in prompt
    assert "[RESPONSE]" in prompt
    assert "[EOT]" in prompt


def test_native_context_avoids_universal_protocol_requirements() -> None:
    prompt = build_native_openai_context(Config())

    assert "native tool-calling" in prompt
    assert "[RESPONSE]" not in prompt
    assert "[EOT]" not in prompt

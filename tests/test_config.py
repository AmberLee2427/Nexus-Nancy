from nexus_nancy.config import Config, _parse_flat_yaml, default_config_yaml


def test_default_config_exposes_conservative_route_controls() -> None:
    parsed = _parse_flat_yaml(default_config_yaml())

    assert parsed["execution_strategy"] == "auto"
    assert parsed["native_tools"] == "auto"
    assert parsed["reasoning_channel"] == "auto"
    assert parsed["parallel_tool_calls"] == "auto"
    assert parsed["capability_probe"] is True

    cfg = Config()
    assert cfg.execution_strategy == "auto"
    assert cfg.native_tools == "auto"
    assert cfg.capability_probe is True
    assert cfg.sandbox_root == "."
    assert cfg.max_attachment_bytes == 120000


def test_flat_yaml_parses_new_string_and_boolean_fields() -> None:
    parsed = _parse_flat_yaml(
        """
execution_strategy: native_openai
native_tools: true
reasoning_channel: false
parallel_tool_calls: auto
capability_probe: false
"""
    )

    assert parsed == {
        "execution_strategy": "native_openai",
        "native_tools": True,
        "reasoning_channel": False,
        "parallel_tool_calls": "auto",
        "capability_probe": False,
    }

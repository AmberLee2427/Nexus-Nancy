from nexus_nancy.capabilities import detect_capabilities
from nexus_nancy.config import Config
from nexus_nancy.execution import (
    STRATEGY_NATIVE_OPENAI,
    STRATEGY_UNIVERSAL,
    select_execution_strategy,
)


class ProbeClient:
    def __init__(self, result: bool | Exception) -> None:
        self.result = result

    def probe_native_tools(self) -> bool:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_explicit_config_override_verifies_native_support() -> None:
    cfg = Config(native_tools=True, reasoning_channel=True, parallel_tool_calls=False)

    capabilities = detect_capabilities(cfg, probe_client=ProbeClient(False))

    assert capabilities.native_tools is True
    assert capabilities.reasoning_channel is True
    assert capabilities.parallel_tool_calls is False
    assert capabilities.verified is True
    assert capabilities.source == "config override"


def test_probe_failure_falls_back_to_universal_in_auto() -> None:
    cfg = Config(capability_probe=True)

    capabilities = detect_capabilities(cfg, probe_client=ProbeClient(RuntimeError("boom")))
    selection = select_execution_strategy(cfg, capabilities)

    assert capabilities.verified is False
    assert capabilities.source == "probe failure"
    assert selection.selected == STRATEGY_UNIVERSAL


def test_auto_selects_native_when_probe_verifies_support() -> None:
    cfg = Config(capability_probe=True)

    capabilities = detect_capabilities(cfg, probe_client=ProbeClient(True))
    selection = select_execution_strategy(cfg, capabilities)

    assert capabilities.verified is True
    assert selection.selected == STRATEGY_NATIVE_OPENAI


def test_forced_native_fails_when_support_cannot_be_verified() -> None:
    cfg = Config(execution_strategy="native_openai", capability_probe=False)
    capabilities = detect_capabilities(cfg)

    try:
        select_execution_strategy(cfg, capabilities)
    except RuntimeError as exc:
        assert "requires verified native tool support" in str(exc)
    else:
        raise AssertionError("forced native should fail without verified support")

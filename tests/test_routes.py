from pathlib import Path
from typing import Any

from nexus_nancy.app import run_prompt
from nexus_nancy.capabilities import ModelCapabilities
from nexus_nancy.config import Config
from nexus_nancy.execution import STRATEGY_NATIVE_OPENAI, STRATEGY_UNIVERSAL
from nexus_nancy.sandbox import SandboxPolicy
from nexus_nancy.session import SessionState


class FakeLLM:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def chat(self, messages, tools=None, **kwargs):
        self.calls.append({"messages": list(messages), "tools": tools or [], "kwargs": kwargs})
        message = self.responses.pop(0)
        return {"choices": [{"message": message}]}


def _state(tmp_path: Path, strategy: str) -> SessionState:
    cfg = Config(
        model="test-model",
        api_key_file=str(tmp_path / "key"),
        sandbox_root=str(tmp_path),
        execution_strategy=strategy,
        native_tools=True,
    )
    state = SessionState.create(cfg, "system", tmp_path, tmp_path / "logs")
    state.execution_strategy = strategy
    state.capabilities = ModelCapabilities(
        native_tools=strategy == STRATEGY_NATIVE_OPENAI,
        parallel_tool_calls=True,
        source="test",
        verified=strategy == STRATEGY_NATIVE_OPENAI,
    )
    return state


def test_universal_route_parses_response_blocks_and_hides_private_text(tmp_path) -> None:
    state = _state(tmp_path, STRATEGY_UNIVERSAL)
    llm = FakeLLM([
        {"role": "assistant", "content": "private\n[RESPONSE]\nhello\n[/RESPONSE]\n[EOT]"}
    ])
    sandbox = SandboxPolicy(root=tmp_path, yolo=True, allowlist_substrings=[])

    result = run_prompt(state, llm, sandbox, "say hi")

    assert result.response_text == "hello"
    assert result.private_blocks == ["private"]


def test_native_route_executes_native_tool_call_and_returns_plain_response(tmp_path) -> None:
    state = _state(tmp_path, STRATEGY_NATIVE_OPENAI)
    llm = FakeLLM(
        [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "bash", "arguments": '{"command": "pwd"}'},
                    }
                ],
            },
            {"role": "assistant", "content": "done"},
        ]
    )
    sandbox = SandboxPolicy(root=tmp_path, yolo=True, allowlist_substrings=[])

    result = run_prompt(state, llm, sandbox, "run pwd")

    assert result.response_text == "done"
    assert result.tool_calls[0].status == "executed"
    assert str(tmp_path) in result.tool_calls[0].output
    assert llm.calls[0]["kwargs"]["parallel_tool_calls"] is True


def test_native_route_raw_json_function_call_safety_net(tmp_path) -> None:
    state = _state(tmp_path, STRATEGY_NATIVE_OPENAI)
    llm = FakeLLM(
        [
            {"role": "assistant", "content": '{"name":"bash","arguments":{"command":"pwd"}}'},
            {"role": "assistant", "content": "done"},
        ]
    )
    sandbox = SandboxPolicy(root=tmp_path, yolo=True, allowlist_substrings=[])

    result = run_prompt(state, llm, sandbox, "run pwd")

    assert result.response_text == "done"
    assert result.tool_calls[0].name == "bash"
    assert result.private_blocks == ['{"name":"bash","arguments":{"command":"pwd"}}']


def test_native_route_malformed_tool_args_are_recorded(tmp_path) -> None:
    state = _state(tmp_path, STRATEGY_NATIVE_OPENAI)
    llm = FakeLLM(
        [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_bad",
                        "type": "function",
                        "function": {"name": "bash", "arguments": "{bad json"},
                    }
                ],
            },
            {"role": "assistant", "content": "done"},
        ]
    )
    sandbox = SandboxPolicy(root=tmp_path, yolo=True, allowlist_substrings=[])

    result = run_prompt(state, llm, sandbox, "run malformed")

    assert result.response_text == "done"
    assert result.tool_calls[0].status == "error"
    assert "not valid JSON" in result.tool_calls[0].output

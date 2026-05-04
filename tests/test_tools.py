import unittest.mock as mock
from pathlib import Path

from nexus_nancy.tools import ToolDefinition, ToolRegistry


def test_registry_loads_core_tools():
    registry = ToolRegistry()
    assert registry.get("bash") is not None
    assert registry.get("notebook_read") is not None

def test_registry_loads_local_tools(tmp_path):
    # Setup a mock local tool
    tools_dir = tmp_path / ".agents" / "tools"
    tools_dir.mkdir(parents=True)
    tool_file = tools_dir / "test_tool.py"
    tool_file.write_text("""
from nexus_nancy.tools import ToolDefinition
def my_handler(**kwargs): return "ok"
def register_tools():
    return [ToolDefinition(name="test_tool", description="desc", parameters={}, handler=my_handler)]
""", encoding="utf-8")

    registry = ToolRegistry()
    registry.load_plugins(tmp_path)

    assert registry.get("test_tool") is not None
    assert registry.get("test_tool").description == "desc"

def test_registry_executes_plugin_handler():
    registry = ToolRegistry()
    mock_handler = mock.Mock(return_value="success")
    registry.register(
        ToolDefinition(name="plug", description="d", parameters={}, handler=mock_handler)
    )

    from nexus_nancy.sandbox import SandboxPolicy
    from nexus_nancy.tools import execute_tool

    # Use a dummy sandbox
    sandbox = SandboxPolicy(Path("/tmp"), [])

    # We need to monkeypatch the global REGISTRY for execute_tool
    with mock.patch("nexus_nancy.tools.REGISTRY", registry):
        result = execute_tool("plug", {}, sandbox)
        assert result == "success"
        mock_handler.assert_called_once()

def test_registry_loads_entry_points():
    mock_ep = mock.Mock()
    mock_ep.name = "mock_plugin"
    mock_plugin_mod = mock.Mock()
    mock_plugin_mod.register_tools.return_value = [
        ToolDefinition(name="ep_tool", description="ep", parameters={})
    ]
    mock_ep.load.return_value = mock_plugin_mod

    with mock.patch("importlib.metadata.entry_points") as mock_eps:
        mock_eps.return_value = [mock_ep]

        registry = ToolRegistry()
        registry._load_entry_points()

        assert registry.get("ep_tool") is not None

from ai_os.ai_os_core import parse_tool_call, system_prompt


def test_system_prompt_limits_tools_to_the_registry() -> None:
    prompt = system_prompt({"get_hardware_stats", "run_command"})

    assert "get_hardware_stats, run_command" in prompt
    assert "Never invent a tool name" in prompt


def test_tool_call_requires_string_tool_and_object_arguments() -> None:
    assert parse_tool_call('{"tool": "get_hardware_stats", "arguments": {}}') == {
        "tool": "get_hardware_stats",
        "arguments": {},
    }
    assert parse_tool_call('{"tool": ["not-a-tool"], "arguments": {}}') is None
    assert parse_tool_call('{"tool": "get_hardware_stats", "arguments": []}') is None

"""Claude Agent SDK on the local Claude Code login (B-00 spike settings; no ANTHROPIC_API_KEY)."""

import json
from collections.abc import AsyncIterator

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from deployar.llm.client import Done, LLMEvent, TextDelta, ToolResult, ToolUse
from deployar.runtime.gate import CanUseTool
from deployar.tools.registry import SERVER, Registry, ToolContext

BUILTINS = ["Bash", "Read", "Write", "Edit", "WebFetch", "WebSearch", "Glob", "Grep", "Task", "NotebookEdit"]


def _status(block: ToolResultBlock) -> str:
    text = block.content if isinstance(block.content, str) else "".join(
        c.get("text", "") for c in (block.content or []) if isinstance(c, dict)
    )  # fmt: skip
    try:
        return str(json.loads(text).get("status", "ok"))
    except (ValueError, AttributeError):
        return "error" if block.is_error else "ok"


class ClaudeBackend:
    async def run(
        self,
        *,
        prompt: str,
        system_prompt: str,
        registry: Registry,
        tool_ctx: ToolContext,
        can_use_tool: CanUseTool,
        max_turns: int,
        resume: str | None = None,
    ) -> AsyncIterator[LLMEvent]:
        options = ClaudeAgentOptions(
            mcp_servers={SERVER: registry.sdk_server(tool_ctx)},
            strict_mcp_config=True,
            tools=[],
            allowed_tools=registry.allowed_tools(),
            disallowed_tools=BUILTINS,
            setting_sources=[],
            can_use_tool=can_use_tool,
            system_prompt=system_prompt,
            max_turns=max_turns,
            resume=resume,
        )
        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock) and block.text:
                            yield TextDelta(block.text)
                        elif isinstance(block, ToolUseBlock):
                            yield ToolUse(block.id, block.name, block.input)
                elif isinstance(msg, UserMessage) and isinstance(msg.content, list):
                    for block in msg.content:
                        if isinstance(block, ToolResultBlock):
                            yield ToolResult(block.tool_use_id, _status(block))
                elif isinstance(msg, ResultMessage):
                    yield Done(msg.session_id, msg.is_error, msg.result if msg.is_error else None)

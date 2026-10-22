# /// script
# requires-python = ">=3.13"
# dependencies = ["claude-agent-sdk==0.2.172"]
# ///
"""B-00 spike: Agent SDK on the local Claude Code login, in-process MCP, can_use_tool gate.

Run: env -u ANTHROPIC_API_KEY uv run spikes/b00_sdk.py
Throwaway; kept for reference. Findings in docs/evidence/B-00/notes.md.
"""

import asyncio
import os
import sys
import time
from collections import Counter
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    SystemMessage,
    ToolPermissionContext,
    ToolUseBlock,
    create_sdk_mcp_server,
    tool,
)
from claude_agent_sdk import __version__ as sdk_version

T0 = time.monotonic()


def log(msg: str) -> None:
    print(f"[{time.monotonic() - T0:7.2f}s] {msg}", flush=True)


@tool("echo", "Return the given text unchanged. Risk: read.", {"text": str})
async def echo(args: dict[str, Any]) -> dict[str, Any]:
    log(f"TOOL echo ran: {args['text']!r}")
    return {"content": [{"type": "text", "text": args["text"]}]}


@tool("danger", "Pretend to restart an app. Risk: sensitive, needs human approval.", {"target": str})
async def danger(args: dict[str, Any]) -> dict[str, Any]:
    log(f"TOOL danger ran on {args['target']!r}")
    return {"content": [{"type": "text", "text": f"restarted {args['target']} (fake)"}]}


RISK = {"mcp__hamkar__echo": "read", "mcp__hamkar__danger": "sensitive"}


async def read_answer(event: asyncio.Event, box: list[str]) -> None:
    # Stand-in for the approval API: anything that sets the Event releases the gate.
    line = await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readline)
    box.append(line.strip().lower())
    event.set()


async def gate(name: str, args: dict[str, Any], ctx: ToolPermissionContext) -> Any:
    risk = RISK.get(name)
    log(f"GATE {name} risk={risk} args={args}")
    if risk == "read":
        return PermissionResultAllow()
    if risk != "sensitive":
        return PermissionResultDeny(message=f"{name} is not a hamkar tool")
    event, box = asyncio.Event(), []
    asyncio.create_task(read_answer(event, box))
    print(f">>> approve {name} {args}? [y/n] ", end="", flush=True)
    await event.wait()
    log(f"GATE answer={box[0]!r}")
    if box[0] == "y":
        return PermissionResultAllow()
    return PermissionResultDeny(message="Mohammad denied this action.")


TURNS = [
    "Call the echo tool with text 'salam hamkar'. Reply with one short line.",
    "Call the danger tool with target 'demo-app'. Reply with one short line saying what happened.",
    "Call the danger tool again with target 'demo-app-2'. Reply with one short line saying what happened.",
    "Run the shell command `ls /` using the Bash tool. If you cannot, say so in one line.",
]


async def main() -> None:
    assert "ANTHROPIC_API_KEY" not in os.environ, "unset ANTHROPIC_API_KEY: this spike proves the login path"
    log(f"claude-agent-sdk {sdk_version}")
    server = create_sdk_mcp_server("hamkar", tools=[echo, danger])
    options = ClaudeAgentOptions(
        mcp_servers={"hamkar": server},
        strict_mcp_config=True,
        tools=[],  # no built-in tools at all
        # Only read tools here: a whole-tool allow (or "mcp__hamkar__*") skips can_use_tool.
        allowed_tools=["mcp__hamkar__echo"],
        disallowed_tools=["Bash", "Read", "Write", "Edit", "WebFetch", "WebSearch"],
        setting_sources=[],
        can_use_tool=gate,
        system_prompt="You are a test agent. Use only the tools you are given. Be brief.",
        max_turns=6,
    )
    types: Counter[str] = Counter()
    async with ClaudeSDKClient(options=options) as client:
        for i, prompt in enumerate(TURNS, 1):
            log(f"TURN {i} >>> {prompt}")
            start, first = time.monotonic(), None
            await client.query(prompt)
            async for msg in client.receive_response():
                first = first or time.monotonic()
                types[type(msg).__name__] += 1
                if isinstance(msg, SystemMessage) and msg.subtype == "init":
                    d = msg.data
                    log(f"INIT apiKeySource={d.get('apiKeySource')} model={d.get('model')} "
                        f"cli={d.get('claude_code_version')} tools={d.get('tools')}")
                elif isinstance(msg, AssistantMessage):
                    for b in msg.content:
                        types[type(b).__name__] += 1
                        if isinstance(b, ToolUseBlock):
                            log(f"MODEL tool_use {b.name} {b.input}")
                        elif hasattr(b, "text"):
                            log(f"MODEL text: {b.text}")
                elif isinstance(msg, ResultMessage):
                    log(f"RESULT turn {i}: {msg.subtype} error={msg.is_error} "
                        f"first_msg={first - start:.2f}s total={time.monotonic() - start:.2f}s "
                        f"api={msg.duration_api_ms}ms cost=${msg.total_cost_usd}")
    log(f"MESSAGE TYPES {dict(types)}")


if __name__ == "__main__":
    asyncio.run(main())

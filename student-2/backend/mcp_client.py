import asyncio
import json
import os

from mcp import Client


MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    "http://host.docker.internal:5700/mcp"
)


async def _call_mcp_tool(tool_name, arguments=None):
    async with Client(MCP_SERVER_URL) as client:

        result = await client.call_tool(
            tool_name,
            arguments=arguments or {}
        )

        if result.is_error:
            error_messages = [
                item.text
                for item in result.content
                if hasattr(item, "text")
            ]

            raise RuntimeError(
                " ".join(error_messages)
                or "MCP tool call failed."
            )

        if result.structured_content is not None:
            return result.structured_content

        for item in result.content:
            if hasattr(item, "text"):
                try:
                    return json.loads(item.text)
                except json.JSONDecodeError:
                    continue

        raise RuntimeError(
            "MCP tool returned no valid JSON result."
        )


def call_mcp_tool(tool_name, arguments=None):
    return asyncio.run(
        _call_mcp_tool(tool_name, arguments)
    )
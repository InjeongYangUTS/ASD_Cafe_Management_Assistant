import asyncio 
import json 
import os
import sys 

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client 

MCP_SERVER_PATH = os.getenv(
    "MCP_SERVER_PATH",
    "ai-service/mcp-server/server.py"
)

async def _call_mcp_tool(tool_name, arguments = None):
    server_params = StdioServerParameters(
        command = sys.executable,
        args = [MCP_SERVER_PATH],
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            result = await session.call_tool(
                tool_name,
                arguments = arguments or {}
            )
            
            if result.isError:
                error_messages = [
                    item.text 
                    for item in result.content 
                    if hasattr(item, "text")
                ]
                
                raise RuntimeError(
                    " ".join(error_messages)
                    or "MCP tool call failed."
                ) 
                
            if result.structuredContent is not None:
                return result.structuredContent
            
            for item in result.content:
                if hasattr(item, "text"):
                    try:
                        return json.loads(item.text)
                    except json.JSONDecodeError:
                        continue
                    
            raise RuntimeError(
                "MCP tool returned no valid JSON result."
            )
        
def call_mcp_tool(tool_name, arguments = None):
    return asyncio.run(
        _call_mcp_tool(tool_name, arguments)
    )
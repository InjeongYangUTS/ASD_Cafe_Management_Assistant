import asyncio 
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
            
            # Connect to MCP server
            await session.initialize()
            
            # Call MCP tool
            result = await session.call_tool(
                tool_name,
                arguments = arguments or {}
            )
            
            return result 
        
def call_mcp_tool(tool_name, arguments = None):
    return asyncio.run(
        _call_mcp_tool(tool_name, arguments)
    )
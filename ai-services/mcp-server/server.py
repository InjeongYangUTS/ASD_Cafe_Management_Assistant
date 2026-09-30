from mcp.server.mcpserver import MCPServer

from tools.student1_tools import register_student1_tools
from tools.student3_tools import register_student3_tools

mcp = MCPServer("Cafe Management Assistant MCP")

# Student 1, Customer Feedback & Reviews
register_student1_tools(mcp)

# Student 3, Inventory & Restocking
register_student3_tools(mcp)

if __name__ == "__main__" :
    mcp.run(
        transport = "streamable-http",
        host = "0.0.0.0",
        port = 5700
    ) 
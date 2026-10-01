from mcp.server.mcpserver import MCPServer

from tools.student2_tools import register_student2_tools
from tools.student3_tools import register_student3_tools
from tools.student4_tools import register_student4_tools 

mcp = MCPServer("Cafe Management Assistant MCP")

# Student 2, Menu & Recipe Management
register_student2_tools(mcp)

# Student 3, Inventory & Restocking
register_student3_tools(mcp)

# Student 4, Order & Kitchen Management
register_student4_tools(mcp)

if __name__ == "__main__" :
    mcp.run(
        transport = "streamable-http",
        host = "0.0.0.0",
        port = 5700
    ) 
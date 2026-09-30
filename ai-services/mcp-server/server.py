from mcp.server.fastmcp import FastMCP

from tools.student3_tools import register_student3_tools 

mcp = FastMCP("Cafe Management Assistant MCP")

# Student 3, Inventory & Restocking
register_student3_tools(mcp)

if __name__ == "__main__" :
    mcp.run() 
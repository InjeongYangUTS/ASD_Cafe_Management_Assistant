from mcp.server.mcpserver import MCPServer
from starlette.responses import JSONResponse

from tools.student1_tools import register_student1_tools
from tools.student2_tools import register_student2_tools
from tools.student3_tools import register_student3_tools
from tools.student4_tools import register_student4_tools 
from tools.student5_tools import register_student5_tools

mcp = MCPServer("Cafe Management Assistant MCP")


@mcp.custom_route("/health", methods=["GET"])
async def health(_request):
    """Health endpoint required by the Release 1 integration contract."""
    return JSONResponse({"status": "ok", "service": "shared-mcp"})

# Student 1, Customer Feedback & Reviews
register_student1_tools(mcp)

# Student 2, Menu & Recipe Management
register_student2_tools(mcp)

# Student 3, Inventory & Restocking
register_student3_tools(mcp)

# Student 4, Order & Kitchen Management
register_student4_tools(mcp)

# Student 5, Payment & Billing Management
register_student5_tools(mcp)

if __name__ == "__main__" :
    mcp.run(
        transport = "streamable-http",
        host = "0.0.0.0",
        port = 5700
    ) 

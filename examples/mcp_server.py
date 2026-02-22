import asyncio
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("demo")


@mcp.tool()
async def analyze_data(query: str) -> str:
    await asyncio.sleep(2)  # simulate long work
    return f"Analysis result for: {query}"


if __name__ == "__main__":
    mcp.run()

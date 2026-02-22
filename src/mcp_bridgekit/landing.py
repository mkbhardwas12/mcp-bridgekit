from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def landing():
    return """
    <html>
    <head><title>MCP BridgeKit</title>
    <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-zinc-950 text-white">
        <div class="max-w-4xl mx-auto text-center py-20">
            <h1 class="text-6xl font-bold mb-6">MCP BridgeKit</h1>
            <p class="text-2xl mb-10">The embeddable bridge that lets web chatbots talk to stdio MCP tools.<br>Survives 30s timeouts.</p>
            <a href="/dashboard" class="bg-emerald-500 hover:bg-emerald-600 px-10 py-4 rounded-xl text-xl font-semibold">Open Dashboard →</a>
            <p class="mt-8 text-zinc-500">or <a href="https://vercel.com/new/clone?repository-url=https://github.com/mkbhardwas12/mcp-bridgekit" class="underline">Deploy your own on Vercel (free)</a></p>
        </div>
    </body>
    </html>
    """

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
            <p class="text-2xl mb-4">The embeddable bridge that lets web chatbots talk to stdio MCP tools.</p>
            <p class="text-lg text-zinc-400 mb-10">Per-user session pooling • Real timeout handling • Background job queue • Live dashboard</p>
            <div class="flex gap-4 justify-center">
                <a href="/dashboard" class="bg-emerald-500 hover:bg-emerald-600 px-10 py-4 rounded-xl text-xl font-semibold">Open Dashboard →</a>
                <a href="/architecture" class="bg-zinc-800 hover:bg-zinc-700 px-10 py-4 rounded-xl text-xl font-semibold border border-zinc-700">Architecture →</a>
                <a href="/docs" class="bg-zinc-800 hover:bg-zinc-700 px-10 py-4 rounded-xl text-xl font-semibold border border-zinc-700">API Docs →</a>
            </div>
            <p class="mt-10 text-zinc-600 text-sm">v0.9.0 • Deploy with Docker or run locally</p>
        </div>
    </body>
    </html>
    """

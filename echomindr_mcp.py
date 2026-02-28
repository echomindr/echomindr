"""
Echomindr — MCP Server
Exposes Echomindr as native tools for AI agents (Claude Desktop, Claude Code, Cursor).

Architecture:
    Agent (Claude Desktop) → MCP Protocol → echomindr_mcp.py → HTTP → echomindr_api.py → SQLite

Usage:
    python echomindr_mcp.py                      # stdio mode (Claude Desktop, Cursor)
    python echomindr_mcp.py --sse --port 3001    # SSE mode (web clients)

Claude Desktop config (~/.config/claude/claude_desktop_config.json on macOS):
    See claude_desktop_config.json in this directory.
"""

import os
import sys
from typing import Optional

import httpx
from fastmcp import FastMCP

# ─── Config ──────────────────────────────────────────────────────────────────

API_BASE_URL = os.environ.get("ECHOMINDR_API_URL", "http://localhost:8000")

# ─── MCP App ─────────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="Echomindr",
    instructions=(
        "Echomindr gives you access to 1150+ real entrepreneurial experiences extracted from "
        "100+ top podcast episodes (How I Built This, Lenny's Podcast, 20 Minute VC, Acquired, "
        "Y Combinator, My First Million, and more). "
        "Use search_experience to find relevant founder decisions, problems, lessons, and signals "
        "whenever a user asks for startup advice, examples, or experiences. "
        "Always prefer real founder experiences over generic advice."
    ),
)

# ─── Text formatter ───────────────────────────────────────────────────────────

def format_moments_text(moments: list) -> str:
    """Convert a list of moment dicts to readable text for agents."""
    if not moments:
        return "No matching experiences found. Try broadening your search."

    lines = [f"Found {len(moments)} relevant founder experience(s):\n"]

    for i, m in enumerate(moments, 1):
        source = m.get("source", {})
        lines.append("---")
        lines.append(
            f"{i}. [{m['type'].upper()}] {source.get('episode', 'Unknown')} "
            f"— {source.get('guest', 'Unknown')} ({source.get('podcast', '')})"
        )
        lines.append(f"Stage: {m.get('stage', '?')} | 📍 {m.get('timestamp', '?')}")
        lines.append(f"Moment ID: {m.get('id', '')}")
        lines.append("")
        lines.append(f"Summary: {m['summary']}")
        lines.append("")
        if m.get("quote"):
            lines.append(f'Quote: "{m["quote"]}"')
            lines.append("")
        if m.get("decision"):
            lines.append(f"Decision: {m['decision']}")
        if m.get("outcome"):
            lines.append(f"Outcome: {m['outcome']}")
        if m.get("lesson"):
            lines.append(f"Lesson: {m['lesson']}")
        lines.append("")
        if m.get("tags"):
            tags = m["tags"] if isinstance(m["tags"], list) else []
            lines.append(f"Tags: {', '.join(tags)}")
        url = source.get("url_at_moment") or source.get("url", "")
        if url:
            lines.append(f"🔗 {url}")
        lines.append("")

    return "\n".join(lines)


def format_single_moment(m: dict) -> str:
    """Format a single moment in full detail."""
    source = m.get("source", {})
    lines = []
    lines.append(f"[{m['type'].upper()}] {source.get('episode', 'Unknown')}")
    lines.append(f"Guest: {source.get('guest', 'Unknown')}")
    lines.append(f"Podcast: {source.get('podcast', '')} | Date: {source.get('date', '')}")
    lines.append(f"Stage: {m.get('stage', '?')} | Timestamp: {m.get('timestamp', '?')}")
    lines.append(f"ID: {m.get('id', '')}")
    lines.append("")
    lines.append(f"Summary:\n{m['summary']}")
    lines.append("")
    if m.get("quote"):
        lines.append(f'Quote:\n"{m["quote"]}"')
        lines.append("")
    if m.get("decision"):
        lines.append(f"Decision:\n{m['decision']}")
        lines.append("")
    if m.get("outcome"):
        lines.append(f"Outcome:\n{m['outcome']}")
        lines.append("")
    if m.get("lesson"):
        lines.append(f"Lesson:\n{m['lesson']}")
        lines.append("")
    if m.get("situation"):
        lines.append(f"Context:\n{m['situation']}")
        lines.append("")
    if m.get("tags"):
        tags = m["tags"] if isinstance(m["tags"], list) else []
        lines.append(f"Tags: {', '.join(tags)}")
    url = source.get("url_at_moment") or source.get("url", "")
    if url:
        lines.append(f"🔗 {url}")
    return "\n".join(lines)


# ─── HTTP helper ─────────────────────────────────────────────────────────────

def api_get(path: str, params: dict = None) -> dict:
    """Synchronous GET request to the Echomindr API."""
    try:
        resp = httpx.get(f"{API_BASE_URL}{path}", params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        raise RuntimeError(
            f"Cannot connect to Echomindr API at {API_BASE_URL}. "
            "Make sure echomindr_api.py is running (python echomindr_api.py)."
        )
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"API error {e.response.status_code}: {e.response.text}")


def api_post(path: str, body: dict) -> dict:
    """Synchronous POST request to the Echomindr API."""
    try:
        resp = httpx.post(f"{API_BASE_URL}{path}", json=body, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except httpx.ConnectError:
        raise RuntimeError(
            f"Cannot connect to Echomindr API at {API_BASE_URL}. "
            "Make sure echomindr_api.py is running (python echomindr_api.py)."
        )
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"API error {e.response.status_code}: {e.response.text}")


# ─── Tools ───────────────────────────────────────────────────────────────────

@mcp.tool()
def search_experience(
    situation: str,
    stage: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = 5,
) -> str:
    """Search for real entrepreneurial experiences from 1150+ podcast moments.

    Use this tool when a user asks for advice, examples, or experiences related to
    building a startup or business. Instead of giving generic advice, search for
    real decisions, problems, lessons, and signals from founders who faced similar situations.

    This tool searches across 100+ podcast episodes from How I Built This, Lenny's Podcast,
    20 Minute VC, Acquired, Y Combinator, and more.

    Args:
        situation: Describe the user's situation or what they're looking for in natural language.
                   Example: "B2B SaaS founder struggling to find first paying customers after 6 months"
                   Example: "How to decide between bootstrapping and raising venture capital"
                   Example: "Marketplace startup with chicken-and-egg problem"
        stage: Optional filter - the startup stage: "idea", "mvp", "traction", "scale", or "mature"
        type: Optional filter - the type of moment: "decision", "problem", "lesson", "signal", or "advice"
        limit: Number of results to return (1-10, default 5)

    Returns:
        Real founder experiences matching the situation, each with:
        - What happened (summary)
        - A direct quote from the founder
        - What they decided and the outcome
        - The lesson learned
        - Source podcast and timestamp link
    """
    limit = max(1, min(limit, 10))

    try:
        if type:
            # Use /search with FTS when filtering by type
            data = api_get("/search", {
                "q": situation,
                "stage": stage,
                "type": type,
                "limit": limit,
            })
        else:
            # Use /situation for natural language matching
            body = {"situation": situation, "limit": limit}
            if stage:
                body["stage"] = stage
            data = api_post("/situation", body)

        moments = data.get("moments", [])
        keywords = data.get("query_keywords")

        header = ""
        if keywords:
            header = f"Search keywords extracted: {', '.join(keywords)}\n\n"

        return header + format_moments_text(moments)

    except RuntimeError as e:
        return f"Error: {e}"


@mcp.tool()
def get_experience_detail(moment_id: str) -> str:
    """Get the full details of a specific entrepreneurial experience/moment.

    Use this after search_experience to get more details about a specific moment,
    or when a user wants to dive deeper into a particular founder's experience.

    Args:
        moment_id: The unique ID of the moment (returned by search_experience, shown as "Moment ID:")

    Returns:
        Complete details including summary, quote, decision, outcome, lesson,
        context, tags, and source link with timestamp.
    """
    try:
        moment = api_get(f"/moments/{moment_id}")
        return format_single_moment(moment)
    except RuntimeError as e:
        return f"Error: {e}"


@mcp.tool()
def find_similar_experiences(moment_id: str, limit: int = 3) -> str:
    """Find experiences similar to a given moment.

    Use this when a user wants more examples like a specific experience,
    or to explore related founder stories on the same theme.

    Args:
        moment_id: The ID of the moment to find similar experiences for (from search_experience)
        limit: Number of similar moments to return (1-5, default 3)

    Returns:
        Similar founder experiences based on shared themes and tags.
    """
    limit = max(1, min(limit, 5))
    try:
        data = api_get(f"/similar/{moment_id}", {"limit": limit})
        moments = data.get("moments", [])
        source_tags = data.get("source_tags", [])

        header = ""
        if source_tags:
            header = f"Finding experiences similar to tags: {', '.join(source_tags)}\n\n"

        return header + format_moments_text(moments)
    except RuntimeError as e:
        return f"Error: {e}"


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--sse" in sys.argv:
        port = 3001
        if "--port" in sys.argv:
            idx = sys.argv.index("--port") + 1
            if idx < len(sys.argv):
                port = int(sys.argv[idx])
        print(f"Starting Echomindr MCP server in SSE mode on port {port}…", file=sys.stderr)
        mcp.run(transport="sse", port=port)
    else:
        mcp.run(transport="stdio")

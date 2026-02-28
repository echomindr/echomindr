"""
Echomindr — FastAPI REST API
Serve decisional moments extracted from podcasts.

Usage:
    python echomindr_api.py
    # API on http://localhost:8000
    # Swagger docs on http://localhost:8000/docs
"""

import json
import logging
import os
import re
import sqlite3
import threading
import time
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

# ─── Config ──────────────────────────────────────────────────────────────────

DB_PATH = os.environ.get("ECHOMINDR_DB", os.path.join(os.path.dirname(__file__), "echomindr.db"))
LOGS_DB_PATH = os.environ.get("ECHOMINDR_LOGS_DB", os.path.join(os.path.dirname(__file__), "echomindr_logs.db"))
HOST = os.environ.get("ECHOMINDR_HOST", "0.0.0.0")
PORT = int(os.environ.get("ECHOMINDR_PORT", "8000"))
ADMIN_TOKEN = os.environ.get("ECHOMINDR_ADMIN_TOKEN", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("echomindr")

# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Echomindr API",
    description="Structured entrepreneurial experiences extracted from 100+ top podcasts. Real decisions, problems, lessons and signals from founders — searchable by AI agents.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── DB helper ────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

# ─── Logs DB ──────────────────────────────────────────────────────────────────

def init_logs_db():
    conn = sqlite3.connect(LOGS_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS request_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT (datetime('now')),
            endpoint TEXT,
            method TEXT,
            query TEXT,
            filters TEXT,
            results_count INTEGER,
            ip TEXT,
            user_agent TEXT,
            response_time_ms INTEGER
        )
    """)
    conn.commit()
    conn.close()

def _write_log(endpoint, method, query, filters, results_count, ip, user_agent, response_time_ms):
    try:
        conn = sqlite3.connect(LOGS_DB_PATH)
        conn.execute(
            """INSERT INTO request_logs
               (endpoint, method, query, filters, results_count, ip, user_agent, response_time_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (endpoint, method, query, json.dumps(filters) if filters else None,
             results_count, ip, user_agent, response_time_ms)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("Log write failed: %s", e)

def log_entry(endpoint, method, query, filters, results_count, ip, user_agent, response_time_ms):
    """Fire-and-forget log write — does not block the response."""
    threading.Thread(
        target=_write_log,
        args=(endpoint, method, query, filters, results_count, ip, user_agent, response_time_ms),
        daemon=True,
    ).start()

init_logs_db()

# ─── Moment formatter ─────────────────────────────────────────────────────────

def format_moment(row) -> dict:
    return {
        "id": row["id"],
        "type": row["type"],
        "timestamp": row["timestamp"],
        "summary": row["summary"],
        "quote": row["quote"],
        "decision": row["decision"],
        "outcome": row["outcome"],
        "lesson": row["lesson"],
        "stage": row["stage"],
        "situation": row["situation"],
        "tags": json.loads(row["tags"]) if row["tags"] else [],
        "source": {
            "podcast": row["podcast"],
            "episode": row["episode"],
            "guest": row["guest"],
            "date": row["episode_date"],
            "url": row["source_url"],
            "url_at_moment": row["url_at_moment"],
        },
    }

# ─── Stopwords ────────────────────────────────────────────────────────────────

STOPWORDS = {
    "i", "im", "my", "me", "we", "our", "a", "an", "the", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do",
    "does", "did", "will", "would", "could", "should", "may", "might",
    "shall", "can", "need", "dare", "ought", "used", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "out",
    "off", "over", "under", "again", "further", "then", "once", "here",
    "there", "when", "where", "why", "how", "all", "both", "each",
    "few", "more", "most", "other", "some", "such", "no", "nor", "not",
    "only", "own", "same", "so", "than", "too", "very", "just", "don",
    "dont", "t", "s", "and", "but", "or", "if", "about", "it", "its",
    "that", "this", "what", "which", "who", "whom", "these", "those",
    "am", "been", "having", "doing", "because", "until", "while",
    "up", "down", "whether", "considering", "sure", "really", "think",
    "know", "like", "want", "get", "got", "going", "after",
}


def extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from free text, removing stopwords."""
    words = re.findall(r"[a-zA-Z']{3,}", text.lower())
    keywords = [w.strip("'") for w in words if w not in STOPWORDS and len(w) >= 3]
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
    return unique


# ─── Pydantic models ─────────────────────────────────────────────────────────

class Source(BaseModel):
    podcast: Optional[str] = None
    episode: Optional[str] = None
    guest: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None
    url_at_moment: Optional[str] = None

class Moment(BaseModel):
    id: str
    type: str = Field(description="decision | problem | lesson | signal | advice")
    timestamp: Optional[str] = None
    summary: str
    quote: Optional[str] = None
    decision: Optional[str] = None
    outcome: Optional[str] = None
    lesson: Optional[str] = None
    stage: Optional[str] = Field(None, description="idea | mvp | traction | scale | mature")
    situation: Optional[str] = None
    tags: list[str] = []
    source: Source = Field(default_factory=Source)

class SearchResponse(BaseModel):
    query: str
    filters: dict = {}
    count: int
    moments: list[Moment]

class SituationRequest(BaseModel):
    situation: str = Field(description="Describe the user's situation in natural language")
    stage: Optional[str] = Field(None, description="idea | mvp | traction | scale | mature")
    limit: int = Field(5, ge=1, le=20)

class SituationResponse(BaseModel):
    situation: str
    query_keywords: list[str]
    stage_filter: Optional[str] = None
    count: int
    moments: list[Moment]

class StatsResponse(BaseModel):
    total_moments: int
    by_type: dict[str, int]
    by_stage: dict[str, int]
    podcasts: int
    guests: int
    unique_tags: int

class SimilarResponse(BaseModel):
    source_id: str
    source_tags: list[str] = []
    count: int
    moments: list[Moment]


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/stats", response_model=StatsResponse, tags=["Meta"], summary="Database statistics")
def stats():
    """Return aggregate statistics about the moments database."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM moments")
    total = cur.fetchone()[0]

    cur.execute("SELECT type, COUNT(*) as n FROM moments GROUP BY type ORDER BY n DESC")
    by_type = {r["type"]: r["n"] for r in cur.fetchall()}

    cur.execute("SELECT stage, COUNT(*) as n FROM moments WHERE stage IS NOT NULL GROUP BY stage ORDER BY n DESC")
    by_stage = {r["stage"]: r["n"] for r in cur.fetchall()}

    cur.execute("SELECT COUNT(DISTINCT podcast) FROM moments")
    n_podcasts = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT guest) FROM moments WHERE guest IS NOT NULL AND guest != ''")
    n_guests = cur.fetchone()[0]

    # Unique tags: parse all JSON arrays
    cur.execute("SELECT tags FROM moments WHERE tags IS NOT NULL AND tags != '[]'")
    all_tags: set[str] = set()
    for row in cur.fetchall():
        try:
            all_tags.update(json.loads(row["tags"]))
        except Exception:
            pass

    conn.close()
    log.info("GET /stats → total=%d", total)

    return {
        "total_moments": total,
        "by_type": by_type,
        "by_stage": by_stage,
        "podcasts": n_podcasts,
        "guests": n_guests,
        "unique_tags": len(all_tags),
    }


@app.get("/search", response_model=SearchResponse, tags=["Search"], summary="Search moments by keywords")
def search(
    request: Request,
    q: str = Query(..., description="Keywords to search for"),
    stage: Optional[str] = Query(None, description="Filter by stage: idea, mvp, traction, scale, mature"),
    type: Optional[str] = Query(None, description="Filter by type: decision, problem, lesson, signal, advice"),
    podcast: Optional[str] = Query(None, description="Filter by podcast name (partial match)"),
    limit: int = Query(5, ge=1, le=20, description="Number of results (max 20)"),
):
    """Full-text search across moments with optional filters."""
    t0 = time.time()
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query 'q' cannot be empty")

    # Sanitize FTS query: wrap in quotes if it contains special chars, else pass as-is
    fts_query = q.strip()

    filters: list[str] = []
    params: list = [fts_query]

    if stage:
        filters.append("m.stage = ?")
        params.append(stage)
    if type:
        filters.append("m.type = ?")
        params.append(type)
    if podcast:
        filters.append("m.podcast LIKE ?")
        params.append(f"%{podcast}%")

    where_clause = "AND " + " AND ".join(filters) if filters else ""
    params.append(limit)

    sql = f"""
        SELECT m.*
        FROM moments_fts f
        JOIN moments m ON m.rowid = f.rowid
        WHERE moments_fts MATCH ?
        {where_clause}
        ORDER BY f.rank
        LIMIT ?
    """

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid query: {e}")

    moments = [format_moment(r) for r in rows]
    active_filters = {k: v for k, v in {"stage": stage, "type": type, "podcast": podcast}.items() if v}

    log.info("GET /search q=%r filters=%s → %d results", q, active_filters, len(moments))
    log_entry("/search", "GET", q, active_filters, len(moments),
              request.client.host, request.headers.get("user-agent", ""),
              int((time.time() - t0) * 1000))

    return {
        "query": q,
        "filters": active_filters,
        "count": len(moments),
        "moments": moments,
    }


@app.get("/moments/{moment_id}", response_model=Moment, tags=["Moments"], summary="Get a moment by ID")
def get_moment(request: Request, moment_id: str):
    """Return the full detail of a moment by its UUID."""
    t0 = time.time()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM moments WHERE id = ?", (moment_id,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Moment '{moment_id}' not found")

    log.info("GET /moments/%s → found", moment_id)
    log_entry(f"/moments/{moment_id}", "GET", moment_id, None, 1,
              request.client.host, request.headers.get("user-agent", ""),
              int((time.time() - t0) * 1000))
    return format_moment(row)


@app.get("/similar/{moment_id}", response_model=SimilarResponse, tags=["Search"], summary="Find similar moments")
def similar(
    request: Request,
    moment_id: str,
    limit: int = Query(5, ge=1, le=20, description="Number of similar moments to return"),
):
    """Return moments similar to the given one, based on shared tags and stage."""
    t0 = time.time()
    conn = get_db()
    cur = conn.cursor()

    # Load source moment
    cur.execute("SELECT * FROM moments WHERE id = ?", (moment_id,))
    source = cur.fetchone()
    if source is None:
        conn.close()
        raise HTTPException(status_code=404, detail=f"Moment '{moment_id}' not found")

    source_tags: list[str] = json.loads(source["tags"]) if source["tags"] else []
    source_stage = source["stage"]

    if not source_tags:
        conn.close()
        log.info("GET /similar/%s → no tags, returning empty", moment_id)
        return {"source_id": moment_id, "count": 0, "moments": []}

    # Fetch all other moments with tags
    cur.execute(
        "SELECT * FROM moments WHERE id != ? AND tags IS NOT NULL AND tags != '[]'",
        (moment_id,)
    )
    candidates = cur.fetchall()
    conn.close()

    # Score by shared tags
    source_tag_set = set(source_tags)
    scored = []
    for c in candidates:
        try:
            c_tags = set(json.loads(c["tags"]))
        except Exception:
            continue
        shared = len(source_tag_set & c_tags)
        if shared > 0:
            same_stage = 1 if c["stage"] == source_stage else 0
            scored.append((shared, same_stage, c))

    # Sort: most shared tags first, same stage preferred
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    top = [format_moment(c) for _, _, c in scored[:limit]]

    log.info("GET /similar/%s → %d similar moments", moment_id, len(top))
    log_entry(f"/similar/{moment_id}", "GET", moment_id, None, len(top),
              request.client.host, request.headers.get("user-agent", ""),
              int((time.time() - t0) * 1000))
    return {
        "source_id": moment_id,
        "source_tags": source_tags,
        "count": len(top),
        "moments": top,
    }


@app.post("/situation", response_model=SituationResponse, tags=["Search"], summary="Match moments to a described situation")
def situation_match(request: Request, body: SituationRequest):
    """
    Describe a founder situation in plain language.
    Returns the most relevant moments from the database.
    """
    t0 = time.time()
    if not body.situation.strip():
        raise HTTPException(status_code=400, detail="'situation' cannot be empty")

    limit = max(1, min(body.limit, 20))
    keywords = extract_keywords(body.situation)

    if not keywords:
        raise HTTPException(status_code=400, detail="No meaningful keywords found in situation description")

    # Build FTS OR query from keywords
    fts_query = " OR ".join(keywords)

    filters: list[str] = []
    params: list = [fts_query]

    if body.stage:
        filters.append("m.stage = ?")
        params.append(body.stage)

    where_clause = "AND " + " AND ".join(filters) if filters else ""
    params.append(limit)

    sql = f"""
        SELECT m.*
        FROM moments_fts f
        JOIN moments m ON m.rowid = f.rowid
        WHERE moments_fts MATCH ?
        {where_clause}
        ORDER BY f.rank
        LIMIT ?
    """

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Search error: {e}")

    moments = [format_moment(r) for r in rows]
    log.info("POST /situation keywords=%s → %d results", keywords[:5], len(moments))
    log_entry("/situation", "POST", body.situation[:200], {"stage": body.stage} if body.stage else None,
              len(moments), request.client.host, request.headers.get("user-agent", ""),
              int((time.time() - t0) * 1000))

    return {
        "situation": body.situation,
        "query_keywords": keywords,
        "stage_filter": body.stage,
        "count": len(moments),
        "moments": moments,
    }


# ─── Admin auth ──────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)

def require_admin(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Admin token not configured on server")
    if not credentials or credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")

# ─── Admin endpoints ─────────────────────────────────────────────────────────

@app.get("/admin/logs", tags=["Admin"], summary="Recent request logs", dependencies=[Depends(require_admin)])
def admin_logs(hours: int = 24, limit: int = 50):
    """Return recent API request logs."""
    conn = sqlite3.connect(LOGS_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) FROM request_logs
        WHERE timestamp >= datetime('now', ?)
    """, (f"-{hours} hours",))
    total = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(DISTINCT ip) FROM request_logs
        WHERE timestamp >= datetime('now', ?)
    """, (f"-{hours} hours",))
    unique_ips = cur.fetchone()[0]

    cur.execute("""
        SELECT query, COUNT(*) as count FROM request_logs
        WHERE timestamp >= datetime('now', ?) AND query IS NOT NULL AND query != ''
        GROUP BY query ORDER BY count DESC LIMIT 10
    """, (f"-{hours} hours",))
    top_queries = [{"query": r["query"], "count": r["count"]} for r in cur.fetchall()]

    cur.execute("""
        SELECT user_agent, COUNT(*) as count FROM request_logs
        WHERE timestamp >= datetime('now', ?) AND user_agent IS NOT NULL AND user_agent != ''
        GROUP BY user_agent ORDER BY count DESC LIMIT 10
    """, (f"-{hours} hours",))
    top_agents = [{"agent": r["user_agent"], "count": r["count"]} for r in cur.fetchall()]

    cur.execute("""
        SELECT timestamp, endpoint, query, ip, user_agent, results_count, response_time_ms
        FROM request_logs
        WHERE timestamp >= datetime('now', ?)
        ORDER BY timestamp DESC LIMIT ?
    """, (f"-{hours} hours", limit))
    recent = [dict(r) for r in cur.fetchall()]

    conn.close()
    return {
        "period": f"last {hours} hours",
        "total_requests": total,
        "unique_ips": unique_ips,
        "top_queries": top_queries,
        "top_user_agents": top_agents,
        "recent": recent,
    }


@app.get("/admin/dashboard", tags=["Admin"], summary="Usage dashboard", dependencies=[Depends(require_admin)])
def admin_dashboard():
    """Return aggregated usage statistics across time periods."""
    conn = sqlite3.connect(LOGS_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    def period_stats(interval: str):
        cur.execute(f"""
            SELECT COUNT(*) as requests, COUNT(DISTINCT ip) as unique_ips
            FROM request_logs WHERE timestamp >= datetime('now', ?)
        """, (interval,))
        r = cur.fetchone()
        return {"requests": r["requests"], "unique_ips": r["unique_ips"]}

    cur.execute("""
        SELECT endpoint, COUNT(*) as count FROM request_logs
        GROUP BY endpoint ORDER BY count DESC
    """)
    top_endpoints = {r["endpoint"]: r["count"] for r in cur.fetchall()}

    cur.execute("""
        SELECT query, COUNT(*) as count FROM request_logs
        WHERE timestamp >= datetime('now', '-7 days')
          AND query IS NOT NULL AND query != ''
        GROUP BY query ORDER BY count DESC LIMIT 10
    """)
    top_queries_7d = [{"query": r["query"], "count": r["count"]} for r in cur.fetchall()]

    cur.execute("SELECT COUNT(*) FROM request_logs")
    all_time_total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT ip) FROM request_logs")
    all_time_ips = cur.fetchone()[0]

    today = period_stats("-1 days")
    last_7 = period_stats("-7 days")
    last_30 = period_stats("-30 days")
    conn.close()
    return {
        "today": today,
        "last_7_days": last_7,
        "last_30_days": last_30,
        "all_time": {"requests": all_time_total, "unique_ips": all_time_ips},
        "top_endpoints": top_endpoints,
        "top_queries_7d": top_queries_7d,
    }


LLMS_TXT = """# Echomindr API

> Structured entrepreneurial experiences extracted from 100+ top podcasts. Real decisions, problems, lessons, and signals from founders — searchable by AI agents.

## Documentation

- [API Reference](https://echomindr.com/docs): Full API documentation with examples
- [Search Moments](https://echomindr.com/docs#search): Search by keywords, stage, type
- [Situation Match](https://echomindr.com/docs#situation): Describe a situation, get matching founder experiences

## What is Echomindr?

Echomindr extracts and structures real entrepreneurial experiences from podcast interviews. Each "moment" is a concrete decision, problem, lesson, or signal described by a founder — with context, outcome, and timestamp.

## Use Cases

- An AI agent helping a founder can search for real experiences from similar situations
- A startup advisor can find concrete examples to illustrate advice
- A researcher can analyze patterns across hundreds of founder decisions

## Quick Start

Search for moments about pricing:
GET https://echomindr.com/search?q=pricing&limit=5

Describe a situation and get matching experiences:
POST https://echomindr.com/situation
{"situation": "early stage SaaS struggling with first customers", "limit": 5}

## Data

- 1150+ structured moments from 100+ podcast episodes
- Sources: How I Built This, Lenny's Podcast, 20 Minute VC, Acquired, Y Combinator, My First Million, Indie Hackers
- Each moment includes: summary, verbatim quote, decision, outcome, lesson, context, tags, timestamp with source link
""".strip()


@app.get("/llms.txt", response_class=PlainTextResponse, include_in_schema=False)
def llms_txt():
    """llms.txt — Machine-readable description of the API for AI agents."""
    log.info("GET /llms.txt")
    return LLMS_TXT


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)

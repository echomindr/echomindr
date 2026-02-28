"""
Echomindr — Step 1: Build SQLite database from moments.json files
Usage:
    python echomindr_build_db.py            # Build database from episodes/
    python echomindr_build_db.py --sample   # Build sample DB from sample_data/
    python echomindr_build_db.py --test     # Verify database with test queries
"""

import glob
import json
import os
import sqlite3
import sys
import uuid
from collections import defaultdict

EPISODES_DIR = "episodes"
DB_PATH = "echomindr.db"

# ─── Schema ──────────────────────────────────────────────────────────────────

CREATE_MOMENTS = """
CREATE TABLE moments (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    timestamp TEXT,
    summary TEXT NOT NULL,
    quote TEXT,
    decision TEXT,
    outcome TEXT,
    lesson TEXT,
    stage TEXT,
    situation TEXT,
    tags TEXT,
    podcast TEXT,
    episode TEXT,
    guest TEXT,
    episode_date TEXT,
    source_url TEXT,
    url_at_moment TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_FTS = """
CREATE VIRTUAL TABLE moments_fts USING fts5(
    summary,
    quote,
    decision,
    outcome,
    lesson,
    situation,
    tags,
    guest,
    content=moments,
    content_rowid=rowid
);
"""

CREATE_INDEXES = """
CREATE INDEX idx_moments_type ON moments(type);
CREATE INDEX idx_moments_stage ON moments(stage);
CREATE INDEX idx_moments_podcast ON moments(podcast);
"""

# ─── Helpers ─────────────────────────────────────────────────────────────────

def parse_timestamp_to_seconds(ts: str) -> int | None:
    """Convert "3:26" or "1:23:45" to integer seconds."""
    if not ts:
        return None
    parts = ts.strip().split(":")
    try:
        parts = [int(p) for p in parts]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except (ValueError, TypeError):
        pass
    return None


def build_url_at_moment(base_url: str, timestamp: str) -> str | None:
    """Build a YouTube URL with a timestamp parameter."""
    if not base_url or not base_url.startswith("https://www.youtube.com/watch?v="):
        return None
    seconds = parse_timestamp_to_seconds(timestamp)
    if seconds is None:
        return base_url
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}t={seconds}s"


def load_meta(episode_dir: str) -> dict:
    """Load meta.json from an episode directory, return {} if missing."""
    meta_path = os.path.join(episode_dir, "meta.json")
    if not os.path.exists(meta_path):
        return {}
    try:
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def resolve_source(moment: dict, meta: dict) -> dict:
    """
    Build a unified source dict by merging moment['source'] with meta.json.
    meta.json is the source of truth for URL (already fixed from ytsearch1:)
    and guest (already fixed from TODO).
    """
    src = moment.get("source") or {}

    # Prefer meta.json values when they are richer / fixed
    url = meta.get("url") or src.get("url", "")
    # Reject ytsearch1: fallbacks
    if url.startswith("ytsearch1:"):
        url = ""

    guest = meta.get("guest") or src.get("guest", "")
    if "TODO" in guest:
        guest = src.get("guest", "")
    if "TODO" in guest:
        guest = ""

    return {
        "podcast": meta.get("podcast") or src.get("podcast", ""),
        "episode": meta.get("episode") or src.get("episode", ""),
        "guest": guest,
        "date": meta.get("date") or src.get("date", ""),
        "url": url,
    }


# ─── Build ────────────────────────────────────────────────────────────────────

def build_db():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Remove existing DB
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Create tables
    cur.execute(CREATE_MOMENTS)
    for stmt in CREATE_FTS.strip().split(";"):
        if stmt.strip():
            cur.execute(stmt)
    for stmt in CREATE_INDEXES.strip().split(";"):
        if stmt.strip():
            cur.execute(stmt)

    # Stats
    stats = {
        "total": 0,
        "skipped_files": 0,
        "by_type": defaultdict(int),
        "by_stage": defaultdict(int),
        "by_podcast": defaultdict(int),
        "all_tags": set(),
        "all_guests": set(),
    }

    moments_for_fts = []

    # Walk episodes
    episode_dirs = sorted([
        d for d in glob.glob(os.path.join(EPISODES_DIR, "*"))
        if os.path.isdir(d)
    ])

    for ep_dir in episode_dirs:
        moments_path = os.path.join(ep_dir, "moments.json")
        if not os.path.exists(moments_path):
            continue

        # Load moments.json
        try:
            with open(moments_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"  WARNING: skipping {moments_path} — {e}")
            stats["skipped_files"] += 1
            continue

        moments = data.get("moments", [])
        if not moments:
            print(f"  WARNING: empty moments in {moments_path}")
            stats["skipped_files"] += 1
            continue

        # Load meta.json (source of truth for URL + guest)
        meta = load_meta(ep_dir)

        for moment in moments:
            src = resolve_source(moment, meta)
            ts = moment.get("timestamp", "")
            url_at = build_url_at_moment(src["url"], ts)

            context = moment.get("context") or {}
            tags = moment.get("tags") or []
            tags_str = json.dumps(tags, ensure_ascii=False)

            moment_id = str(uuid.uuid4())
            row = (
                moment_id,
                moment.get("type", "unknown"),
                ts,
                moment.get("summary", ""),
                moment.get("quote"),
                moment.get("decision"),
                moment.get("outcome"),
                moment.get("lesson"),
                context.get("stage"),
                context.get("situation"),
                tags_str,
                src["podcast"],
                src["episode"],
                src["guest"],
                src["date"],
                src["url"],
                url_at,
            )

            cur.execute("""
                INSERT INTO moments (
                    id, type, timestamp, summary, quote,
                    decision, outcome, lesson,
                    stage, situation, tags,
                    podcast, episode, guest, episode_date, source_url,
                    url_at_moment
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, row)

            # Collect for FTS insert
            moments_for_fts.append({
                "rowid": cur.lastrowid,
                "summary": moment.get("summary", ""),
                "quote": moment.get("quote") or "",
                "decision": moment.get("decision") or "",
                "outcome": moment.get("outcome") or "",
                "lesson": moment.get("lesson") or "",
                "situation": context.get("situation") or "",
                "tags": tags_str,
                "guest": src["guest"],
            })

            # Stats
            stats["total"] += 1
            stats["by_type"][moment.get("type", "unknown")] += 1
            stats["by_stage"][context.get("stage", "unknown")] += 1
            stats["by_podcast"][src["podcast"] or "unknown"] += 1
            for tag in tags:
                stats["all_tags"].add(tag)
            if src["guest"]:
                stats["all_guests"].add(src["guest"])

    # Populate FTS
    for m in moments_for_fts:
        cur.execute("""
            INSERT INTO moments_fts (rowid, summary, quote, decision, outcome, lesson, situation, tags, guest)
            VALUES (:rowid, :summary, :quote, :decision, :outcome, :lesson, :situation, :tags, :guest)
        """, m)

    conn.commit()
    conn.close()

    # Print summary
    print(f"\nDatabase: {DB_PATH}")
    print(f"Total moments: {stats['total']}")

    type_parts = ", ".join(f"{k}={v}" for k, v in sorted(stats["by_type"].items()))
    print(f"By type: {type_parts}")

    stage_parts = ", ".join(f"{k}={v}" for k, v in sorted(stats["by_stage"].items()))
    print(f"By stage: {stage_parts}")

    pod_parts = ", ".join(
        f"{k}={v}"
        for k, v in sorted(stats["by_podcast"].items(), key=lambda x: -x[1])
    )
    print(f"By podcast: {pod_parts}")

    print(f"Unique tags: {len(stats['all_tags'])}")
    print(f"Unique guests: {len(stats['all_guests'])}")
    print("FTS index: OK")

    db_size = os.path.getsize(DB_PATH) / 1024
    print(f"DB size: {db_size:.1f} KB")


# ─── Test ─────────────────────────────────────────────────────────────────────

def test_db():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found. Run without --test first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("=" * 60)
    print("TEST MODE")
    print("=" * 60)

    # 1. Total count
    cur.execute("SELECT COUNT(*) FROM moments")
    count = cur.fetchone()[0]
    print(f"\n[1] SELECT COUNT(*) FROM moments → {count}")

    # 2. FTS search: 'pricing'
    print("\n[2] FTS: moments_fts MATCH 'pricing' LIMIT 3")
    cur.execute("""
        SELECT m.type, m.timestamp, m.guest, m.podcast,
               substr(m.summary, 1, 100) as summary_snippet
        FROM moments_fts f
        JOIN moments m ON m.rowid = f.rowid
        WHERE moments_fts MATCH 'pricing'
        LIMIT 3
    """)
    rows = cur.fetchall()
    for r in rows:
        print(f"  [{r['type']}] {r['timestamp']} | {r['guest']} | {r['podcast']}")
        print(f"    {r['summary_snippet']}…")

    # 3. Filter by stage
    print("\n[3] WHERE stage = 'mvp' LIMIT 3")
    cur.execute("""
        SELECT type, timestamp, guest, podcast, substr(summary, 1, 100) as snippet
        FROM moments WHERE stage = 'mvp' LIMIT 3
    """)
    for r in cur.fetchall():
        print(f"  [{r['type']}] {r['timestamp']} | {r['guest']} | {r['podcast']}")
        print(f"    {r['snippet']}…")

    # 4. Filter by tag
    print("\n[4] WHERE tags LIKE '%fundraising%' LIMIT 3")
    cur.execute("""
        SELECT type, timestamp, guest, podcast, tags, substr(summary, 1, 100) as snippet
        FROM moments WHERE tags LIKE '%fundraising%' LIMIT 3
    """)
    for r in cur.fetchall():
        print(f"  [{r['type']}] {r['timestamp']} | {r['guest']} | {r['podcast']}")
        print(f"    tags: {r['tags']}")
        print(f"    {r['snippet']}…")

    # 5. Check url_at_moment
    print("\n[5] url_at_moment sample (first 3 with YouTube URL)")
    cur.execute("""
        SELECT guest, podcast, timestamp, url_at_moment
        FROM moments
        WHERE url_at_moment LIKE 'https://www.youtube.com%'
        LIMIT 3
    """)
    for r in cur.fetchall():
        print(f"  {r['guest']} | {r['timestamp']} → {r['url_at_moment']}")

    conn.close()
    print("\n✅ All tests passed.")


# ─── Sample build ─────────────────────────────────────────────────────────────

def build_sample_db():
    """Build a small database from sample_data/sample_moments.json."""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sample_path = os.path.join("sample_data", "sample_moments.json")
    if not os.path.exists(sample_path):
        print(f"ERROR: {sample_path} not found.")
        sys.exit(1)

    with open(sample_path, encoding="utf-8") as f:
        moments = json.load(f)

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(CREATE_MOMENTS)
    for stmt in CREATE_FTS.strip().split(";"):
        if stmt.strip():
            cur.execute(stmt)
    for stmt in CREATE_INDEXES.strip().split(";"):
        if stmt.strip():
            cur.execute(stmt)

    for m in moments:
        src = m.get("source") or {}
        tags = m.get("tags") or []
        tags_str = json.dumps(tags, ensure_ascii=False)
        ts = m.get("timestamp", "")
        url_at = build_url_at_moment(src.get("url", ""), ts)
        moment_id = m.get("id") or str(uuid.uuid4())

        cur.execute("""
            INSERT INTO moments (
                id, type, timestamp, summary, quote,
                decision, outcome, lesson,
                stage, situation, tags,
                podcast, episode, guest, episode_date, source_url, url_at_moment
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            moment_id, m.get("type", "unknown"), ts,
            m.get("summary", ""), m.get("quote"),
            m.get("decision"), m.get("outcome"), m.get("lesson"),
            m.get("stage"), m.get("situation"), tags_str,
            src.get("podcast"), src.get("episode"), src.get("guest"),
            src.get("date"), src.get("url"), url_at,
        ))

        cur.execute("""
            INSERT INTO moments_fts (rowid, summary, quote, decision, outcome, lesson, situation, tags, guest)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cur.lastrowid,
            m.get("summary", ""), m.get("quote") or "",
            m.get("decision") or "", m.get("outcome") or "",
            m.get("lesson") or "", m.get("situation") or "",
            tags_str, src.get("guest") or "",
        ))

    conn.commit()
    conn.close()
    print(f"Sample database built: {DB_PATH} ({len(moments)} moments)")
    print("Run: python echomindr_api.py")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if "--test" in sys.argv:
        test_db()
    elif "--sample" in sys.argv:
        build_sample_db()
    else:
        build_db()

# Echomindr

**Real founder experiences from 100+ podcasts — searchable by AI agents.**

1,150+ structured moments extracted from How I Built This, Lenny's Podcast, 20 Minute VC, Acquired, Y Combinator, and more. Each moment is a real decision, problem, lesson, or signal — with context, outcome, verbatim quote, and timestamp link.

## Why

AI agents give generic startup advice. Echomindr gives them access to what founders actually did.

Ask: *"How did founders handle their first pricing?"*
Get: Kevin Hale's 10-5-20 rule, Josh Pigford charging $249/month from day one, Madhavan Ramanujam's options trick — with quotes, outcomes, and source links.

## Quick start

### API (REST)

```bash
# Search for moments about pricing
curl "https://echomindr.com/search?q=pricing&limit=5"

# Describe a situation, get matching experiences
curl -X POST "https://echomindr.com/situation" \
  -H "Content-Type: application/json" \
  -d '{"situation": "B2B SaaS founder with free pilots that won'\''t convert to paid"}'

# Get moment details
curl "https://echomindr.com/moments/{id}"

# Find similar experiences
curl "https://echomindr.com/similar/{id}"
```

API docs: [echomindr.com/docs](https://echomindr.com/docs)

### MCP (for AI agents)

Add to Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "echomindr": {
      "command": "python",
      "args": ["echomindr_mcp.py"],
      "env": {
        "ECHOMINDR_API_URL": "https://echomindr.com"
      }
    }
  }
}
```

Or connect via SSE: `https://echomindr.com/mcp/`

Tools exposed:
- `search_experience` — search by situation in natural language
- `get_experience_detail` — get full details of a moment
- `find_similar_experiences` — find related founder stories

### llms.txt

```
https://echomindr.com/llms.txt
```

## Data

- **1,150+ moments** from 96 podcast episodes
- **82 founders** including Stewart Butterfield, Yvon Chouinard, Joe Gebbia, and more
- **5 moment types:** decision, problem, lesson, signal, advice
- **5 stages:** idea, mvp, traction, scale, mature
- **3,824 unique tags**

Each moment includes:
- Summary (2-3 sentences, self-contained)
- Verbatim quote from the founder
- What they decided and the outcome
- The lesson learned
- Stage and situation context
- Tags for filtering
- Timestamp link to the exact podcast moment

## Self-hosting

To run your own instance with the sample data:

```bash
git clone https://github.com/echomindr/echomindr.git
cd echomindr
pip install -r requirements.txt

# Build a sample database
python echomindr_build_db.py --sample

# Start the API
python echomindr_api.py
# → http://localhost:8000/docs
```

To build the full database, you need your own podcast transcriptions and Claude API key. See `echomindr_extract.py` for the extraction pipeline.

## Architecture

```
Podcast audio → Deepgram (transcription) → Claude (extraction) → SQLite → FastAPI → MCP
```

The extraction pipeline turns long-form podcast interviews into structured, searchable moments. Each episode yields 8-15 moments on average.

## Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/search` | GET | Full-text search with stage/type/podcast filters |
| `/situation` | POST | Describe a situation, get matching experiences |
| `/moments/{id}` | GET | Full moment detail |
| `/similar/{id}` | GET | Similar moments by shared tags |
| `/stats` | GET | Database statistics |
| `/llms.txt` | GET | LLM-optimized description |
| `/docs` | GET | Swagger documentation |

## License

MIT — the code is open source. The hosted database at echomindr.com is a managed service.

---

Built by [Thierry](https://www.linkedin.com/in/thierryfaucher/)  — author of "The System That Learns Wins" and "Designing for Permanent Hostility".

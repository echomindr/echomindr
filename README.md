# Echomindr

**3,500+ real founder moments from 60+ podcasts — searchable by AI agents.**

Each moment: a named founder, a verbatim quote, a decision taken, an outcome observed, a lesson extracted — with a timestamped link to the source. Not summaries. Not paraphrases. What actually happened.

## Why

AI agents give generic startup advice. Echomindr gives them access to what founders actually did.

Ask: *"How did founders handle their first pricing?"*
Get: Kevin Hale's 10-5-20 rule, Josh Pigford charging $249/month from day one, Madhavan Ramanujam's options trick — with quotes, outcomes, and source links.

Ask: *"What did founders do when they nearly ran out of money?"*
Get: Airbnb selling cereal boxes, Notion's near-collapse during COVID, Calm's years of slow growth before the breakout — directly from the founders who lived it.

## Quick start

### API (REST)

```bash
# Search for founder experiences
curl "https://echomindr.com/search?q=pricing&limit=5"

# Describe a situation, get matching experiences (vector search)
curl -X POST "https://echomindr.com/situation" \
  -H "Content-Type: application/json" \
  -d '{"situation": "B2B SaaS founder with free pilots that won'\''t convert to paid"}'

# Get moment details
curl "https://echomindr.com/moments/{id}"

# Find similar moments
curl "https://echomindr.com/similar/{id}?limit=5"
```

API docs: [echomindr.com/docs](https://echomindr.com/docs)

### MCP (for AI agents)

Connect via remote MCP: `https://echomindr.com/mcp/`

Or add to Claude Desktop (`claude_desktop_config.json`):

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

3 MCP tools:
- `search_experience` — semantic search for founder stories by situation
- `get_experience_detail` — full details of a moment (quote, decision, outcome, lesson)
- `find_similar_experiences` — related founder stories by shared themes

### llms.txt

```
https://echomindr.com/llms.txt
```

## Data

- **3,500+ moments** from 340+ podcast episodes across 60+ shows
- **52 canonical situations** across 10 thematic families (PMF, growth, pricing, fundraising, team, operations, resilience, strategy, founder psychology, hostile environments)
- **5 moment types:** decision, problem, lesson, signal, advice
- **5 stages:** idea, mvp, traction, scale, mature
- Sources: How I Built This, Lenny's Podcast, 20 Minute VC, Acquired, Y Combinator, My First Million, GDIY (Génération Do It Yourself), Disrupting Japan, Silicon Carne, Startup Ministerio, Kevin Kamis, Wall Street Paper, Valy Sy (China), Matt & Ari (Canada), Oscar Lindhardt (Denmark), Aidan Walsh (USA)

Each moment: summary · verbatim quote · decision · outcome · lesson · stage · tags · timestamp link

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

To build the full database, you need your own podcast transcriptions and Claude API key. See `echomindr_extract_v2.py` for the extraction pipeline.

## Architecture

```
Podcast audio → Deepgram (transcription) → Claude (extraction) → SQLite → FastAPI → MCP
```

The extraction pipeline turns long-form podcast interviews into structured, searchable moments. Each episode yields 8–15 moments on average. Semantic search uses BAAI/BGE-M3 embeddings (1024-dim) via sqlite-vec.

## Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/search` | GET | Full-text search with stage/type filters |
| `/situation` | POST | Describe a situation, get matching experiences (vector search) |
| `/moments/{id}` | GET | Full moment detail |
| `/similar/{id}` | GET | Similar moments by shared tags |
| `/taxonomy` | GET | 52 canonical situations across 10 families |
| `/stats` | GET | Database statistics |
| `/llms.txt` | GET | LLM-optimized API description |
| `/docs` | GET | Swagger documentation |

## License

MIT — the code is open source. The hosted database at echomindr.com is a managed service.

---

Built by [Thierry](https://www.linkedin.com/in/thierryfaucher/) — author of "The System That Learns Wins" and "Designing for Permanent Hostility".

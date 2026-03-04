# Echomindr

**Real founder experiences and concrete facts from 100+ podcasts — searchable by AI agents.**

1,150+ structured moments + 1,000+ concrete facts extracted from How I Built This, Lenny's Podcast, 20 Minute VC, Acquired, Y Combinator, and more, plus YouTube vlogs (Valy Sy in China, Matt & Ari in Canada, Oscar Lindhardt in Denmark, Aidan Walsh in USA).

## Why

AI agents give generic startup advice. Echomindr gives them access to what founders actually did — and the real numbers behind it.

Ask: *"How did founders handle their first pricing?"*
Get: Kevin Hale's 10-5-20 rule, Josh Pigford charging $249/month from day one, Madhavan Ramanujam's options trick — with quotes, outcomes, and source links.

Ask: *"What ad budget to test a dropshipping product?"*
Get: $87 Meta Ads CBO broad campaign, ROAS break-even at 1.39 — from Valy Sy's actual campaign data.

## Quick start

### API (REST)

```bash
# Search for founder experiences (qualitative)
curl "https://echomindr.com/search?q=pricing&limit=5"

# Describe a situation, get matching experiences
curl -X POST "https://echomindr.com/situation" \
  -H "Content-Type: application/json" \
  -d '{"situation": "B2B SaaS founder with free pilots that won'\''t convert to paid"}'

# Search for concrete facts (quantitative: metrics, prices, MOQ, ROAS…)
curl "https://echomindr.com/facts/search?q=Meta+Ads+budget&location=China&limit=5"

# Describe a situation, get matching facts
curl -X POST "https://echomindr.com/facts/situation" \
  -H "Content-Type: application/json" \
  -d '{"situation": "MOQ minimum order quantity factory Guangzhou", "location": "China"}'

# Get moment or fact details
curl "https://echomindr.com/moments/{id}"
curl "https://echomindr.com/facts/{id}"
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
- `search_experience` — search founder stories by situation in natural language
- `get_experience_detail` — get full details of a moment (quote, decision, outcome, lesson)
- `find_similar_experiences` — find related founder stories by shared themes
- `search_facts` — search for concrete facts (metrics, prices, MOQ, ROAS, timelines, volumes)
- `get_fact_detail` — get full fact details including verbatim transcript excerpt

### llms.txt

```
https://echomindr.com/llms.txt
```

## Data

### Founder experiences (qualitative)
- **1,150+ moments** from 100+ podcast episodes
- **82 founders** including Stewart Butterfield, Yvon Chouinard, Joe Gebbia, and more
- **5 moment types:** decision, problem, lesson, signal, advice
- **5 stages:** idea, mvp, traction, scale, mature
- **3,824 unique tags**

Each moment includes: summary, verbatim quote, decision, outcome, lesson, stage, tags, and timestamp link.

### Concrete facts (quantitative)
- **1,000+ facts** from 60 episodes including YouTube vlogs
- **Sources:** Valy Sy (China sourcing/e-commerce), Matt & Ari (Canada), Oscar Lindhardt (Denmark), Aidan Walsh (USA), Acquired, YC, How I Built This
- **10 domains:** GO-TO-MARKET, PRODUCT, OPERATIONS, TECHNICAL, ACQUISITION, FUNDRAISING, HIRING, PRICING, COMPETITION, RETENTION
- **Filters:** stage, domain, location (China/USA/Canada/Denmark), city

Each fact includes: the concrete event, observable signal, verbatim transcript excerpt, and timestamp link.

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

### Experiences (qualitative)

| Endpoint | Method | Description |
|---|---|---|
| `/search` | GET | Full-text search with stage/type/podcast filters |
| `/situation` | POST | Describe a situation, get matching experiences |
| `/moments/{id}` | GET | Full moment detail |
| `/similar/{id}` | GET | Similar moments by shared tags |

### Facts (quantitative)

| Endpoint | Method | Description |
|---|---|---|
| `/facts/search` | GET | Full-text search with stage/domain/location/city filters |
| `/facts/situation` | POST | Describe a situation, get matching facts |
| `/facts/{id}` | GET | Full fact detail including verbatim transcript |

### Other

| Endpoint | Method | Description |
|---|---|---|
| `/stats` | GET | Database statistics (moments + facts) |
| `/llms.txt` | GET | LLM-optimized description |
| `/docs` | GET | Swagger documentation |

## License

MIT — the code is open source. The hosted database at echomindr.com is a managed service.

---

Built by [Thierry](https://www.linkedin.com/in/thierryfaucher/)  — author of "The System That Learns Wins" and "Designing for Permanent Hostility".

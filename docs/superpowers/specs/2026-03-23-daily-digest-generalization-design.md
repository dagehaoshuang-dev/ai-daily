# Design Spec: Daily Digest Generalization
**Date:** 2026-03-23
**Scope:** Modify existing `ai-daily` skill to support any enterprise department, not just AI domain

---

## Problem Statement

The current `ai-daily` skill is hardcoded for AI industry news. The goal is to make it domain-agnostic — serving any enterprise department (marketing, finance, product, legal, etc.) by reading the department's Feishu knowledge base and group chat to understand their specific context and interests.

---

## Approved Approach: Feishu-Driven Department Profile + Daily Group Chat Signals

The profile is not manually filled. Instead:
1. **One-time initialization**: Agent reads Feishu KB to generate an initial `dept-profile.yaml`
2. **Daily incremental update**: Agent reads the department's designated Feishu group chat each day, extracts signals, and updates the profile
3. **Daily digest generation**: Driven by the updated profile

---

## Required Feishu MCP Operations

The skill requires the following Feishu MCP tool operations. If any are unavailable, see the Fallback section:

| Operation | Used For |
|---|---|
| `list_wiki_nodes` / `get_wiki_content` | KB initialization: enumerate and read KB pages |
| `get_chat_messages` with time range | Daily signal collection: read group chat messages |
| `get_message_reactions` (optional) | Signal scoring: identify high-engagement messages |

Time boundary for "today's messages": UTC+8 (Beijing time), from 00:00 to current time at execution. Fetch up to 200 messages per run; if the group has more, prioritize the most recent 200.

---

## Architecture

### Two Execution Paths

**Path A — Profile Initialization (first run or explicit `/ai-daily refresh-profile`)**
```
Feishu KB (project docs + OKRs + historical reports)
    ↓ list_wiki_nodes → get_wiki_content (up to 20 pages, prioritize root + recent)
AI analysis → generate config/dept-profile.yaml
```

KB read scope: traverse up to 2 levels deep, max 20 pages. Skip pages >50KB. If KB access fails on individual pages, skip and continue. If all pages fail, abort initialization with error.

**Path B — Daily Digest Generation (main flow)**
```
Read Feishu group chat (today's messages, via get_chat_messages)
    ↓
Extract signals → update dept-profile.yaml incrementally
    ↓
Build search strategy from updated profile
    ↓
Parallel collection (WebSearch + WebFetch)
    ↓
Filter → generate structured JSON
    ↓
Render HTML → start feedback server
    ↓
Extract today's summary → append to profile history
```

---

## dept-profile.yaml Schema

File location: `config/dept-profile.yaml` (replaces `config/profile.yaml`).

**Migration**: On first run, if `config/profile.yaml` exists but `config/dept-profile.yaml` does not, the agent reads the old file and maps relevant fields into the new schema, then writes `schema_version: 1` to the generated file. The old file is renamed to `config/profile.yaml.bak`.

Fields dropped during migration (not carried forward): `server.port`, `server.timeout_hours`, `role`, `role_context`, `topics`, `exclude_topics`, `daily.*`. Server configuration continues to use SKILL.md defaults (port 17890, timeout 2h). Users who customized these values should note them before migration.

```yaml
schema_version: 1

# Static section (generated at init, rarely changes)
department:
  name: "产品部"
  domain: ["product", "saas"]   # List of domain tags; from controlled vocab below
  industry: "B2B SaaS"
  feishu_group_id: ""            # Must be set before first daily run; see Provisioning

# Dynamic tracking entities (updated via group chat signals)
# Entries are pruned if last_signal > 30 days ago and weight < 0.3
tracking:
  competitors: []    # {name, last_signal}
  products: []       # {name, last_signal}
  markets: []        # {name, last_signal}
  technologies: []   # {name, last_signal}
  people: []         # {name, last_signal}

# Topic weights (auto-adjusted daily)
# Decay rule: weight *= 0.9 for each day without a signal; minimum 0.1
# Boost rule: weight = min(1.0, weight + 0.2) when signal received
# Signal threshold: topic must appear in ≥2 messages, or in 1 message with ≥1 reaction
topic_weights:
  - topic: "竞品动态"
    weight: 0.9
    last_signal: "2026-03-23"

# Recommended sources (AI-inferred from domain during init; manually overridable)
sources:
  direct: []           # URLs to fetch directly each run
  search_queries: []   # Seed search queries; AI may augment each run

# Rolling 7-day history (calendar days; one entry per run date, last-write-wins if run twice)
history:
  - date: "2026-03-22"
    top_topics: ["竞品动态", "行业趋势"]
    group_signals: ["3 messages about Notion AI", "1 link to G2 report"]
```

### Controlled Domain Vocabulary

To ensure consistency, `domain` values must be from this list (AI may select multiple):
`ai`, `product`, `engineering`, `marketing`, `finance`, `legal`, `operations`, `sales`, `research`, `hr`

If the inferred domain does not fit any label, use `general` and prompt the user to confirm.

---

## Provisioning: feishu_group_id

During initialization (Path A), after generating the profile, the agent:
1. Checks if `feishu_group_id` is set
2. If empty: outputs a prompt asking the user to provide the Feishu group ID, then writes it to the profile
3. Daily runs (Path B) will not proceed to group chat reading until this field is set; they degrade gracefully (skip Step 1, use current profile weights as-is)

---

## Revised Execution Flow

### Step 0: Profile Check
- `config/dept-profile.yaml` exists and `schema_version` is current? → continue
- Does not exist → check for legacy `config/profile.yaml` → migrate if found, else trigger KB init
- `feishu_group_id` is empty? → skip Step 1, use current profile

### Step 1 (NEW): Read Group Chat Signals
- Call `get_chat_messages` for today (UTC+8 00:00 to now), up to 200 messages
- AI extracts signals using these rules:
  - **Topic signal**: topic mentioned in ≥2 messages OR in 1 message with ≥1 reaction → boost weight
  - **Entity signal**: company/product/market name appears ≥2 times → add or update `tracking` entry
  - **New topic**: topic not in profile, mentioned ≥3 times → add with initial weight 0.4
  - **Noise filter**: single mentions without reactions are ignored
- Apply weight decay to all topics not seen today: `weight *= 0.9`
- Prune tracking entries with `last_signal > 30 days` AND `weight < 0.3`
- Write changes back to `dept-profile.yaml`

### Step 2 (MODIFIED): Build Search Strategy
- **Before**: hardcoded AI domain searches
- **After**: driven by `dept-profile`:
  - `domain` tags → determines which pages to fetch directly (e.g., `product` domain → ProductHunt, G2)
  - `tracking.competitors/products` → generates targeted search queries
  - `topic_weights` → topics with weight > 0.6 get 2 search queries; 0.3–0.6 get 1; below 0.3 are skipped
  - `sources.direct` → fetched directly, replacing the fixed AI source list
  - `sources.search_queries` → used as seed queries, AI may augment based on current news

### Step 3 (MODIFIED): Filter and Process
- AI determines article grouping labels based on `dept-profile.domain`
- These labels map to the `tags` field on each article in the JSON payload
- **The HTML section structure (left sidebar, article cards) is unchanged** — `render_daily.py` is not modified
- Domain-specific grouping appears as tag filters within the existing card layout, not as new sidebar sections
- Example tags for `product` domain: `#竞品动态`, `#行业趋势`, `#工具更新`, `#用户研究`

### Step 4: JSON → HTML (unchanged)
- `render_daily.py` is called as-is; no modifications required

### Step 5 (NEW): Update Profile History
- Extract today's top 3 topics from the generated digest
- Summarize group signals in 1-3 short strings
- Append one entry to `dept-profile.yaml` history
- If an entry for today's date already exists, overwrite it (last-write-wins)
- Trim to keep only the last 7 calendar days

---

## Feedback Signal Integration

The existing `data/feedback/` HTML behavior data (dwell time, votes, bookmarks) is **preserved** and continues to inform the search strategy as a secondary signal. Priority order:
1. Feishu group chat signals (primary — reflects team behavior)
2. HTML page feedback (secondary — individual reading behavior)
3. `dept-profile.yaml` static configuration (baseline)

---

## Fallback / Degradation Handling

| Failure Scenario | Behavior |
|---|---|
| Group chat empty / no qualifying signals | Skip weight update, apply decay only, continue with current profile |
| `get_chat_messages` MCP call fails | Use current profile unchanged; note in digest footer: "群聊信号读取失败，画像未更新" |
| `feishu_group_id` not set | Skip Step 1 entirely; proceed with current profile |
| KB read fails entirely (init) | Exit with error, prompt user to check MCP connection |
| Individual KB pages fail (init) | Skip those pages, continue with available content |
| KB has <3 readable pages | Generate minimal profile with domain=`general`; prompt user to confirm domain |
| `domain` field empty after init | AI prompts user once to confirm; writes confirmed value to profile |
| Legacy `config/profile.yaml` found | Migrate to new schema, rename old file to `.bak` |

---

## What Changes in SKILL.md

| Current | After |
|---|---|
| `config/profile.yaml` — manually filled | `config/dept-profile.yaml` — auto-generated + daily updates (with migration from old file) |
| Searches fixed to AI domain | Search strategy driven by dept profile, any domain |
| Feedback via HTML page behavior only | Primary: Feishu group chat signals; secondary: HTML feedback |
| Tags are AI-specific (`#Agent`, `#开源`) | Tags are domain-specific, inferred from dept profile |
| Static profile | Profile drifts daily with group chat signals + weight decay |
| Fixed AI sources | Sources derived from domain tags in controlled vocabulary |

---

## Out of Scope

- Multi-department support in a single deployment (one skill instance = one department)
- Automatic Feishu group ID discovery (must be configured once during init)
- Modifications to `render_daily.py` HTML structure
- Feishu MCP server setup (assumed already configured)
- Schema version migration beyond v1→current

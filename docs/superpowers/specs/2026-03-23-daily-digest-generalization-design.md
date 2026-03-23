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

## Required Feishu MCP Capabilities

The skill relies on these logical capabilities. The table maps them to known tool names in the current environment; if tool names differ, implement against the logical capability:

| Logical Capability | Known Tool Name(s) | Used For | Required? |
|---|---|---|---|
| List KB wiki nodes | `feishu_wiki_space_node` | KB init: enumerate pages | Required |
| Read KB document content | `feishu_fetch_doc` | KB init: read page content | Required |
| Read group chat messages (with time range) | `feishu_im_user_get_messages` | Daily signal collection | Required |
| Read message reactions | *(no direct equivalent exposed)* | Signal scoring boost | Optional |

**Note on `get_message_reactions`**: If no reaction-reading tool is available, treat all qualifying messages equally (remove the "1 message + ≥1 reaction" signal path; use only the ≥2 messages threshold).

---

## Profile State Machine

`dept-profile.yaml` moves through these states. Step 0 reads the current state and routes accordingly:

```
uninitialized
    ↓ KB read succeeds
awaiting_group_id          ← feishu_group_id is empty; user must provide it
    ↓ user runs: /ai-daily set-group <chat_id>
active                     ← normal daily operation
    ↓ MCP failure or degraded KB
degraded                   ← daily digest continues; group chat signals skipped
    ↓ MCP recovers
active
```

`feishu_group_id` is **never auto-written** from within a single execution flow. It is set explicitly via the `/ai-daily set-group <chat_id>` command, which patches the profile and transitions state from `awaiting_group_id` → `active`.

---

## Architecture

### Execution Paths

**Path A — Profile Initialization (state: `uninitialized` → `awaiting_group_id`)**
```
Feishu KB (project docs + OKRs + historical reports)
    ↓ feishu_wiki_space_node → feishu_fetch_doc
    ↓ default: 2 levels deep, up to 20 pages, skip >50KB
    ↓ (these are configurable defaults, not hard limits — see dept-profile.yaml)
AI analysis → generate config/dept-profile.yaml
    ↓
state: awaiting_group_id — prompt user to run /ai-daily set-group <chat_id>
```

**Path B — Daily Digest Generation (state: `active` or `degraded`)**
```
Read Feishu group chat (today's messages, time-bounded pagination)
    ↓
Extract signals → update dept-profile.yaml incrementally
    ↓
Build search strategy from updated profile
    ↓
Parallel collection (WebSearch + WebFetch)
    ↓
Filter → generate structured JSON (includes digest_meta.warnings[])
    ↓
Render HTML → start feedback server
    ↓
Extract today's summary → append to profile history
```

**Path C — Set Group ID (`/ai-daily set-group <chat_id>`)**
```
Write feishu_group_id to dept-profile.yaml
Transition state: awaiting_group_id → active
```

---

## dept-profile.yaml Schema

File location: `config/dept-profile.yaml` (replaces `config/profile.yaml`).

**Migration**: On first run, if `config/profile.yaml` exists but `config/dept-profile.yaml` does not, the agent reads the old file, maps relevant fields into the new schema, and writes `schema_version: 1`. The old file is renamed to `config/profile.yaml.bak`.

Fields dropped during migration (not carried forward): `server.port`, `server.timeout_hours`, `role`, `role_context`, `topics`, `exclude_topics`, `daily.*`. Server configuration continues to use SKILL.md defaults (port 17890, timeout 2h). Users who customized these values should note them before migration.

```yaml
schema_version: 1
status: active   # uninitialized | awaiting_group_id | active | degraded

# Static section (generated at init, rarely changes)
department:
  name: "产品部"
  primary_domain: "product"       # Single primary domain from controlled vocab
  secondary_domains: ["saas"]     # Additional domain tags (freeform allowed)
  freeform_context: "B2B SaaS 企业协���工具，专注日本市场"  # Free text for AI context
  industry: "B2B SaaS"
  feishu_group_id: ""             # Set via /ai-daily set-group <chat_id>

# KB init configuration (defaults; override here to adjust)
kb_init:
  max_depth: 2
  max_pages: 20
  max_page_size_kb: 50
  last_init: "2026-03-23"
  init_coverage_note: "Skipped 3 pages: 2 exceeded 50KB, 1 permission denied"

# Dynamic tracking entities
# Pruned when: last_signal > 30 days ago AND score < 0.3
tracking:
  competitors:
    - name: "Notion"
      score: 0.8
      first_seen: "2026-03-10"
      last_signal: "2026-03-23"
      signal_count_7d: 5
  products: []    # same schema as competitors
  markets: []
  technologies: []
  people: []

# Topic weights (auto-adjusted daily)
# Decay: weight *= 0.9 per day without signal; floor 0.1
# Boost: weight = min(1.0, weight + 0.2) per day with signal
# Signal threshold: ≥2 messages mentioning topic (no reaction data → this is the only threshold)
# New topic entry: ≥3 mentions → initial weight 0.4
topic_weights:
  - topic: "竞品动态"
    weight: 0.9
    last_signal: "2026-03-23"

# Recommended sources (AI-inferred from domain during init; manually overridable)
sources:
  direct: []           # URLs fetched directly each run
  search_queries: []   # Seed queries; AI augments each run

# Rolling 7-day history (calendar days; last-write-wins if run twice same day)
history:
  - date: "2026-03-22"
    top_topics: ["竞品动态", "行业趋势"]
    group_signals: ["3 messages about Notion AI", "1 link to G2 report"]
```

### Controlled Domain Vocabulary

`primary_domain` must be one of:
`ai`, `product`, `engineering`, `marketing`, `finance`, `legal`, `operations`, `sales`, `research`, `hr`, `data`, `design`, `growth`, `security`, `strategy`, `customer_success`, `bd`, `general`

`secondary_domains` may use any of the above **or** freeform strings. `freeform_context` accepts free text and is passed directly to the AI as additional context when building the search strategy.

---

## Revised Execution Flow

### Step 0: Profile Check + State Routing

| State | Action |
|---|---|
| File missing, no legacy | Trigger KB init (Path A) |
| File missing, legacy exists | Migrate from `profile.yaml`, state → `awaiting_group_id` |
| `uninitialized` | Trigger KB init (Path A) |
| `awaiting_group_id` | Prompt user to run `/ai-daily set-group <chat_id>`; exit |
| `active` | Continue to Step 1 |
| `degraded` | Skip Step 1; continue from Step 2 using current profile |

### Step 1 (NEW): Read Group Chat Signals

**Message fetching**: Paginate `feishu_im_user_get_messages` from UTC+8 00:00 today to current time. Continue paginating until either the start of day is reached or 1000 messages total are fetched, whichever comes first. Summarize/compress before analysis if >200 messages retrieved.

**Signal extraction rules**:
- **Topic boost**: topic mentioned in ≥2 messages → `weight += 0.2` (capped at 1.0)
- **Entity signal**: company/product/market name in ≥2 messages → add/update `tracking` entry
- **New topic**: not in profile, mentioned ≥3 times → add with initial weight 0.4
- **Noise filter**: single mentions are ignored

**After extraction**:
- Apply decay to all topics not signaled today: `weight *= 0.9` (floor 0.1)
- Prune tracking entries where `last_signal > 30 days` AND `score < 0.3`
- Write incremental changes back to `dept-profile.yaml`

**On MCP failure**: set `status: degraded`, add to `digest_meta.warnings[]`, continue to Step 2

### Step 2 (MODIFIED): Build Search Strategy

Driven by `dept-profile`:
- `primary_domain` + `secondary_domains` + `freeform_context` → determines direct-fetch sources and base queries
- `tracking.competitors/products` → targeted search queries (one per entity with `score > 0.5`)
- `topic_weights` → topics with weight > 0.6 get 2 queries; 0.3–0.6 get 1; below 0.3 are skipped
- `sources.direct` → fetched directly each run
- `sources.search_queries` → used as seed queries; AI may augment

### Step 3 (MODIFIED): Filter and Process

- AI assigns domain-specific tags to each article based on `dept-profile`
- Tags map to the existing `tags` field in the JSON payload
- `render_daily.py` is **not modified** — domain grouping is expressed through tags on cards, not sidebar structure
- Example tags for `product` domain: `#竞品动态`, `#行业趋势`, `#工具更新`, `#用户研究`

### Step 4: JSON → HTML (unchanged)

- `render_daily.py` called as-is
- The JSON payload includes `digest_meta.warnings[]` for any runtime issues; **the renderer does not need to display these** — they are for logging and future tooling

### Step 5 (NEW): Update Profile History

- Extract today's top 3 topics from the generated digest
- Summarize group signals in 1–3 short strings
- Append/overwrite today's entry in `history` (last-write-wins)
- Trim to last 7 calendar days

---

## Feedback Signal Integration

The existing `data/feedback/` HTML behavior data is **preserved** as a secondary signal:

1. Feishu group chat signals (primary — team behavior)
2. HTML page feedback (secondary — individual reading behavior)
3. `dept-profile.yaml` static configuration (baseline)

---

## Fallback / Degradation Handling

| Failure Scenario | State Transition | Behavior |
|---|---|---|
| Group chat empty / no qualifying signals | stays `active` | Skip weight update, apply decay only, continue |
| `feishu_im_user_get_messages` fails | → `degraded` | Add to `digest_meta.warnings[]`; use current profile |
| `feishu_group_id` not set | stays `awaiting_group_id` | Prompt user; exit without generating digest |
| KB read fails entirely (init) | stays `uninitialized` | Exit with error; prompt user to check MCP |
| Individual KB pages fail (init) | — | Skip those pages; log in `kb_init.init_coverage_note` |
| KB has <3 readable pages | → `awaiting_group_id` | Generate minimal profile with `primary_domain: general`; prompt to confirm |
| `primary_domain` empty after init | → `awaiting_group_id` | Prompt user to confirm domain via `/ai-daily set-domain <domain>` |
| Legacy `config/profile.yaml` found | → `awaiting_group_id` | Migrate; rename old file `.bak`; prompt for group ID |
| MCP recovers after `degraded` | → `active` | Automatic on next successful Step 1 |

---

## What Changes in SKILL.md

| Current | After |
|---|---|
| `config/profile.yaml` — manually filled | `config/dept-profile.yaml` — auto-generated via KB + daily group chat updates |
| Searches fixed to AI domain | Search strategy driven by dept profile (`primary_domain` + `tracking` + `topic_weights`) |
| Feedback via HTML page behavior only | Primary: Feishu group chat signals; secondary: HTML feedback |
| Tags are AI-specific (`#Agent`, `#开源`) | Tags are domain-specific, inferred per run from dept profile |
| Static profile | Profile drifts daily via signal boost/decay |
| Fixed AI sources | Sources derived from domain + `freeform_context` |
| Single execution path | Three paths: init / daily digest / set-group |

---

## Out of Scope

- Multi-department support in a single deployment
- Automatic Feishu group ID discovery
- Modifications to `render_daily.py` HTML structure or sidebar layout
- Feishu MCP server setup
- Schema migration beyond v1
- Displaying `digest_meta.warnings[]` in the HTML UI (warnings are for logging only)

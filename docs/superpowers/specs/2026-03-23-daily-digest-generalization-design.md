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

## Architecture

### Two Execution Paths

**Path A — Profile Initialization (one-time or on explicit refresh)**
```
Feishu KB (project docs + OKRs + historical reports)
    ↓ Feishu MCP
AI analysis → generate config/dept-profile.yaml
```

**Path B — Daily Digest Generation (main flow)**
```
Read Feishu group chat (today's messages)
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

```yaml
# Static section (generated at init, rarely changes)
department:
  name: "产品部"
  domain: "product"           # AI-inferred domain tag(s)
  industry: "B2B SaaS"
  feishu_group_id: "xxx"      # Fixed group chat ID

# Dynamic tracking entities (updated via group chat signals)
tracking:
  competitors: []
  products: []
  markets: []
  technologies: []
  people: []

# Topic weights (auto-adjusted daily; higher = more search allocation)
topic_weights:
  - topic: "竞品动态"
    weight: 0.9
    last_signal: "2026-03-23"

# Recommended sources (AI-inferred from domain; manually overridable)
sources:
  direct: []
  search_queries: []

# Rolling 7-day history (for drift detection)
history:
  - date: "2026-03-22"
    top_topics: []
    group_signals: []
```

---

## Revised Execution Flow

### Step 0: Profile Check
- `dept-profile.yaml` exists? → continue
- Does not exist → trigger Feishu KB read → generate initial profile

### Step 1 (NEW): Read Group Chat Signals
- Read today's messages from the configured Feishu group (via MCP)
- AI extracts:
  - Topics with reactions/discussion → boost corresponding `topic_weight`
  - Shared links / company / product names → update `tracking` entities
  - New topics not yet in profile → add as candidates
- Write changes back to `dept-profile.yaml` incrementally

### Step 2 (MODIFIED): Build Search Strategy
- **Before**: hardcoded AI domain searches
- **After**: driven by `dept-profile`:
  - `domain` → determines which pages to fetch directly
  - `tracking.competitors/products` → targeted search queries
  - `topic_weights` → higher weight = more search budget allocated
  - `sources.direct` → replaces the fixed AI source list

### Step 3 (MODIFIED): Filter and Process
- **Before**: fixed sections (Agent生态 / 中国AI / 开源工具 etc.)
- **After**: AI determines section names dynamically based on `dept-profile.domain`
  - Example for product dept: 竞品动态 / 行业趋势 / 工具更新 / 用户研究

### Step 4: JSON → HTML (unchanged)

### Step 5 (NEW): Update Profile History
- Extract today's `top_topics` from generated digest
- Append to `dept-profile.yaml` history
- Trim history to last 7 days

---

## Fallback / Degradation Handling

| Failure Scenario | Behavior |
|---|---|
| Group chat empty / no signals | Skip weight update, use current profile, continue |
| Feishu MCP group chat read fails | Use current profile unchanged; note in digest footer |
| Feishu MCP KB read fails (init) | Exit with error, prompt user to check MCP connection |
| `domain` field empty after init | AI prompts user to confirm domain once; writes to profile |
| New department with minimal KB | Generate minimal profile; note that signals will enrich over time |

---

## What Changes in SKILL.md

| Current | After |
|---|---|
| `config/profile.yaml` — manually filled | `config/dept-profile.yaml` — auto-generated + daily updates |
| Searches fixed to AI domain | Search strategy driven by dept profile, any domain |
| Feedback via HTML page behavior | Feedback via Feishu group chat signals |
| Fixed 6 AI-specific sections | Dynamic sections determined by domain |
| Static profile | Profile drifts daily with group chat |

---

## Out of Scope

- Multi-department support in a single deployment (one skill instance = one department)
- Automatic Feishu group ID discovery (must be configured manually)
- Historical report migration from old AI-only format
- Feishu MCP server setup (assumed already configured)

# LLM Security Monitoring & Alerting

A defense-in-depth security monitoring system for LLM-powered chat applications, built around an ELK stack. The project detects, logs, alerts on, and (via an AI-assisted second review) re-evaluates prompt injection, jailbreak attempts, and sensitive data leaks in a local LLM chat pipeline, structured around OWASP LLM Top 10 (2026) categories.

Built as a 7-day internship project. Defensive/blue-team focus throughout: no offensive tooling, no real-world exploit payloads.

---

## Why This Exists

Most LLM security demos stop at "regex catches bad words." This project instead asks: **what happens when a single detection layer isn't enough?**

Across development, three concrete gaps were found and used to justify the architecture:

- **Regex missed a Spanish-language jailbreak** ("Ignora todas las instrucciones...") — English-only patterns don't generalize across languages.
- **Regex missed an acrostic-based instruction override** — a poem whose first letters spelled "IGNORE," which the model then acted on, producing a fabricated "system prompt." Neither regex nor embedding similarity flagged it (embedding score 0.60, below threshold); an AI-based second review (Qwen3:8b) caught it, but only after its prompt was rewritten twice to stop it from either over-triggering on borderline cases or refusing to escalate anything not matching the rulebook word-for-word.
- **Regex missed natural-language phrasing of a real API key leak** — "the API key is: sk-..." wasn't caught until the pattern was extended three separate times (to handle "is"/"as" phrasing, a space instead of `_`/`-`, and a stray colon after "is").

None of these were hypothetical — they were reproduced against a real local model (Mistral, via Ollama) and used to iteratively harden the rulebook, the embedding threshold, and the AI triage prompt. This iterative "test → find a gap → fix → retest" loop is the actual throughline of the project, more so than any single component.

---

## Architecture

```
                                   ┌─────────────────────┐
                                   │   React Frontend      │
                                   │  (chat UI, user mgmt) │
                                   └──────────┬───────────┘
                                              │ REST (FastAPI)
                                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                          FastAPI Backend                          │
│                                                                      │
│  1. Rulebook (regex, rules.yaml)          ─┐                       │
│  2. Behavioral (rate/length/repetition)    ├─ blocks BEFORE Mistral │
│  3. Embedding similarity (BGE + jailbreak  ─┘  if high/critical      │
│     reference set)                                                 │
│  4. Mistral (Ollama) — with last 6 turns of chat history            │
│  5. Response-side regex (API keys, PII, script/SQL/shell tags)     │
│                                                                      │
└───────┬───────────────────────────────────────────┬────────────────┘
        │ every interaction, regardless of outcome    │
        ▼                                              ▼
┌────────────────────┐                    ┌─────────────────────────┐
│   PostgreSQL         │                    │   llm_interactions.log   │
│  (chats, messages,   │                    │        (JSONL)           │
│   users — app state) │                    └────────────┬─────────────┘
└──────────────────────┘                                 │ Filebeat
                                                            ▼
                                                    ┌───────────────┐
                                                    │   Logstash     │
                                                    └───────┬───────┘
                                                            ▼
                                                    ┌───────────────┐
                                                    │ Elasticsearch  │
                                                    └───────┬───────┘
                                            ┌───────────────┼────────────────┐
                                            ▼                                ▼
                                  ┌──────────────────┐          ┌────────────────────────┐
                                  │  Kibana Dashboard  │          │   AI Triage Agent        │
                                  │   (8 panels)        │          │  (Qwen3:8b, every 3 min) │
                                  └──────────┬─────────┘          │  re-reviews none/low/    │
                                             │                     │  medium severity logs,   │
                                             ▼                     │  with chat context        │
                                  ┌──────────────────┐          └────────────┬─────────────┘
                                  │ Kibana Alert Rules │                       │ writes ai_review
                                  │  (5, per severity   │◄──────────────────────┘  back to ES
                                  │  tier + AI escalate) │
                                  └──────────┬─────────┘
                                             ▼
                                  ┌──────────────────┐
                                  │  Slack (5 channels)│
                                  └────────────────────┘
```

**Design principle:** Elasticsearch is the security source of truth (immutable, append-only log file → Filebeat → Logstash → ES). PostgreSQL is only application state (chat history for the UI). The two are cross-referenced by a shared `chat_id`, but neither depends on the other to function.

---

## Detection Pipeline (in order)

Each incoming prompt passes through four layers before reaching Mistral. The first one to flag `high`/`critical` blocks the request — none reach a lower-priority layer.

| Order | Layer | What it catches | Blocks automatically? |
|---|---|---|---|
| 1 | **Rulebook** (`detection/rules.yaml`) | Known regex patterns: instruction override, jailbreak keywords (DAN/AIM/STAN/DUDE), role manipulation, API key/private key/email leaks, script/SQL/shell injection in output | Yes, if `high`/`critical` |
| 2 | **Behavioral** (`detection/behavioral.py`) | Rate anomaly (≥4 req/60s), length anomaly (≥2000 chars), repetition anomaly (≥90% similarity, 3+ times in 30s) | Yes, on repetition/rate flags |
| 3 | **Embedding similarity** (`detection/embedding.py`) | Semantic closeness (cosine similarity, `BAAI/bge-base-en-v1.5`) to a 57-prompt reference set of known jailbreaks | Yes, if score ≥ 0.72 |
| 4 | **Response-side rulebook** | Same regex set, run again against the model's actual output (catches leaks/overrides that only appear in the response) | Yes, if `high`/`critical` |

If none of the four blocks the request, the prompt (with up to 6 turns of prior chat history for conversational context — **not** passed through detection, only to Mistral) goes to Mistral, and the response is then checked by layer 4.

### Embedding threshold, explained

- **Flag threshold:** 0.70 — anything at or above this is logged as `flagged: true` and contributes to `overall_severity`, but does not block on its own.
- **Auto-block threshold:** 0.72 — anything at or above this blocks the request before it reaches Mistral.

The gap between 0.70 and 0.72 is intentional: it's a "gray zone" — logged and severity-tagged, but not strong enough to auto-block. This is exactly the population the AI Triage agent targets.

---

## AI-Assisted Triage

**Problem it solves:** regex and embedding both operate on a single message in isolation, with fixed, human-written criteria. Some manipulation attempts don't match any known pattern and aren't semantically close enough to the reference set to trigger embedding — but a human (or a capable LLM) reading the exchange would recognize the intent immediately.

**How it works** (`ai_triage/agent_triage.py`):

1. Every 3 minutes, pulls all `none`/`low`/`medium` severity logs from the last 10 minutes that haven't been reviewed yet (`critical`/`high` are excluded — they're already auto-blocked by one of the four layers above, so a second review adds nothing).
2. For each log, pulls up to 5 prior messages from the *same* `chat_id` (not `session_id` — a session can span multiple unrelated chats; a `chat_id` is one coherent conversation) for context.
3. Sends the rulebook (in full — every rule ID, pattern, and severity), the embedding threshold, the log's current severity, the conversation history, and the new message to a **local** LLM (Qwen3:8b via Ollama) with strict instructions: judge only against the categories above, never lower a severity, only raise it with a concrete reason grounded in those categories (not "just to be cautious").
4. Writes the result back to the Elasticsearch document as a nested `ai_review` field — `severity_before_ai_review`, `recommended_severity`, `matched_rule_id`, `severity_escalated` (boolean), `reason`. **The original `overall_severity` is never overwritten** — this is a second opinion, not an authority. Nothing in the log file itself is touched; only the indexed document is updated.
5. If `severity_escalated: true`, a dedicated Kibana Alert Rule fires to a 5th Slack channel (`#llm-security-ai-triage`).

**Why a local model, not GPT-4o-mini / Gemini:** the data being reviewed is the exact kind of thing this system exists to catch — potential API keys, PII, jailbreak content. Sending it to a third-party cloud API to *catch leaks* would be its own leak. Cloud models were evaluated and rejected specifically for this reason; Qwen3:8b runs entirely on the same machine as everything else. The context-window size (currently 5 prior turns) is a single constructor parameter, chosen for local hardware — trivially scalable to a full conversation history on stronger hardware.

**Known limitation:** Qwen3:8b is not perfectly reliable. In testing, it once mis-stated a rule's own severity level from the context it was just given (called `LLM01-003`, defined as `high` two lines earlier, "medium"). A larger model (14B tested, no measurable improvement on the specific failure mode — character-level obfuscation like reversed text or base64) or a cloud model would likely be more consistent, but was ruled out for the privacy reason above. This is reported honestly rather than hidden: the AI Triage layer is a *signal*, not a verdict, which is exactly why its output is stored separately and requires the original severity to remain visible alongside it.

---

## Stack

| Component | Role |
|---|---|
| **FastAPI** | Backend API, detection pipeline orchestration |
| **Ollama (Mistral)** | Chat model the user talks to |
| **Ollama (Qwen3:8b)** | AI Triage reviewer — separate model, so the system isn't reviewing itself with the same weights that got manipulated |
| **sentence-transformers (`BAAI/bge-base-en-v1.5`)** | Embedding similarity |
| **Elasticsearch + Kibana + Logstash + Filebeat** | Security log storage, dashboarding, alerting |
| **PostgreSQL** | Chat/message/user storage for the UI |
| **React + Vite + Tailwind** | Chat frontend |
| **Slack** | Alert delivery (5 channels: critical / high / medium / low / AI-triage escalations) |

All infrastructure (ES, Kibana, Logstash, Filebeat, PostgreSQL) runs via a single `docker-compose.yml`.

---

## Log Schema (Elasticsearch)

Every interaction — blocked or not — produces one document:

```json
{
  "event_timestamp": "...",       // when processing finished (blocked or Mistral responded)
  "prompt_received_at": "...",    // when the request arrived (used for latency analysis)
  "user_id": "...",
  "session_id": "...",            // one per frontend load
  "chat_id": "...",               // one per conversation (shared with PostgreSQL)
  "network": { "source_ip", "source_port", "destination_ip", "destination_port" },
  "prompt": "...", "response": "...", "final_response": "...",
  "blocked": true|false,
  "blocked_at": "prompt_stage" | "behavioral_stage" | "embedding_stage" | "response_stage" | null,
  "detection": {
    "prompt_detection": { "triggered_rules": [...], "rule_count": N },
    "response_detection": { ... },
    "behavioral_detection": { "rate_anomaly", "length_anomaly", "repetition_anomaly" },
    "semantic_match": { "flagged", "similarity_score", "closest_match_text", "owasp_category" }
  },
  "triggered_owasp_categories": [...],   // union across all layers
  "triggered_rule_ids": [...],           // union of prompt + response rulebook hits
  "overall_severity": "none|low|medium|high|critical",
  "overall_severity_source": "rulebook:<id>" | "behavioral:<anomaly>" | "embedding" | "none",
  "ai_review": {                          // added later, by the triage agent — optional
    "reviewed_at", "severity_before_ai_review", "recommended_severity",
    "matched_rule_id", "severity_escalated", "reason"
  }
}
```

`overall_severity_source` is intentionally separate from the blocking decision — a `high` severity does **not** imply the request was auto-blocked (e.g. an embedding score in the 0.70–0.72 gray zone is tagged `high`/`medium` but deliberately not blocked). This tripped me up once during development; documenting it here so it doesn't trip up anyone else.

---

## Kibana Dashboard (8 panels)

1. Severity distribution (pie)
2. OWASP category distribution (bar, `triggered_owasp_categories`)
3. Most-triggered rule IDs (pie, `triggered_rule_ids`)
4. Severity over time (stacked bar)
5. Blocked vs. allowed (pie)
6. Blocking stage distribution (pie, `blocked_at`)
7. Severity decision source (pie, `overall_severity_source`)
8. AI Triage — most-matched rule (pie, `ai_review.matched_rule_id`)

---

## Alerting

Five Kibana Alert Rules, each on a `overall_severity: "<tier>"` (or `ai_review.severity_escalated: true`) query, each posting to its own Slack channel via a native Slack (Incoming Webhook) connector. Rules use `On status changes` firing so an ongoing condition doesn't re-alert every check cycle. Messages are built with Mustache templates that loop over `context.hits`, surfacing the actual user, prompt, timestamp, and a ready-to-paste Kibana KQL query per matching log — so an analyst can jump straight from a Slack ping to the exact document in Discover.

---

## Setup

```bash
# 1. Start infrastructure
cd elk
docker compose up -d

# 2. Backend
cd ../backend
pip install -r requirements.txt   # or install individually — see below
python db.py                      # creates PostgreSQL tables
uvicorn app:app --reload --port 5000

# 3. Frontend
cd ../frontend
npm install
npm run dev

# 4. AI Triage (separate, long-running process)
cd ../backend
python ai_triage/agent_triage.py
```

Required local models (via `ollama pull`): `mistral`, `qwen3:8b`.

Two `.env` files are required (both gitignored):
- `elk/.env` — `KIBANA_ENCRYPTION_KEY` (generate via `docker exec -it kibana bin/kibana-encryption-keys generate`), `POSTGRES_PASSWORD`
- `backend/.env` — `POSTGRES_PASSWORD` (same value)

---

## Known Limitations (Reported, Not Hidden)

- **Regex is regex.** Every gap found and fixed during testing (see "Why This Exists") is a reminder that pattern-matching alone cannot cover natural-language variation. The layered design exists *because* of this, not despite it.
- **AI Triage context window is 5 turns.** Deliberately small for local-hardware feasibility; a single parameter change scales it to a full conversation on stronger hardware.
- **Qwen3:8b is not perfectly reliable** (see AI-Assisted Triage section above) — treated as a signal requiring human review, not an automated verdict.


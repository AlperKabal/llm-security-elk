# LLM Security Monitoring & Alerting

A defense-in-depth security monitoring system for LLM-powered chat applications, built around an ELK stack. The project detects, logs, alerts on, and (via an AI-assisted second review with conversational memory) re-evaluates prompt injection, jailbreak attempts, and sensitive data leaks in a local LLM chat pipeline, structured around OWASP LLM Top 10 (2026) categories.

Built as a 7-day internship project. Defensive/blue-team focus throughout: no offensive tooling, no real-world exploit payloads.

---

## Why This Exists

Most LLM security demos stop at "regex catches bad words." This project instead asks: **what happens when a single detection layer isn't enough — and what happens when an attack is split across several messages instead of one?**

Across development, concrete gaps were found and used to justify the architecture:

- **Regex missed a Spanish-language jailbreak** ("Ignora todas las instrucciones...") — English-only patterns don't generalize across languages.
- **Regex missed an acrostic-based instruction override** — a poem whose first letters spelled "IGNORE," which the model then acted on, producing a fabricated "system prompt." Neither regex nor embedding similarity flagged it (embedding score 0.60, below threshold); an AI-based second review (Qwen3:8b) caught it, but only after its prompt was rewritten twice to stop it from either over-triggering on borderline cases or refusing to escalate anything not matching the rulebook word-for-word.
- **Regex missed natural-language phrasing of a real API key leak** — "the API key is: sk-..." wasn't caught until the pattern was extended three separate times (to handle "is"/"as" phrasing, a space instead of `_`/`-`, and a stray colon after "is").
- **A single-message code-word attack survived every layer, until history was added to AI Triage.** A two-turn attack was designed to isolate this: turn 1 privately defines a code word ("sunflower" secretly means "ignore"); turn 2 — with no trigger words at all — asks the model to describe its configuration "sunflower style." Neither the rulebook nor embedding flagged turn 2 in isolation (nothing to match), and the model's actual reply was unrelated filler text with no leak in it either. AI Triage, given the last 5 turns of the conversation alongside the new message, still escalated turn 2 to `high`, explicitly citing in its reasoning that the code word had been "established earlier" — a conclusion that isn't reachable from the message or the response alone, only from the conversation as a whole. This was the deciding test for adding chat history to the triage agent, and it's a good demonstration of why context matters as much as content.

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
│  4. Mistral (Ollama) — with last 10 turns of chat history          │
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
                                  ┌──────────────────┐          ┌─────────────────────────┐
                                  │  Kibana Dashboard  │          │   AI Triage Agent         │
                                  │   (8 panels)        │          │  (Qwen3:8b, every 3 min)  │
                                  └──────────┬─────────┘          │  re-reviews none/low/     │
                                             │                     │  medium severity logs,    │
                                             ▼                     │  WITH prior chat_id turns │
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

If none of the four blocks the request, the prompt (with up to 10 turns of prior chat history from PostgreSQL, prepended as plain conversational context — **not** passed through detection, only to Mistral) goes to Mistral, and the response is then checked by layer 4.

Two independent timestamps are recorded per interaction — `prompt_received_at` (when the request arrived) and `event_timestamp` (when processing finished, whether blocked or answered) — both server-side, never trusted from the client, so response-latency analysis is possible without relying on the browser's clock.

### Embedding threshold, explained

- **Flag threshold:** 0.70 — anything at or above this is logged as `flagged: true` and contributes to `overall_severity`, but does not block on its own.
- **Auto-block threshold:** 0.72 — anything at or above this blocks the request before it reaches Mistral.

The gap between 0.70 and 0.72 is intentional: it's a "gray zone" — logged and severity-tagged, but not strong enough to auto-block. This is exactly the population the AI Triage agent targets. Note that embedding similarity turned out to catch more than expected during testing — it flagged obfuscated variants using an unrelated substitute code word (e.g. `"[X] all previous instructions..."` with `[X]` swapped for a nonsense word), suggesting it responds to sentence-level structure, not just vocabulary. That specific structural pattern was eventually defeated by rephrasing the attack entirely — see the code-word example below.

---

## AI-Assisted Triage

**Problem it solves:** regex and embedding both operate on a single message in isolation, with fixed, human-written criteria. Some manipulation attempts don't match any known pattern and aren't semantically close enough to the reference set to trigger embedding. Worse, some attacks are deliberately split across multiple messages — one message sets something up, a later, individually-harmless-looking message uses it — which no single-message layer can ever catch by design.

**How it works** (`ai_triage/agent_triage.py`):

1. Every 3 minutes, pulls all `none`/`low`/`medium` severity logs from the last 10 minutes that haven't been reviewed yet (`critical`/`high` are excluded — they're already auto-blocked by one of the four layers above, so a second review adds nothing).
2. For each log, pulls up to 5 prior messages from the *same* `chat_id` (not `session_id` — a session can span multiple unrelated chats; a `chat_id` is one coherent conversation) from Elasticsearch for context.
3. Sends the rulebook (in full — every rule ID, pattern, and severity), the embedding threshold, the log's current severity, the conversation history, and the new message to a **local** LLM (Qwen3:8b via Ollama), with instructions to: judge only against the categories above, never lower a severity, only raise it with a concrete reason grounded in those categories (not "just to be cautious") — and explicitly to treat the conversation history as essential context, checking whether the current message activates something set up earlier, and to say so in its reasoning if it does.
4. Writes the result back to the Elasticsearch document as a nested `ai_review` field — `severity_before_ai_review`, `recommended_severity`, `matched_rule_id`, `severity_escalated` (boolean), `reason`. **The original `overall_severity` is never overwritten** — this is a second opinion, not an authority. Nothing in the log file itself is touched; only the indexed document is updated.
5. If `severity_escalated: true`, a dedicated Kibana Alert Rule fires to a 5th Slack channel (`#llm-security-ai-triage`).

**Validating that the history actually gets used (not just carried along):** early tests were inconclusive — every escalation could be explained by the current message or the model's response alone being suspicious enough on their own, without needing the history at all. A cleaner test was designed to rule that out: turn 1 privately establishes "sunflower" as code for "ignore"; turn 2 asks the model to describe its configuration "sunflower style," with no trigger words present in either the prompt or Mistral's (irrelevant, filler) reply. AI Triage still flagged turn 2 as `high`, and its `reason` field explicitly referenced the rule "established earlier" — the only place that information could have come from. That result is what confirmed the history wiring was doing real work, not just sitting unused in the prompt.

**No automatic action is taken on escalation.** A `severity_escalated: true` result does not ban, suspend, or block a user or chat — it only raises severity in the log and notifies Slack. This is intentional: Qwen3:8b is not reliable enough (see below) to be trusted with irreversible actions, and real SOC workflows separate detection from response for the same reason. A human reviews the Slack alert, pulls up the full `chat_id` history in Kibana, and decides.

**Known limitation:** Qwen3:8b is not perfectly reliable. In testing, it once mis-stated a rule's own severity level from the context it was just given (called `LLM01-003`, defined as `high` two lines earlier, "medium"). It also struggles specifically with character-level obfuscation — reversed text and base64-encoded instructions were both missed, even though the same model successfully caught acrostic and cross-lingual variants of the same underlying attack. A larger model (14B tested) showed no measurable improvement on that specific failure mode, and a cloud model was ruled out entirely for the privacy reason below. This is reported honestly rather than hidden: the AI Triage layer is a *signal*, not a verdict, which is exactly why its output is stored separately, requires the original severity to remain visible alongside it, and never triggers automatic action.

**Why a local model, not GPT-4o-mini / Gemini:** the data being reviewed is the exact kind of thing this system exists to catch — potential API keys, PII, jailbreak content. Sending it to a third-party cloud API to *catch leaks* would be its own leak. Cloud models were evaluated and rejected specifically for this reason; Qwen3:8b runs entirely on the same machine as everything else. The context-window size (currently 5 prior turns for triage, 10 for the chat model itself) is a constructor parameter in both cases — trivially scalable to a full conversation history on stronger hardware.

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

## Frontend

A React chat UI (dark theme) sits on top of the backend — sidebar with chat history per user, a user switcher (dropdown, add-new-user supported, no auth — this is a demo surface, not the security boundary), and a chat window with a "typing" indicator. Blocked assistant messages render visually distinct (red) from normal ones.

Two IDs are tracked per conversation, deliberately kept separate:
- **`session_id`** — generated once per frontend page load (`crypto.randomUUID()`), never trusted as authoritative for anything security-relevant.
- **`chat_id`** — generated server-side, on the first message of a new conversation, and persisted in PostgreSQL. This is the ID that both AI Triage's history lookup and the app's own chat history use — one conversation, one `chat_id`, regardless of how many browser sessions touch it.

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

`chat_id` is the join key between this index and PostgreSQL's `chats`/`messages` tables — Elasticsearch owns the security narrative, Postgres owns the UI narrative, and they're queryable side by side without either depending on the other.

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

Five Kibana Alert Rules, each on a `overall_severity: "<tier>"` (or `ai_review.severity_escalated: true`) query, each posting to its own Slack channel via a native Slack (Incoming Webhook) connector. Rules use `On status changes` firing so an ongoing condition doesn't re-alert every check cycle. Messages are built with Mustache templates that loop over `context.hits`, surfacing the actual user, prompt, timestamp, and a ready-to-paste Kibana KQL query per matching log — so an analyst can jump straight from a Slack ping to the exact document in Discover. The AI-triage channel's template additionally includes `severity_before_ai_review`, `recommended_severity`, the model's `reason`, and `ai_review.reviewed_at` — separate from the original event time, so detection latency (how long after the fact the AI caught it) is visible directly in the alert.

---

## Setup

```bash
# 1. Start infrastructure
cd elk
docker compose up -d

# 2. Backend
cd ../backend
pip install -r requirements.txt   # or install individually — see below
python db.py                      # creates PostgreSQL tables (users, chats, messages)
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

Three `.env` files are required (all gitignored):
- `elk/.env` — `KIBANA_ENCRYPTION_KEY` (generate via `docker exec -it kibana bin/kibana-encryption-keys generate`), `POSTGRES_PASSWORD`
- `backend/.env` — `POSTGRES_PASSWORD` (same value)
- `frontend/.env` — `VITE_API_BASE` (backend URL, e.g. `http://localhost:5000`)

---

## Known Limitations (Reported, Not Hidden)

- **Regex is regex.** Every gap found and fixed during testing (see "Why This Exists") is a reminder that pattern-matching alone cannot cover natural-language variation. The layered design exists *because* of this, not despite it.
- **AI Triage context window is 5 turns; the chat model's is 10.** Deliberately small for local-hardware feasibility; a single parameter change scales either to a full conversation on stronger hardware.
- **Qwen3:8b is not perfectly reliable** (see AI-Assisted Triage section above) — treated as a signal requiring human review, never an automated verdict, and never wired to an automatic action.
- **Real-time detection (rulebook/behavioral/embedding) does not see conversation history** — only AI Triage does, and it runs after the fact (every 3 minutes), not in real time. A multi-step attack spread across several messages can pass the real-time layers on each individual message and only get flagged retroactively once AI Triage reviews it. This is a deliberate scope decision (confirmed with mentor) to keep per-message real-time detection independent and auditable — the multi-turn case documented above (the "sunflower" code-word attack) is exactly this scenario, caught by design on the second pass rather than the first.
- **Longer chat-history windows can destabilize a small local model.** Increasing the chat model's context window from 6 to 10 turns produced at least one case of Mistral fabricating an entire multi-turn dialogue that was never asked for, unprompted. This didn't compromise security (the fabricated content was benign), but it's a reminder that "more context" isn't free for a 7B-class model, and is worth watching if the window is scaled up further.
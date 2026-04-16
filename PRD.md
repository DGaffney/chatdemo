# AI Front Desk — Product Requirements Document

**Prototype for Brightwheel Take-Home Assignment**
**Author:** Devin Gaffney
**Status:** Draft v1

---

## 1. Problem

Daycare administrators spend hours each day answering the same questions by phone, text, and email. Parents — anxious, time-pressed, often in the middle of something else — wait on hold or refresh inboxes for answers that exist in handbooks they can't easily search on a phone. The operator loses billable hours to repetitive lookup. The parent loses trust every time a sick kid, a missed lunch, or a schedule change goes unanswered for four hours.

Most of these questions are knowable. The handbook says the center is closed on Veterans Day. Tuition for infants is a number. The sick-kid policy is written down. What's missing is not the *information*; it's an always-available, trustworthy interface to it that also knows when to escalate to a human.

## 2. Users and their needs

### 2.1 The Parent (chat user)

Sarah is a working mother with a two-year-old at Sunrise Early Learning. It's 6:47 AM. Her daughter feels warm. She needs to know — right now, before she leaves for a 7:30 meeting — whether she can drop off at the center or needs to call in sick.

What Sarah needs:
- **Speed.** An answer in under 30 seconds, not a callback at 10 AM.
- **Specificity.** "Our sick policy" at Sunrise, not generic daycare advice pulled from the internet.
- **Trust.** When the answer cites the handbook, she believes it. When the system isn't sure, it says so rather than making something up.
- **A graceful handoff.** When her question is sensitive (a custody issue, a medical concern, a billing dispute), she needs to be escalated to a human — with her question preserved so she doesn't have to retell it.
- **Mobile-first.** She's on her phone, one-handed, with a toddler on her hip.

What Sarah must *never* experience:
- A confident wrong answer about health, safety, or money.
- A chatbot that loops when it doesn't know something.
- Having to re-explain her question to a human after the bot gave up.

### 2.2 The Operator (admin / director)

Maria runs Sunrise Early Learning. She has 42 kids enrolled, 8 staff, and a phone that rings 30+ times a day with the same dozen questions. She is not a software buyer and does not want to be. She wants her time back.

What Maria needs:
- **Simple onboarding.** Answer a handful of questions about her center — hours, tuition tiers, holidays, sick policy, meals — and have a working front desk. No CMS, no configuration files, no "import your handbook as a structured schema."
- **Visibility.** A single place to see what parents are asking, what the AI answered, and what it couldn't handle.
- **A triage queue, not an inbox.** When the AI escalates, she doesn't want 40 individual conversations. She wants *"8 questions about holiday closures this week — here's the cluster, here's a draft answer, one click to resolve all."*
- **Low-effort improvement.** Every time she answers a triaged question, the system should remember that answer for next time. The "learning" is invisible — she just answers parents, and the bot gets smarter.
- **Trustworthy escalation.** When the AI hands off, Maria needs the parent's question, the parent's email, and the AI's reasoning — so she can reply in one message and close the loop.
- **Visibility into where her handbook is failing.** If 12 parents this month asked something her handbook doesn't cover, she wants to know.

What Maria must *never* experience:
- The AI giving parents wrong information about health or safety policies she is liable for.
- Being unable to correct or override the AI.
- Losing a tour inquiry (a *lead*, actual revenue) to a bot that tried to handle it itself.

## 3. Scope: prototype v1

One center. One handbook. Single-turn Q&A (no multi-turn memory in v1). One tool today (handbook retrieval), but the orchestration layer is built so adding tools — calendar lookup, CRM integration, payment status, real-time staff paging — is additive, not invasive.

Explicitly **in scope** for the prototype:

- Parent chat interface (mobile-first)
- Intent classification + topic tagging on every question
- Grounded answers against a center-specific handbook
- Sensitive-topic detection and graceful escalation
- Operator dashboard with triage queue, topic-grouped unanswered questions, and "novel topic" discovery
- Operator knowledge editor (override/add Q&A pairs)
- Simple center onboarding flow
- Pre-filled answers for the assignment's example questions
- Conversation logging with intent × topic × confidence tags
- Escalation handoff that captures parent email + preserved context

Explicitly **out of scope** for v1 (but noted as extension paths):

- Multi-turn conversation memory
- Voice input/output
- Real-time staff paging (SMS, Slack)
- Multi-center tenancy
- Fine-grained per-family personalization
- Billing or PII lookup against real daycare management systems

## 4. Key product decisions

### 4.1 Questions are not one problem

The five example questions in the assignment are three different product categories:

| Question type | Example | System behavior |
|---|---|---|
| **Lookup** | "Are you open Veterans Day?" / "What's tuition for infants?" | Retrieve + answer. High confidence threshold. Cite source. |
| **Policy judgment** | "My kid has a fever, can they come in?" / "I forgot to pack lunch." | Retrieve policy + answer conservatively. Default to "here's the policy, here's what typically happens, and I've flagged staff." Never make the call on edge cases. |
| **Lead capture** | "How do I schedule a tour?" | Collect parent info, confirm tour request, *priority-escalate to operator.* This is revenue; it must never hit voicemail. |
| **Sensitive** | Custody, medical, billing disputes, anything about another child | Do not attempt to answer. Preserve question. Escalate with email. |

Treating these identically is the mistake most prototypes will make. Treating them differently is the insight.

### 4.2 Taxonomy: intent × topic (two dimensions)

Every question gets two tags.

**Intent** (how the system handles it): `lookup | policy | lead | sensitive`

**Topic** (what it's about): `hours | tuition | sick_policy | meals | tours | enrollment | custody | billing | staff | curriculum | safety | other`

When `topic == "other"`, the classifier also writes a free-text `topic_guess` field. The operator dashboard surfaces novel topic guesses with counts, so Maria can see "5 parents asked about 'nap mats' — we don't have a handbook section for that" and promote it to a real topic. This is how the taxonomy itself learns.

### 4.3 Confidence thresholds are per-intent, not global

- Lookup: high bar for confidence, but when the handbook has a clear answer, answer it. Wrong confidence = wrong number.
- Policy: lower confidence bar than lookup, but *always* append "I've flagged your question for staff follow-up" — the answer is informational, not authoritative. This is the liability shield.
- Lead: never "confident" enough to handle autonomously. Always captures + escalates.
- Sensitive: zero-confidence handling. Always escalates.

### 4.4 The operator experience is correcting, not authoring

Every time the AI escalates, Maria answers once. That answer is written back to the knowledge base and checked first on future queries. She is not a content author; she is a teacher. The learning loop is the product.

## 5. System architecture

### 5.1 Stack

- **Python 3.11, async FastAPI** — async matters here because LLM latency dominates; concurrent requests shouldn't queue
- **LangGraph** for orchestration — the state machine is the extensibility story
- **LiteLLM** for model provider abstraction — Claude today, swappable to GPT-4o, Gemini, or open-weight models via config
- **LangSmith** for tracing — drop-in observability, free shareable trace URLs per conversation
- **SQLite** via `aiosqlite` — three tables, one file, zero setup
- **Pydantic** for structured LLM outputs — validated classifier schemas, not regex
- **Vite + React + TypeScript + shadcn/ui** — two pages (parent chat, operator dashboard)
- **Docker Compose** — one-command local run
- **`.env` + pydantic-settings** — all config via environment variables; no secrets in code

### 5.2 The orchestration graph (LangGraph)

```
[Parent question arrives]
        ↓
[Pre-call guardrail: block obvious misuse]
        ↓
[Classify intent + topic + sensitivity]
        ↓
    ┌───┴───────┬──────────┬──────────────┐
[Lookup]    [Policy]    [Lead]        [Sensitive]
    ↓           ↓           ↓              ↓
[Retrieve   [Retrieve   [Collect       [Compose
handbook]   policy +    parent info]   handoff
    ↓       overrides]      ↓          message]
[Generate       ↓       [Priority-         ↓
answer +    [Generate   flag in         [Write to
cite]       conservative triage]       escalation
    ↓       answer +        ↓          queue]
[Confidence guardrail]  [Confirm           ↓
check]          ↓       to parent]     [Return
    ↓       [Confidence     ↓           handoff
[Post-call  check]      [Log]           reply]
citation        ↓           ↓
verify]     [Post-call  [Return]
    ↓       citation
[Log]       verify]
    ↓           ↓
[Return]    [Log]
                ↓
            [Return]
```

Every terminal node writes to the `conversations` table. Every escalation also writes to `triage_queue`. Every low-confidence answer writes to `triage_queue` with `reason="low_confidence"`.

Adding a new intent is adding a branch. Adding a new tool (calendar lookup, CRM) is adding a node inside an intent branch. The graph makes the extensibility claim structurally visible.

### 5.3 Knowledge base: layered and extensible

Three layers, checked in order:

1. **Operator overrides** (`knowledge_overrides` table) — things Maria has explicitly answered or corrected. Always wins.
2. **Center-specific handbook** (`/handbook/*.md`) — markdown files with frontmatter (`category:`, `updated_at:`). Loaded at startup, chunked, indexed.
3. **Generic daycare knowledge** (`/handbook/_generic/*.md`) — baseline answers for common questions that ship out-of-the-box. Overridable by center-specific handbook.

The extensibility story:
- New markdown file → new knowledge, no code change
- Operator answers triaged question → override written, checked first going forward
- New center onboards → their `/handbook/` directory is populated by onboarding flow
- Migration to production: swap flat markdown + keyword match for a vector store + reranker without changing the retrieval interface

### 5.4 Data model (SQLite)

```sql
CREATE TABLE conversations (
  id INTEGER PRIMARY KEY,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  session_id TEXT,
  question TEXT NOT NULL,
  answer TEXT,
  intent TEXT,              -- lookup | policy | lead | sensitive
  topic TEXT,               -- from closed vocabulary
  topic_guess TEXT,         -- populated when topic = 'other'
  confidence REAL,          -- 0.0–1.0
  escalated BOOLEAN DEFAULT 0,
  escalation_reason TEXT,   -- sensitive | low_confidence | lead | operator_review
  policy_cited TEXT,        -- handbook section referenced
  guardrail_flags TEXT      -- JSON array of triggered guardrails
);

CREATE TABLE knowledge_overrides (
  id INTEGER PRIMARY KEY,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  topic TEXT,
  question_pattern TEXT,    -- canonical version of the question
  answer TEXT,
  author TEXT,              -- which operator wrote it
  source_conversation_id INTEGER  -- which triaged question prompted this
);

CREATE TABLE triage_queue (
  id INTEGER PRIMARY KEY,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  conversation_id INTEGER NOT NULL,
  parent_email TEXT,        -- captured for reply
  priority TEXT,            -- high (leads, sensitive) | normal (low_confidence)
  status TEXT DEFAULT 'open',  -- open | resolved | dismissed
  resolved_at TIMESTAMP,
  resolved_by TEXT,
  resolution_text TEXT,
  FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE center_config (
  key TEXT PRIMARY KEY,
  value TEXT
);
-- Populated by onboarding: center_name, operator_email, hours_summary, 
-- sick_policy_summary, tuition_infant, tuition_toddler, etc.
```

### 5.5 Guardrails

Layered and aligned with LiteLLM's pre/during/post model so migration to proxy-based guardrails is clean.

**Pre-call guardrails** (before the LLM sees anything):
- Block obvious out-of-domain misuse (prompt injection, unrelated topics)
- Detect sensitive keywords and force-route to `sensitive` intent (custody, medical emergency, abuse, legal)

**In-call guardrails** (via system prompts and structured outputs):
- Classifier must return a valid enum value (Pydantic validation)
- Answer generator is instructed: "If the handbook does not contain this information, say so. Do not infer numeric values (prices, times, ages) that are not explicitly present."

**Post-call guardrails** (after the LLM response):
- **Citation verification** — if intent is `lookup` or `policy`, verify the answer references a handbook section. If not, lower confidence and flag for triage.
- **Numeric sanity check** — if the answer contains a dollar amount, percentage, or time, verify it appears in the retrieved context. Prevents hallucinated tuition numbers.

All guardrail triggers are logged to `conversations.guardrail_flags` for audit.

### 5.6 Clustering and novel-question surfacing

v1 (prototype): group unanswered questions by `topic`. Within `topic = 'other'`, group by `topic_guess` (LLM-assigned free-text category).

v2 (extension, noted in writeup): embedding-based clustering within topic to catch near-duplicates across phrasing ("Are you open 12/24?" vs "Are you closed Christmas Eve?"). Clusters surface as a single triage item with a count.

The operator dashboard view for clusters:

```
🔴 8 questions about holiday_closures  [View] [Answer all]
🟡 5 questions about nap_mats (novel topic)  [View] [Add to handbook]
🟢 3 low-confidence questions about sick_policy  [View]
```

### 5.7 Observability

- **Per-conversation tracing** via LangSmith (drop-in, free tier)
- **Structured logging** to stdout (Docker-friendly) in JSON
- **SQLite as operational observability** — the `conversations` table *is* the audit log, queryable by the operator view
- Every LLM call logs: model, prompt tokens, completion tokens, latency, cost estimate (via LiteLLM)

### 5.8 Escalation flow

When the graph routes to escalation:

1. System composes a reply to the parent: *"I wasn't able to answer this confidently. I've flagged your question for Maria at Sunrise, and she'll respond to {email} within business hours. Is there anything else I can help with in the meantime?"*
2. Parent's email is captured (prompted in the chat if not already known via session).
3. Triage item is written with `priority='high'` (sensitive/lead) or `'normal'` (low_confidence).
4. Operator dashboard surfaces it grouped by topic.
5. When operator resolves it, the `resolution_text` is optionally promoted to a `knowledge_overrides` entry with one click.

## 6. Onboarding flow

New operator opens the app. A guided setup asks ~8 questions:

1. What's the name of your center?
2. What's your email? (for escalations)
3. What are your operating hours?
4. What holidays are you closed?
5. What are your tuition tiers? (Infant / Toddler / Preschool)
6. What's your policy on sick children? (fever threshold, return criteria)
7. Do you provide meals? (what's typical, can parents bring food, allergies)
8. How do parents schedule a tour?

Answers are written to `center_config` and materialized as markdown files in `/handbook/`. The center is immediately operational. The onboarding is the handbook.

Pre-filled with sensible defaults for the assignment's example questions (Sunrise Early Learning, fictional Portland OR location) so the prototype works out-of-the-box on first run without any configuration.

## 7. File structure

```
/ai-front-desk
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── README.md
├── backend/
│   ├── pyproject.toml
│   ├── main.py                 # FastAPI app, route mounting
│   ├── settings.py             # pydantic-settings, all env vars
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py            # LangGraph state definition
│   │   ├── nodes/
│   │   │   ├── classify.py
│   │   │   ├── retrieve.py
│   │   │   ├── answer.py
│   │   │   ├── escalate.py
│   │   │   └── guardrails.py
│   │   └── graph.py            # graph assembly
│   ├── knowledge/
│   │   ├── loader.py           # markdown → chunks
│   │   ├── retriever.py        # keyword match (v1), interface for vector (v2)
│   │   └── overrides.py        # operator override layer
│   ├── db/
│   │   ├── schema.sql
│   │   ├── conversations.py
│   │   ├── triage.py
│   │   └── overrides.py
│   ├── prompts/
│   │   ├── classifier.py
│   │   ├── lookup_answer.py
│   │   ├── policy_answer.py
│   │   ├── lead_capture.py
│   │   └── escalate.py
│   ├── api/
│   │   ├── parent.py           # POST /api/ask, SSE stream
│   │   ├── operator.py         # GET /api/triage, POST /api/override
│   │   └── onboarding.py
│   ├── handbook/               # default Sunrise center
│   │   ├── _generic/
│   │   │   ├── sick_policy.md
│   │   │   └── meals.md
│   │   ├── hours.md
│   │   ├── tuition.md
│   │   ├── holidays.md
│   │   ├── tours.md
│   │   └── sick_policy.md
│   └── tests/
│       ├── test_questions.json # test suite of canned Q&A pairs
│       └── run_evals.py        # CI-style eval runner
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx
│       ├── pages/
│       │   ├── ParentChat.tsx
│       │   ├── OperatorDashboard.tsx
│       │   └── Onboarding.tsx
│       ├── components/
│       │   ├── ChatMessage.tsx
│       │   ├── TriageQueue.tsx
│       │   ├── KnowledgeEditor.tsx
│       │   └── TopicCluster.tsx
│       └── lib/
│           ├── api.ts
│           └── sse.ts
```

## 8. Environment configuration

`.env.example`:

```
# LLM provider (LiteLLM handles routing)
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
DEFAULT_MODEL=anthropic/claude-sonnet-4-5
CLASSIFIER_MODEL=anthropic/claude-haiku-4-5  # cheaper/faster for classification

# LangSmith (optional, enables tracing)
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=ai-front-desk

# App
DATABASE_PATH=/data/frontdesk.db
HANDBOOK_PATH=/app/backend/handbook
OPERATOR_EMAIL=maria@sunrise-daycare.example
CENTER_NAME=Sunrise Early Learning

# Feature flags
ENABLE_CITATION_GUARDRAIL=true
ENABLE_NUMERIC_GUARDRAIL=true
CONFIDENCE_THRESHOLD_LOOKUP=0.75
CONFIDENCE_THRESHOLD_POLICY=0.65
```

All config via `pydantic-settings`. No secrets in code. `.env.example` checked in, `.env` gitignored.

## 9. Deployment

One-command local run:

```bash
docker compose up
```

Single Docker image: backend serves the built React bundle as static files, exposes `/api/*` for dynamic routes. One port, one URL, suitable for demo.

Deploy target for submission: Render.com or Fly.io (FastAPI-friendly, free tier, GitHub-connected). Single public URL for the hosted prototype.

## 10. Testing

`test_questions.json`:

```json
[
  {
    "question": "Are you open on Veterans Day?",
    "expected_intent": "lookup",
    "expected_topic": "holidays",
    "should_cite": "holidays.md",
    "should_escalate": false
  },
  {
    "question": "My daughter has a 100.4 fever, can she come in?",
    "expected_intent": "policy",
    "expected_topic": "sick_policy",
    "should_cite": "sick_policy.md",
    "should_escalate": false,
    "must_contain_staff_notification": true
  },
  {
    "question": "I want to schedule a tour.",
    "expected_intent": "lead",
    "expected_topic": "tours",
    "should_escalate": true,
    "escalation_priority": "high"
  },
  {
    "question": "What's your custody pickup policy for divorced parents?",
    "expected_intent": "sensitive",
    "expected_topic": "custody",
    "should_escalate": true,
    "must_not_answer_autonomously": true
  }
  // ... ~15 total, including adversarial edge cases
]
```

`run_evals.py` hits the local API with each question, validates the response against expectations, prints a pass/fail table. Runnable via `make test`.

## 11. Evaluation criteria (Brightwheel's rubric, mapped)

| Brightwheel criterion | How this PRD addresses it |
|---|---|
| **Scope & completeness** | Clear v1 scope, explicit extension path, docker-compose deployable |
| **Persuasiveness** | Operator triage queue + novel-topic discovery is the killer feature; intent×topic taxonomy is a real insight |
| **User empathy** | Distinguishes four question types with different handling; never-miss-a-lead thesis; sick-kid liability shield |
| **Uniqueness** | LangGraph state machine as extensibility story; citation + numeric post-call guardrails; "operator is a teacher not an author" framing |

## 12. Extension paths (post-prototype)

- Multi-turn conversation memory (LangGraph checkpointing supports this natively)
- Voice interface (Twilio + Whisper + TTS — fits the graph as an input/output adapter)
- Embedding-based clustering for near-duplicate questions
- Real-time staff paging via SMS / Slack for high-priority escalations
- Multi-center tenancy (partition the database, per-center handbook directories)
- Replace flat-file retrieval with vector store + reranker (interface is already abstracted)
- Per-family personalization (enrollment data integration)
- Migrate homegrown guardrails to LiteLLM proxy guardrails (Presidio for PII, Bedrock Guardrails for content moderation)

---

*End of PRD v1.*
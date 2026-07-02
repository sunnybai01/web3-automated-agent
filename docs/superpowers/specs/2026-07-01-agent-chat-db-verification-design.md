# Agent Chat Database-Driven Verification V1 Design

## 1. Context And Goal

This project currently runs a long-lived Python pipeline for fetch, dedup, classify, verify, score, and dispatch. The existing web surface is Streamlit and does not support interactive agent chat workflows.

V1 goal is to add a Next.js + CopilotKit frontend that enables read-only agent chat for:

- selecting records from the database (not URL paste),
- automatically performing reliability verification,
- returning structured evidence and confidence scores,
- generating implementation options based on verified facts.

V1 is strictly read-only. No automatic execution or side-effect actions are allowed.

## 2. Scope

In scope:

- Next.js chat UI with CopilotKit.
- Mixed target selection mode:
  - precise mode: `event_id`
  - batch mode: `source_name + time_window + limit`
- Agent orchestration actions for selecting targets, verifying, and proposing implementation options.
- Reuse existing Python verifier logic from `src/verifier/` as backend capability.
- Structured reliability output: score + level + verdict + evidence + unknowns + conflicts.

Out of scope:

- Full automation/execution actions.
- Workflow write-back actions (except optional observability logs).
- Replacing the existing scheduled ingestion pipeline.

## 3. Existing Assets To Reuse

- Data model:
  - `events`, `event_sources`, `raw_signals`, `source_health` in `src/db/models.py`.
- Verification layers:
  - origin identity anchoring in `src/verifier/whitelist.py`
  - cross-reference checks in `src/verifier/cross_reference.py`
  - security checks in `src/verifier/security_api.py`
  - orchestration in `src/verifier/verifier.py`
- Existing event fields that can support chat output:
  - title, description, amount, deadline, source_url, application_url, ecosystem, source_platform, verification_log.

## 4. High-Level Architecture

1. Frontend (Vercel):

- Next.js App Router application with CopilotKit chat component.
- User input for mixed target mode parameters.
- Chat timeline showing reliability results and implementation options.

2. Chat Orchestration Layer (Vercel server functions):

- CopilotKit actions as the orchestration boundary.
- Input validation, policy checks (read-only guard), and response formatting.
- Calls backend read-only verification APIs.

3. Verification Service (Python, long-running platform):

- New read-only API endpoints wrapping existing database queries and verifier pipeline.
- Deterministic scoring engine for confidence score.
- LLM summarization layer only for explanation and implementation options.

4. Data Layer:

- PostgreSQL with read-only credentials for chat path.
- Existing pipeline remains write-enabled in current deployment environment.

## 5. Mixed Target Selection Contract

### Input Contract

```json
{
  "mode": "mixed",
  "event_id": 123,
  "source_name": "github_web3_bounties",
  "from": "2026-06-28T00:00:00Z",
  "to": "2026-07-01T00:00:00Z",
  "limit": 20
}
```

Resolution rules:

1. If `event_id` is present, select exactly that event.
2. Otherwise use `source_name + time window` query.
3. `limit` defaults to a safe value (for example 20) and has a hard cap (for example 100).
4. If query returns zero records, return explicit `no_data` response with filter echo.

## 6. Reliability Evaluation Model

### 6.1 Output Schema

```json
{
  "score": 0,
  "level": "low|medium|high",
  "verdict": "untrusted|caution|trusted",
  "evidence": [
    {
      "category": "origin|consistency|cross_reference|security|history",
      "detail": "string",
      "source": "db|url|verifier_layer",
      "weight": 0,
      "impact": "positive|negative|neutral"
    }
  ],
  "unknowns": ["string"],
  "conflicts": ["string"]
}
```

### 6.2 Scoring Policy (Rule-First)

- Rule engine computes score and verdict.
- LLM is not allowed to mutate factual fields or score values.
- High confidence requires cross-reference support; without it, score ceiling applies (for example <= 80).

Suggested weighted dimensions:

- Origin trust: 25
- Content completeness: 15
- Internal consistency: 20
- Cross-reference consistency: 25
- Security/risk penalties: -20 to 0
- Historical source reliability bonus: up to +15

Final score is clamped to [0, 100].

Level mapping:

- high: >= 80
- medium: 55-79
- low: < 55

Verdict mapping:

- trusted: high and no major conflict
- caution: medium or unresolved conflicts
- untrusted: low or critical security failure

## 7. Agent Workflow (Read-Only)

1. User asks for analysis in chat.
2. Agent calls `selectTargets` action.
3. Agent calls `verifyFromDatabase` action:

- fetch event records and related source evidence,
- execute verifier layers,
- run scoring policy,
- build structured evidence object.

4. Agent calls `proposeImplementationOptions` action:

- use only verified facts,
- produce 2-3 implementation options with assumptions clearly marked.

5. Chat response sections:

- reliability summary,
- key evidence,
- unknowns/conflicts,
- implementation options.

No side-effect action is permitted in V1.

## 8. CopilotKit Action Design (V1)

Required actions:

1. `selectTargets(params)`

- validates mixed mode params
- resolves target event ids

2. `verifyFromDatabase(targetIds)`

- reads event + source evidence
- runs verifier pipeline
- returns reliability schema

3. `explainEvidence(verificationResult)`

- converts evidence to user-readable explanation while preserving original facts

4. `proposeImplementationOptions(verifiedFacts)`

- returns options by complexity tier: light/standard/advanced
- includes assumptions and constraints

Optional action: 5. `compareCandidates(targetIds)`

- batch comparison table by score and evidence confidence

## 9. API Boundary Proposal

Python verification service endpoints (read-only):

- `POST /api/v1/chat/select-targets`
- `POST /api/v1/chat/verify`
- `POST /api/v1/chat/propose-options`

Security and policy controls:

- use separate read-only DB user for chat APIs,
- reject any non-GET/POST side-effect intent at service layer,
- request signing between Next.js and Python service,
- strict timeout and circuit breaker on external checks.

## 10. Failure Handling And Degradation

- Database unavailable:
  - return explicit `data_unavailable`, no guessed conclusions.
- External cross-reference timeout:
  - mark evidence as `unknown`, apply score penalty, keep response usable.
- Partial verifier failure:
  - include layer-level failure detail in evidence and conflicts.
- No related records:
  - return normalized empty response and suggested next filters.

## 11. Observability

Track these metrics for quality:

- verification request count / latency / error rate,
- score distribution,
- percent of responses with unresolved unknowns,
- high-score false positive rate (offline labeled set),
- source-level reliability drift over time.

Structured logs should include:

- request filters,
- selected target ids,
- per-layer outcomes,
- final score and verdict,
- model/provider used for explanation.

## 12. Test Strategy

1. Unit tests:

- mixed mode target resolution rules,
- scoring policy boundaries and clamping,
- verdict mapping,
- read-only policy guard.

2. Integration tests:

- verify action with seeded DB fixtures,
- batch mode query correctness,
- degraded response when cross-reference fails.

3. Prompt-contract tests:

- LLM explanation must not alter facts,
- implementation options must cite verified facts.

4. Regression set:

- labeled historical events (trusted/caution/untrusted),
- monitor precision/recall and specifically high-score false positives.

## 13. Rollout Plan

Phase 1:

- backend read-only verification APIs,
- scoring rule engine extraction,
- Next.js + CopilotKit skeleton with select + verify + explain.

Phase 2:

- implementation option generation with strict verified-fact grounding,
- comparison view for batch selection.

Phase 3:

- evaluation dashboard and reliability drift monitoring,
- model/prompt hardening.

## 14. Deployment Guidance

- Keep Python worker + verifier service on a long-running platform.
- Deploy Next.js chat UI and orchestration on Vercel.
- Use managed PostgreSQL with separate credentials:
  - pipeline writer user,
  - chat read-only user.
- Keep secrets isolated by environment and service role.

## 15. Acceptance Criteria (V1)

- User can analyze by `event_id` or `source_name + time_window` from chat.
- Agent automatically retrieves DB records and runs reliability verification.
- Response always includes structured reliability object.
- Response includes implementation options grounded in verified facts.
- No write side effects occur in chat path.

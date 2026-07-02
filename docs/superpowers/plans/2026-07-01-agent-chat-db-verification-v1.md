# Agent Chat Database-Driven Verification V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only Next.js + CopilotKit chat experience that selects events from database targets (mixed mode), runs reliability verification using existing Python verifier capabilities, and returns score + evidence + grounded implementation options.

**Architecture:** Add a Python read-only chat verification API layer on top of the existing DB and verifier modules, then integrate a new Next.js frontend using CopilotKit actions that call this API. Keep write-capable pipeline runtime unchanged and isolate chat traffic using read-only DB credentials.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, pytest, Next.js App Router, TypeScript, CopilotKit, Vercel

---

### Task 1: Add Read-Only Chat Verification Backend Skeleton

**Files:**

- Modify: `requirements.txt`
- Create: `src/chat_api/__init__.py`
- Create: `src/chat_api/app.py`
- Create: `src/chat_api/schemas.py`
- Create: `src/chat_api/auth.py`
- Create: `tests/chat_api/test_health.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/chat_api/test_health.py
from fastapi.testclient import TestClient

from src.chat_api.app import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    resp = client.get("/api/v1/chat/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/chat_api/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError` for `fastapi` or missing `src.chat_api.app`.

- [ ] **Step 3: Add dependencies and minimal implementation**

```txt
# requirements.txt (append)
fastapi>=0.115.0
uvicorn>=0.30.0
```

```python
# src/chat_api/__init__.py
"""Read-only chat API package."""
```

```python
# src/chat_api/schemas.py
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
```

```python
# src/chat_api/auth.py
from fastapi import Header, HTTPException


async def verify_internal_key(x_internal_key: str = Header(default="")) -> None:
    # V1 allows empty key in local tests; hardened in later task.
    if x_internal_key is None:
        raise HTTPException(status_code=401, detail="missing internal key")
```

```python
# src/chat_api/app.py
from fastapi import FastAPI

from .schemas import HealthResponse

app = FastAPI(title="Web3 Agent Chat API", version="v1")


@app.get("/api/v1/chat/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/chat_api/test_health.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt src/chat_api tests/chat_api/test_health.py
git commit -m "feat(chat-api): add fastapi skeleton and health endpoint"
```

### Task 2: Implement Mixed Target Selection Endpoint

**Files:**

- Create: `src/chat_api/selection_service.py`
- Modify: `src/chat_api/schemas.py`
- Modify: `src/chat_api/app.py`
- Create: `tests/chat_api/test_select_targets.py`

- [ ] **Step 1: Write the failing test for mixed mode resolution**

```python
# tests/chat_api/test_select_targets.py
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from src.chat_api.app import app


def test_select_targets_prefers_event_id(monkeypatch):
    client = TestClient(app)

    def fake_select(params):
        assert params["event_id"] == 7
        return [7]

    monkeypatch.setattr("src.chat_api.selection_service.select_target_event_ids", fake_select)

    resp = client.post(
        "/api/v1/chat/select-targets",
        json={
            "mode": "mixed",
            "event_id": 7,
            "source_name": "rss_grants",
            "from": datetime(2026, 6, 28, tzinfo=timezone.utc).isoformat(),
            "to": datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat(),
            "limit": 20,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["target_event_ids"] == [7]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/chat_api/test_select_targets.py -v`
Expected: FAIL because endpoint/service is not implemented.

- [ ] **Step 3: Implement schemas, service, and endpoint**

```python
# src/chat_api/schemas.py (append)
from datetime import datetime
from typing import Literal


class SelectTargetsRequest(BaseModel):
    mode: Literal["mixed"] = "mixed"
    event_id: int | None = None
    source_name: str | None = None
    from_: datetime | None = None
    to: datetime | None = None
    limit: int = 20

    class Config:
        populate_by_name = True
        fields = {"from_": "from"}


class SelectTargetsResponse(BaseModel):
    target_event_ids: list[int]
    no_data: bool = False
```

```python
# src/chat_api/selection_service.py
from sqlalchemy import select

from src.db.database import SessionLocal
from src.db.models import Event, EventSource


def select_target_event_ids(params: dict) -> list[int]:
    event_id = params.get("event_id")
    if event_id:
        return [event_id]

    source_name = params.get("source_name")
    from_dt = params.get("from")
    to_dt = params.get("to")
    limit = min(max(int(params.get("limit", 20)), 1), 100)

    if not source_name or not from_dt or not to_dt:
        return []

    db = SessionLocal()
    try:
        stmt = (
            select(Event.id)
            .join(EventSource, EventSource.event_id == Event.id)
            .where(EventSource.source_name == source_name)
            .where(Event.created_at >= from_dt)
            .where(Event.created_at <= to_dt)
            .order_by(Event.created_at.desc())
            .limit(limit)
        )
        return [row[0] for row in db.execute(stmt).all()]
    finally:
        db.close()
```

```python
# src/chat_api/app.py (append)
from .schemas import SelectTargetsRequest, SelectTargetsResponse
from .selection_service import select_target_event_ids


@app.post("/api/v1/chat/select-targets", response_model=SelectTargetsResponse)
def select_targets(payload: SelectTargetsRequest) -> SelectTargetsResponse:
    params = payload.model_dump(by_alias=True)
    ids = select_target_event_ids(params)
    return SelectTargetsResponse(target_event_ids=ids, no_data=len(ids) == 0)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/chat_api/test_select_targets.py tests/chat_api/test_health.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/chat_api tests/chat_api/test_select_targets.py
git commit -m "feat(chat-api): add mixed-mode select-targets endpoint"
```

### Task 3: Build Rule-First Reliability Scoring Engine

**Files:**

- Create: `src/chat_api/scoring.py`
- Modify: `src/chat_api/schemas.py`
- Create: `tests/chat_api/test_scoring.py`

- [ ] **Step 1: Write failing unit tests for score boundaries and verdict mapping**

```python
# tests/chat_api/test_scoring.py
from src.chat_api.scoring import compute_reliability


def test_score_is_clamped_to_0_100():
    result = compute_reliability(
        origin=30,
        completeness=30,
        consistency=30,
        cross_reference=30,
        security_penalty=-50,
        history_bonus=20,
        has_cross_reference=True,
        has_major_conflict=False,
    )
    assert result["score"] == 100


def test_high_requires_cross_reference():
    result = compute_reliability(
        origin=25,
        completeness=15,
        consistency=20,
        cross_reference=0,
        security_penalty=0,
        history_bonus=10,
        has_cross_reference=False,
        has_major_conflict=False,
    )
    assert result["score"] <= 80
    assert result["level"] != "high"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/chat_api/test_scoring.py -v`
Expected: FAIL with missing module/function.

- [ ] **Step 3: Implement deterministic scoring logic**

```python
# src/chat_api/scoring.py
from dataclasses import dataclass


@dataclass
class ReliabilityResult:
    score: int
    level: str
    verdict: str


def _level(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _verdict(level: str, has_major_conflict: bool, critical_security_failure: bool) -> str:
    if critical_security_failure:
        return "untrusted"
    if level == "high" and not has_major_conflict:
        return "trusted"
    if level == "low":
        return "untrusted"
    return "caution"


def compute_reliability(
    *,
    origin: int,
    completeness: int,
    consistency: int,
    cross_reference: int,
    security_penalty: int,
    history_bonus: int,
    has_cross_reference: bool,
    has_major_conflict: bool,
    critical_security_failure: bool = False,
) -> dict:
    raw = origin + completeness + consistency + cross_reference + security_penalty + history_bonus
    score = max(0, min(100, raw))

    if not has_cross_reference:
        score = min(score, 80)

    level = _level(score)
    if not has_cross_reference and level == "high":
        level = "medium"

    verdict = _verdict(level, has_major_conflict, critical_security_failure)

    return {
        "score": score,
        "level": level,
        "verdict": verdict,
    }
```

```python
# src/chat_api/schemas.py (append)
class EvidenceItem(BaseModel):
    category: str
    detail: str
    source: str
    weight: int
    impact: str


class VerifyResponse(BaseModel):
    score: int
    level: str
    verdict: str
    evidence: list[EvidenceItem]
    unknowns: list[str]
    conflicts: list[str]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/chat_api/test_scoring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/chat_api/scoring.py src/chat_api/schemas.py tests/chat_api/test_scoring.py
git commit -m "feat(chat-api): add rule-first reliability scoring engine"
```

### Task 4: Implement Verify Endpoint Reusing Existing Verifier

**Files:**

- Create: `src/chat_api/verify_service.py`
- Modify: `src/chat_api/app.py`
- Create: `tests/chat_api/test_verify.py`

- [ ] **Step 1: Write failing integration-style test for verify endpoint shape**

```python
# tests/chat_api/test_verify.py
from fastapi.testclient import TestClient

from src.chat_api.app import app


def test_verify_endpoint_returns_structured_payload(monkeypatch):
    client = TestClient(app)

    def fake_verify(target_ids):
        assert target_ids == [101]
        return {
            "score": 78,
            "level": "medium",
            "verdict": "caution",
            "evidence": [
                {
                    "category": "origin",
                    "detail": "domain match",
                    "source": "verifier_layer",
                    "weight": 20,
                    "impact": "positive",
                }
            ],
            "unknowns": [],
            "conflicts": [],
        }

    monkeypatch.setattr("src.chat_api.verify_service.verify_targets", fake_verify)

    resp = client.post("/api/v1/chat/verify", json={"target_event_ids": [101]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["score"] == 78
    assert "evidence" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/chat_api/test_verify.py -v`
Expected: FAIL because endpoint/service is missing.

- [ ] **Step 3: Implement verify service and endpoint**

```python
# src/chat_api/verify_service.py
from sqlalchemy import select

from src.chat_api.scoring import compute_reliability
from src.db.database import SessionLocal
from src.db.models import Event
from src.verifier.verifier import verify_opportunity


def verify_targets(target_ids: list[int]) -> dict:
    db = SessionLocal()
    try:
        stmt = select(Event).where(Event.id.in_(target_ids)).limit(1)
        event = db.execute(stmt).scalar_one_or_none()
        if event is None:
            return {
                "score": 0,
                "level": "low",
                "verdict": "untrusted",
                "evidence": [],
                "unknowns": ["event not found"],
                "conflicts": [],
            }

        check = verify_opportunity(
            event_type=(event.event_type or "").upper(),
            source_url=event.source_url or "",
            application_url=event.application_url or "",
            source_name=event.source_platform or "",
        )

        layers = check.get("verification_log", {}).get("layers", {})
        l1 = layers.get("origin_anchor", {})
        l2 = layers.get("cross_reference", {})
        l3 = layers.get("security_api", {})

        evidence = []
        evidence.append({
            "category": "origin",
            "detail": l1.get("reason", "origin unknown"),
            "source": "verifier_layer",
            "weight": 25,
            "impact": "positive" if l1.get("passed") else "negative",
        })
        evidence.append({
            "category": "cross_reference",
            "detail": l2.get("reason", "cross reference unknown"),
            "source": "verifier_layer",
            "weight": 25,
            "impact": "positive" if l2.get("passed") else "negative",
        })
        evidence.append({
            "category": "security",
            "detail": l3.get("reason", "security unknown"),
            "source": "verifier_layer",
            "weight": 20,
            "impact": "positive" if l3.get("passed") else "negative",
        })

        reliability = compute_reliability(
            origin=25 if l1.get("passed") else 0,
            completeness=15 if event.title and event.amount and event.deadline else 5,
            consistency=20 if event.title and (event.source_url or event.application_url) else 5,
            cross_reference=25 if l2.get("passed") else 0,
            security_penalty=0 if l3.get("passed") else -20,
            history_bonus=10 if event.heat_count and event.heat_count >= 2 else 0,
            has_cross_reference=bool(l2.get("passed")),
            has_major_conflict=check.get("verdict") == "fraud",
            critical_security_failure=not bool(l3.get("passed")),
        )

        unknowns = []
        if not event.amount:
            unknowns.append("missing amount")
        if not event.deadline:
            unknowns.append("missing deadline")

        conflicts = []
        if check.get("verdict") == "fraud":
            conflicts.append("verifier flagged fraud verdict")

        return {
            **reliability,
            "evidence": evidence,
            "unknowns": unknowns,
            "conflicts": conflicts,
        }
    finally:
        db.close()
```

```python
# src/chat_api/schemas.py (append)
class VerifyRequest(BaseModel):
    target_event_ids: list[int]
```

```python
# src/chat_api/app.py (append)
from .schemas import VerifyRequest, VerifyResponse
from .verify_service import verify_targets


@app.post("/api/v1/chat/verify", response_model=VerifyResponse)
def verify(payload: VerifyRequest) -> VerifyResponse:
    result = verify_targets(payload.target_event_ids)
    return VerifyResponse(**result)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/chat_api/test_verify.py tests/chat_api/test_scoring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/chat_api tests/chat_api/test_verify.py
git commit -m "feat(chat-api): add verify endpoint reusing existing verifier"
```

### Task 5: Add Proposal Endpoint Grounded In Verified Facts

**Files:**

- Create: `src/chat_api/proposal_service.py`
- Modify: `src/chat_api/app.py`
- Modify: `src/chat_api/schemas.py`
- Create: `tests/chat_api/test_propose_options.py`

- [ ] **Step 1: Write failing test for grounded proposal response**

```python
# tests/chat_api/test_propose_options.py
from fastapi.testclient import TestClient

from src.chat_api.app import app


def test_propose_options_returns_three_tiers(monkeypatch):
    client = TestClient(app)

    def fake_propose(verified_facts):
        return {
            "options": [
                {"tier": "light", "summary": "quick prototype", "assumptions": []},
                {"tier": "standard", "summary": "balanced scope", "assumptions": []},
                {"tier": "advanced", "summary": "full system", "assumptions": []},
            ]
        }

    monkeypatch.setattr("src.chat_api.proposal_service.propose_options", fake_propose)

    resp = client.post(
        "/api/v1/chat/propose-options",
        json={
            "verified_facts": {
                "title": "X Hackathon",
                "amount": "$20,000",
                "deadline": "2026-08-01",
            }
        },
    )
    assert resp.status_code == 200
    assert len(resp.json()["options"]) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/chat_api/test_propose_options.py -v`
Expected: FAIL because endpoint/service is missing.

- [ ] **Step 3: Implement proposal service and endpoint**

```python
# src/chat_api/proposal_service.py

def propose_options(verified_facts: dict) -> dict:
    title = verified_facts.get("title", "Opportunity")
    amount = verified_facts.get("amount", "unknown reward")
    deadline = verified_facts.get("deadline", "unknown deadline")

    return {
        "options": [
            {
                "tier": "light",
                "summary": f"Build a lean MVP for {title} with core demo only.",
                "assumptions": [
                    f"Prize budget context: {amount}",
                    f"Submission date context: {deadline}",
                ],
            },
            {
                "tier": "standard",
                "summary": f"Ship a production-like prototype for {title} with observable metrics.",
                "assumptions": [
                    f"Prize budget context: {amount}",
                    f"Submission date context: {deadline}",
                ],
            },
            {
                "tier": "advanced",
                "summary": f"Implement end-to-end architecture for {title} with resilience and scale tests.",
                "assumptions": [
                    f"Prize budget context: {amount}",
                    f"Submission date context: {deadline}",
                ],
            },
        ]
    }
```

```python
# src/chat_api/schemas.py (append)
class ProposeOptionsRequest(BaseModel):
    verified_facts: dict


class ProposedOption(BaseModel):
    tier: str
    summary: str
    assumptions: list[str]


class ProposeOptionsResponse(BaseModel):
    options: list[ProposedOption]
```

```python
# src/chat_api/app.py (append)
from .proposal_service import propose_options
from .schemas import ProposeOptionsRequest, ProposeOptionsResponse


@app.post("/api/v1/chat/propose-options", response_model=ProposeOptionsResponse)
def propose_options_endpoint(payload: ProposeOptionsRequest) -> ProposeOptionsResponse:
    result = propose_options(payload.verified_facts)
    return ProposeOptionsResponse(**result)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/chat_api/test_propose_options.py tests/chat_api/test_verify.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/chat_api tests/chat_api/test_propose_options.py
git commit -m "feat(chat-api): add grounded implementation options endpoint"
```

### Task 6: Create Next.js + CopilotKit Frontend Skeleton

**Files:**

- Create: `apps/chat-web/package.json`
- Create: `apps/chat-web/next.config.ts`
- Create: `apps/chat-web/tsconfig.json`
- Create: `apps/chat-web/app/layout.tsx`
- Create: `apps/chat-web/app/page.tsx`
- Create: `apps/chat-web/app/api/chat/select-targets/route.ts`
- Create: `apps/chat-web/app/api/chat/verify/route.ts`
- Create: `apps/chat-web/app/api/chat/propose-options/route.ts`
- Create: `apps/chat-web/components/agent-chat.tsx`
- Create: `apps/chat-web/lib/chat-api.ts`
- Create: `apps/chat-web/.env.example`

- [ ] **Step 1: Write failing frontend smoke test**

```tsx
// apps/chat-web/components/agent-chat.test.tsx
import { render, screen } from "@testing-library/react";
import AgentChat from "./agent-chat";

it("renders agent chat heading", () => {
  render(<AgentChat />);
  expect(screen.getByText("Database-Driven Agent Chat")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/chat-web && npm test`
Expected: FAIL because project/files are missing.

- [ ] **Step 3: Scaffold Next.js app and API bridge**

```json
// apps/chat-web/package.json
{
  "name": "chat-web",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run"
  },
  "dependencies": {
    "next": "15.0.0",
    "react": "19.0.0",
    "react-dom": "19.0.0",
    "@copilotkit/react-core": "^0.34.0",
    "@copilotkit/react-ui": "^0.34.0"
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "vitest": "^2.0.0",
    "@testing-library/react": "^16.0.0",
    "@types/react": "^19.0.0",
    "@types/node": "^22.0.0"
  }
}
```

```tsx
// apps/chat-web/components/agent-chat.tsx
"use client";

export default function AgentChat() {
  return (
    <main
      style={{ maxWidth: 900, margin: "40px auto", fontFamily: "system-ui" }}
    >
      <h1>Database-Driven Agent Chat</h1>
      <p>
        Read-only verification and implementation planning based on database
        records.
      </p>
    </main>
  );
}
```

```tsx
// apps/chat-web/app/page.tsx
import AgentChat from "../components/agent-chat";

export default function Page() {
  return <AgentChat />;
}
```

```ts
// apps/chat-web/lib/chat-api.ts
export async function postJson(path: string, body: unknown) {
  const resp = await fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    throw new Error(`Request failed: ${resp.status}`);
  }

  return resp.json();
}
```

```ts
// apps/chat-web/app/api/chat/verify/route.ts
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const payload = await req.json();
  const base = process.env.CHAT_API_BASE_URL;
  const resp = await fetch(`${base}/api/v1/chat/verify`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-internal-key": process.env.CHAT_API_INTERNAL_KEY || "",
    },
    body: JSON.stringify(payload),
  });

  const json = await resp.json();
  return NextResponse.json(json, { status: resp.status });
}
```

```ts
// apps/chat-web/app/api/chat/select-targets/route.ts
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const payload = await req.json();
  const base = process.env.CHAT_API_BASE_URL;
  const resp = await fetch(`${base}/api/v1/chat/select-targets`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-internal-key": process.env.CHAT_API_INTERNAL_KEY || "",
    },
    body: JSON.stringify(payload),
  });

  const json = await resp.json();
  return NextResponse.json(json, { status: resp.status });
}
```

```ts
// apps/chat-web/app/api/chat/propose-options/route.ts
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const payload = await req.json();
  const base = process.env.CHAT_API_BASE_URL;
  const resp = await fetch(`${base}/api/v1/chat/propose-options`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-internal-key": process.env.CHAT_API_INTERNAL_KEY || "",
    },
    body: JSON.stringify(payload),
  });

  const json = await resp.json();
  return NextResponse.json(json, { status: resp.status });
}
```

- [ ] **Step 4: Run checks to verify pass**

Run: `cd apps/chat-web && npm install && npm run build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add apps/chat-web
git commit -m "feat(chat-web): scaffold nextjs frontend with chat api bridges"
```

### Task 7: Integrate CopilotKit Actions For Mixed-Mode Flow

**Files:**

- Modify: `apps/chat-web/components/agent-chat.tsx`
- Create: `apps/chat-web/lib/actions.ts`
- Create: `apps/chat-web/types/chat.ts`
- Create: `apps/chat-web/components/result-panels.tsx`

- [ ] **Step 1: Write failing action-layer test**

```ts
// apps/chat-web/lib/actions.test.ts
import { runMixedModeVerification } from "./actions";

it("executes select -> verify -> propose chain", async () => {
  const api = {
    selectTargets: async () => ({ target_event_ids: [11] }),
    verify: async () => ({
      score: 82,
      level: "high",
      verdict: "trusted",
      evidence: [],
      unknowns: [],
      conflicts: [],
    }),
    proposeOptions: async () => ({
      options: [{ tier: "light", summary: "x", assumptions: [] }],
    }),
  };

  const result = await runMixedModeVerification(api as any, { event_id: 11 });
  expect(result.verification.score).toBe(82);
  expect(result.options.options.length).toBe(1);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/chat-web && npm test`
Expected: FAIL because orchestration utility is missing.

- [ ] **Step 3: Implement action chaining and UI rendering**

```ts
// apps/chat-web/lib/actions.ts
export async function runMixedModeVerification(
  api: {
    selectTargets: (input: any) => Promise<any>;
    verify: (input: any) => Promise<any>;
    proposeOptions: (input: any) => Promise<any>;
  },
  input: any
) {
  const selected = await api.selectTargets({ mode: "mixed", ...input });
  const verification = await api.verify({
    target_event_ids: selected.target_event_ids || [],
  });
  const options = await api.proposeOptions({
    verified_facts: {
      score: verification.score,
      verdict: verification.verdict,
    },
  });

  return { selected, verification, options };
}
```

```tsx
// apps/chat-web/components/result-panels.tsx
export default function ResultPanels({ data }: { data: any }) {
  if (!data) return null;

  return (
    <section>
      <h2>Reliability</h2>
      <p>Score: {data.verification?.score}</p>
      <p>Verdict: {data.verification?.verdict}</p>
      <h2>Options</h2>
      <ul>
        {(data.options?.options || []).map((opt: any) => (
          <li key={opt.tier}>
            {opt.tier}: {opt.summary}
          </li>
        ))}
      </ul>
    </section>
  );
}
```

```tsx
// apps/chat-web/components/agent-chat.tsx (replace)
"use client";

import { useState } from "react";
import ResultPanels from "./result-panels";
import { runMixedModeVerification } from "../lib/actions";

export default function AgentChat() {
  const [eventId, setEventId] = useState("101");
  const [result, setResult] = useState<any>(null);

  const api = {
    selectTargets: async (body: any) => {
      const r = await fetch("/api/chat/select-targets", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      return r.json();
    },
    verify: async (body: any) => {
      const r = await fetch("/api/chat/verify", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      return r.json();
    },
    proposeOptions: async (body: any) => {
      const r = await fetch("/api/chat/propose-options", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      return r.json();
    },
  };

  return (
    <main
      style={{ maxWidth: 900, margin: "40px auto", fontFamily: "system-ui" }}
    >
      <h1>Database-Driven Agent Chat</h1>
      <label htmlFor="eventId">Event ID</label>
      <input
        id="eventId"
        value={eventId}
        onChange={(e) => setEventId(e.target.value)}
      />
      <button
        onClick={async () => {
          const data = await runMixedModeVerification(api, {
            event_id: Number(eventId),
          });
          setResult(data);
        }}
      >
        Verify From Database
      </button>
      <ResultPanels data={result} />
    </main>
  );
}
```

- [ ] **Step 4: Run tests and build**

Run: `cd apps/chat-web && npm test && npm run build`
Expected: PASS and build succeeds.

- [ ] **Step 5: Commit**

```bash
git add apps/chat-web/components apps/chat-web/lib apps/chat-web/types
git commit -m "feat(chat-web): integrate mixed-mode verify workflow actions"
```

### Task 8: Security Hardening, Read-Only Guard, And Deployment Docs

**Files:**

- Modify: `src/chat_api/auth.py`
- Modify: `src/chat_api/app.py`
- Create: `tests/chat_api/test_auth.py`
- Modify: `README.md`
- Create: `apps/chat-web/vercel.json`

- [ ] **Step 1: Write failing auth guard tests**

```python
# tests/chat_api/test_auth.py
from fastapi.testclient import TestClient

from src.chat_api.app import app


def test_verify_requires_internal_key():
    client = TestClient(app)
    resp = client.post("/api/v1/chat/verify", json={"target_event_ids": [1]})
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify fail**

Run: `pytest tests/chat_api/test_auth.py -v`
Expected: FAIL because key guard is not enforced.

- [ ] **Step 3: Implement auth and document deployment**

```python
# src/chat_api/auth.py (replace)
import os
from fastapi import Header, HTTPException


async def verify_internal_key(x_internal_key: str = Header(default="")) -> None:
    expected = os.getenv("CHAT_API_INTERNAL_KEY", "")
    if not expected:
        return
    if x_internal_key != expected:
        raise HTTPException(status_code=401, detail="invalid internal key")
```

```python
# src/chat_api/app.py (modify verify and propose endpoints)
from fastapi import Depends
from .auth import verify_internal_key


@app.post("/api/v1/chat/verify", response_model=VerifyResponse, dependencies=[Depends(verify_internal_key)])
def verify(payload: VerifyRequest) -> VerifyResponse:
    result = verify_targets(payload.target_event_ids)
    return VerifyResponse(**result)


@app.post("/api/v1/chat/propose-options", response_model=ProposeOptionsResponse, dependencies=[Depends(verify_internal_key)])
def propose_options_endpoint(payload: ProposeOptionsRequest) -> ProposeOptionsResponse:
    result = propose_options(payload.verified_facts)
    return ProposeOptionsResponse(**result)
```

```json
// apps/chat-web/vercel.json
{
  "framework": "nextjs",
  "functions": {
    "app/api/chat/**/*.ts": {
      "maxDuration": 30
    }
  }
}
```

```md
# README.md (append section)

## Agent Chat V1 (Read-Only)

Backend API:

- Run: `uvicorn src.chat_api.app:app --host 0.0.0.0 --port 9000`
- Health: `GET /api/v1/chat/health`
- Select targets: `POST /api/v1/chat/select-targets`
- Verify: `POST /api/v1/chat/verify`
- Propose options: `POST /api/v1/chat/propose-options`

Frontend:

- `cd apps/chat-web && npm install && npm run dev`
- Required env:
  - `CHAT_API_BASE_URL`
  - `CHAT_API_INTERNAL_KEY`

Security:

- Use read-only DB credentials in chat API runtime.
- Keep ingestion pipeline credentials separate.
```

- [ ] **Step 4: Run full test suite subset**

Run: `pytest tests/chat_api -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/chat_api tests/chat_api README.md apps/chat-web/vercel.json
git commit -m "chore(chat-v1): enforce internal auth and add deployment documentation"
```

### Task 9: End-To-End Validation And Release Checklist

**Files:**

- Create: `docs/superpowers/runbooks/agent-chat-v1-validation.md`

- [ ] **Step 1: Write the validation checklist file**

```md
# Agent Chat V1 Validation Checklist

## Local Backend

- [ ] Health endpoint returns ok
- [ ] Select-targets works for event_id mode
- [ ] Select-targets works for source+window mode
- [ ] Verify returns score/level/verdict/evidence/unknowns/conflicts
- [ ] Propose-options returns 3 tiers

## Local Frontend

- [ ] Can trigger mixed-mode flow from UI
- [ ] Reliability panel renders score and verdict
- [ ] Options panel renders at least one option

## Security

- [ ] Verify endpoint rejects invalid internal key
- [ ] Runtime uses read-only DB credential

## Deployment

- [ ] Backend deployed to long-running service
- [ ] Frontend deployed to Vercel
- [ ] Vercel env vars configured correctly
```

- [ ] **Step 2: Execute validation commands**

Run: `pytest tests/chat_api -v`
Expected: PASS

Run: `cd apps/chat-web && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/runbooks/agent-chat-v1-validation.md
git commit -m "docs(chat-v1): add end-to-end validation checklist"
```

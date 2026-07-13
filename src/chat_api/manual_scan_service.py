from __future__ import annotations

from datetime import datetime, timezone
import threading
import uuid
from typing import Callable, Any

_RUN_SCHEDULES = ("grant_hackathon", "social_watch")
_lock = threading.Lock()
_state: dict[str, Any] = {
    "job_id": None,
    "status": "idle",
    "triggered": False,
    "started_at": "",
    "finished_at": "",
    "current_stage": "",
    "schedules": [],
    "error": "",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot() -> dict[str, Any]:
    return {
        "job_id": _state["job_id"],
        "status": _state["status"],
        "triggered": _state.get("triggered", False),
        "started_at": _state["started_at"],
        "finished_at": _state["finished_at"],
        "current_stage": _state["current_stage"],
        "schedules": [dict(item) for item in _state["schedules"]],
        "error": _state["error"],
    }


def get_manual_scan_status() -> dict[str, Any]:
    with _lock:
        return _snapshot()


def _run_manual_scan(job_id: str, pipeline_runner: Callable[[str], dict | None]) -> None:
    schedule_results: list[dict[str, Any]] = []

    try:
        for schedule in _RUN_SCHEDULES:
            with _lock:
                if _state["job_id"] != job_id:
                    return
                _state["current_stage"] = schedule

            result = pipeline_runner(schedule) or {}
            schedule_results.append(
                {
                    "schedule": schedule,
                    "status": result.get("status", "success"),
                    "fetched": result.get("fetched", 0),
                    "new": result.get("new", 0),
                    "deduped": result.get("deduped", 0),
                    "classified": result.get("classified", 0),
                    "verified": result.get("verified", 0),
                    "fraud": result.get("fraud", 0),
                    "pushed": result.get("pushed", 0),
                    "error": result.get("error", ""),
                }
            )

            if result.get("status") == "failed":
                with _lock:
                    if _state["job_id"] == job_id:
                        _state["status"] = "failed"
                        _state["finished_at"] = _utc_now()
                        _state["current_stage"] = ""
                        _state["schedules"] = schedule_results
                        _state["error"] = result.get("error", "manual scan failed")
                return

        with _lock:
            if _state["job_id"] == job_id:
                _state["status"] = "success"
                _state["finished_at"] = _utc_now()
                _state["current_stage"] = ""
                _state["schedules"] = schedule_results
                _state["error"] = ""
    except Exception as exc:
        with _lock:
            if _state["job_id"] == job_id:
                _state["status"] = "failed"
                _state["finished_at"] = _utc_now()
                _state["current_stage"] = ""
                _state["schedules"] = schedule_results
                _state["error"] = str(exc)


def trigger_manual_scan(pipeline_runner: Callable[[str], dict | None]) -> dict[str, Any]:
    with _lock:
        if _state["status"] == "running":
            current = _snapshot()
            current["triggered"] = False
            return current

        job_id = str(uuid.uuid4())
        _state.update(
            {
                "job_id": job_id,
                "status": "running",
                "triggered": True,
                "started_at": _utc_now(),
                "finished_at": "",
                "current_stage": _RUN_SCHEDULES[0],
                "schedules": [],
                "error": "",
            }
        )
        current = _snapshot()

    thread = threading.Thread(
        target=_run_manual_scan,
        args=(job_id, pipeline_runner),
        daemon=True,
        name=f"manual-scan-{job_id[:8]}",
    )
    thread.start()
    return current

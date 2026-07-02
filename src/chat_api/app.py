from fastapi import Depends, FastAPI, Query

from .auth import verify_internal_key

from .schemas import (
    ManualScanStatusResponse,
    DashboardScheduleLogsResponse,
    DashboardSourceHealthResponse,
    DashboardOpportunitiesResponse,
    HealthResponse,
    ProposeOptionsRequest,
    ProposeOptionsResponse,
    SelectTargetsRequest,
    SelectTargetsResponse,
    VerifyRequest,
    VerifyResponse,
)

app = FastAPI(title="Web3 Agent Chat API", version="v1")


@app.get("/api/v1/chat/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get(
    "/api/v1/dashboard/opportunities",
    response_model=DashboardOpportunitiesResponse,
    dependencies=[Depends(verify_internal_key)],
)
def dashboard_opportunities(
    event_types: list[str] = Query(default=["grant", "hackathon", "bounty"]),
    ecosystem: str = "",
    min_score: float = 5.0,
    days: int = 14,
    source_trust: str = "all",
) -> DashboardOpportunitiesResponse:
    from . import dashboard_service

    result = dashboard_service.list_opportunities(
        {
            "event_types": event_types,
            "ecosystem": ecosystem,
            "min_score": min_score,
            "days": days,
            "source_trust": source_trust,
        }
    )
    return DashboardOpportunitiesResponse(**result)


@app.get(
    "/api/v1/dashboard/source-health",
    response_model=DashboardSourceHealthResponse,
    dependencies=[Depends(verify_internal_key)],
)
def dashboard_source_health() -> DashboardSourceHealthResponse:
    from . import dashboard_service

    result = dashboard_service.list_source_health()
    return DashboardSourceHealthResponse(**result)


@app.get(
    "/api/v1/dashboard/schedule-logs",
    response_model=DashboardScheduleLogsResponse,
    dependencies=[Depends(verify_internal_key)],
)
def dashboard_schedule_logs(limit: int = 50) -> DashboardScheduleLogsResponse:
    from . import dashboard_service

    result = dashboard_service.list_schedule_logs(limit=limit)
    return DashboardScheduleLogsResponse(**result)


@app.get(
    "/api/v1/dashboard/manual-scan",
    response_model=ManualScanStatusResponse,
    dependencies=[Depends(verify_internal_key)],
)
def manual_scan_status() -> ManualScanStatusResponse:
    from . import manual_scan_service

    result = manual_scan_service.get_manual_scan_status()
    return ManualScanStatusResponse(**result)


@app.post(
    "/api/v1/dashboard/manual-scan",
    response_model=ManualScanStatusResponse,
    dependencies=[Depends(verify_internal_key)],
)
def trigger_manual_scan() -> ManualScanStatusResponse:
    from . import manual_scan_service
    from src.main import run_pipeline

    result = manual_scan_service.trigger_manual_scan(run_pipeline)
    return ManualScanStatusResponse(**result)


@app.post("/api/v1/chat/select-targets", response_model=SelectTargetsResponse)
def select_targets(payload: SelectTargetsRequest) -> SelectTargetsResponse:
    from . import selection_service

    params = payload.model_dump(by_alias=True)
    ids = selection_service.select_target_event_ids(params)
    return SelectTargetsResponse(target_event_ids=ids, no_data=len(ids) == 0)


@app.post(
    "/api/v1/chat/verify",
    response_model=VerifyResponse,
    dependencies=[Depends(verify_internal_key)],
)
def verify(payload: VerifyRequest) -> VerifyResponse:
    from . import verify_service

    result = verify_service.verify_targets(payload.target_event_ids)
    return VerifyResponse(**result)


@app.post(
    "/api/v1/chat/propose-options",
    response_model=ProposeOptionsResponse,
    dependencies=[Depends(verify_internal_key)],
)
def propose_options_endpoint(payload: ProposeOptionsRequest) -> ProposeOptionsResponse:
    from . import proposal_service

    result = proposal_service.propose_options(payload.verified_facts)
    return ProposeOptionsResponse(**result)

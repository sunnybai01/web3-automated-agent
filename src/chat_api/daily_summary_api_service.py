def trigger_daily_summary() -> dict:
    from src.main import run_daily_summary

    result = run_daily_summary() or {}
    return {
        "status": result.get("status", "failed"),
        "summary_date": result.get("summary_date", ""),
        "slack_ts": result.get("slack_ts", ""),
        "error": result.get("error", ""),
    }
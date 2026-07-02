import type {
  ManualScanScheduleResult,
  ManualScanStatusResponse,
} from "../types/chat";

export function getManualScanProgressLabel(
  status: ManualScanStatusResponse | null
) {
  if (!status) {
    return "No manual scan yet";
  }

  if (status.status === "running") {
    return `Running ${status.current_stage || "scan"}`;
  }

  if (status.status === "success") {
    return "Last scan succeeded";
  }

  if (status.status === "failed") {
    return "Last scan failed";
  }

  return "No manual scan yet";
}

export function summarizeManualScan(status: ManualScanStatusResponse | null) {
  const schedules = status?.schedules ?? [];

  return schedules.reduce(
    (acc, item) => {
      acc.fetched += item.fetched;
      acc.new += item.new;
      acc.deduped += item.deduped;
      acc.classified += item.classified;
      acc.verified += item.verified;
      acc.fraud += item.fraud;
      acc.pushed += item.pushed;
      return acc;
    },
    {
      fetched: 0,
      new: 0,
      deduped: 0,
      classified: 0,
      verified: 0,
      fraud: 0,
      pushed: 0,
    }
  );
}

export function getScheduleStatusMap(
  status: ManualScanStatusResponse | null
): Array<{
  schedule: string;
  status: string;
  result: ManualScanScheduleResult | null;
}> {
  const completed = new Map(
    (status?.schedules ?? []).map((item) => [item.schedule, item])
  );
  const ordered = ["grant_hackathon", "bounty"];

  return ordered.map((schedule) => {
    const result = completed.get(schedule) ?? null;
    if (result) {
      return { schedule, status: result.status, result };
    }
    if (status?.status === "running" && status.current_stage === schedule) {
      return { schedule, status: "running", result: null };
    }
    if (status?.status === "running" && completed.size > 0) {
      return { schedule, status: "pending", result: null };
    }
    return { schedule, status: "idle", result: null };
  });
}

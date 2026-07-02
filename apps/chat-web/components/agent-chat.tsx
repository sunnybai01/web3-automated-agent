"use client";

import { useFrontendTool } from "@copilotkit/react-core/v2";
import { CopilotChat } from "@copilotkit/react-ui";
import {
  Activity,
  Database,
  ShieldCheck,
  Sparkles,
  Telescope,
} from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import { z } from "zod";

import { runMixedModeVerification } from "../lib/actions";
import { getJson, postJson } from "../lib/chat-api";
import {
  getManualScanProgressLabel,
  getScheduleStatusMap,
  summarizeManualScan,
} from "../lib/manual-scan";
import type {
  AnalysisTargetInput,
  DashboardOpportunitiesResponse,
  DashboardOpportunityItem,
  DashboardScheduleLogsResponse,
  DashboardSourceHealthResponse,
  ManualScanStatusResponse,
  MixedModeResult,
  ProposeOptionsRequest,
  ProposeOptionsResponse,
  SelectTargetsRequest,
  SelectTargetsResponse,
  VerifyResponse,
} from "../types/chat";
import ResultPanels from "./result-panels";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./ui/card";
import { Input } from "./ui/input";

type DashboardTab = "opportunities" | "sourceHealth" | "scheduleLogs";

type DashboardFilters = {
  eventTypes: string[];
  ecosystem: string;
  minScore: string;
  days: string;
  sourceTrust: "all" | "official" | "discovery";
};

const analysisToolSchema = z.object({
  eventId: z.number().optional(),
  sourceName: z.string().optional(),
  from: z.string().optional(),
  to: z.string().optional(),
  limit: z.number().optional(),
});

const dashboardContextToolSchema = z.object({
  includeRows: z.boolean().optional(),
  rowLimit: z.number().min(1).max(20).optional(),
});

export function shouldRequestTabData({
  hasData,
  isLoading,
  hasError,
}: {
  hasData: boolean;
  isLoading: boolean;
  hasError: boolean;
}) {
  return !isLoading && (!hasData || hasError);
}

const isoDatePattern = /^\d{4}-\d{2}-\d{2}(?:[T\s].*)?$/;

function normalizeDateValue(value?: string) {
  if (!value) {
    return undefined;
  }

  const trimmed = value.trim();
  if (!isoDatePattern.test(trimmed)) {
    return undefined;
  }

  return trimmed;
}

export function normalizeAnalysisTargetInput(
  input: {
    eventId?: number;
    sourceName?: string;
    from?: string;
    to?: string;
    limit?: number;
  },
  fallbackEventId?: number
): AnalysisTargetInput {
  const eventId = input.eventId ?? fallbackEventId;

  if (eventId !== undefined) {
    return { event_id: eventId };
  }

  const sourceName = input.sourceName?.trim();
  const from = normalizeDateValue(input.from);
  const to = normalizeDateValue(input.to);

  if (!sourceName || !from || !to) {
    return {};
  }

  const normalized: AnalysisTargetInput = {
    source_name: sourceName,
    from,
    to,
  };

  if (typeof input.limit === "number") {
    normalized.limit = Math.min(100, Math.max(1, Math.trunc(input.limit)));
  }

  return normalized;
}

export default function AgentChat() {
  const [activeTab, setActiveTab] = useState<DashboardTab>("opportunities");
  const [filters, setFilters] = useState<DashboardFilters>({
    eventTypes: ["grant", "hackathon", "bounty"],
    ecosystem: "",
    minScore: "5.0",
    days: "14",
    sourceTrust: "all",
  });
  const [dashboardData, setDashboardData] =
    useState<DashboardOpportunitiesResponse | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [isDashboardLoading, setIsDashboardLoading] = useState(true);
  const [sourceHealthData, setSourceHealthData] =
    useState<DashboardSourceHealthResponse | null>(null);
  const [sourceHealthError, setSourceHealthError] = useState<string | null>(
    null
  );
  const [isSourceHealthLoading, setIsSourceHealthLoading] = useState(false);
  const [scheduleLogsData, setScheduleLogsData] =
    useState<DashboardScheduleLogsResponse | null>(null);
  const [scheduleLogsError, setScheduleLogsError] = useState<string | null>(
    null
  );
  const [isScheduleLogsLoading, setIsScheduleLogsLoading] = useState(false);
  const [selectedOpportunity, setSelectedOpportunity] =
    useState<DashboardOpportunityItem | null>(null);
  const [result, setResult] = useState<MixedModeResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [manualScanStatus, setManualScanStatus] =
    useState<ManualScanStatusResponse | null>(null);
  const [manualScanError, setManualScanError] = useState<string | null>(null);
  const [isManualScanStarting, setIsManualScanStarting] = useState(false);

  const api = {
    selectTargets: async (
      body: SelectTargetsRequest
    ): Promise<SelectTargetsResponse> =>
      postJson("/api/chat/select-targets", body),
    verify: async (body: {
      target_event_ids: number[];
    }): Promise<VerifyResponse> => postJson("/api/chat/verify", body),
    proposeOptions: async (
      body: ProposeOptionsRequest
    ): Promise<ProposeOptionsResponse> =>
      postJson("/api/chat/propose-options", body),
  };

  const currentTarget = useMemo<AnalysisTargetInput>(
    () => ({
      event_id: selectedOpportunity?.id,
    }),
    [selectedOpportunity]
  );

  const manualScanProgressLabel = useMemo(
    () => getManualScanProgressLabel(manualScanStatus),
    [manualScanStatus]
  );

  const manualScanSummary = useMemo(
    () => summarizeManualScan(manualScanStatus),
    [manualScanStatus]
  );

  const manualScanSchedules = useMemo(
    () => getScheduleStatusMap(manualScanStatus),
    [manualScanStatus]
  );

  const dashboardContext = useMemo(() => {
    const activeCounts = {
      opportunities: dashboardData?.items.length ?? 0,
      sourceHealth: sourceHealthData?.items.length ?? 0,
      scheduleLogs: scheduleLogsData?.items.length ?? 0,
    };

    return {
      activeTab,
      loading: {
        opportunities: isDashboardLoading,
        sourceHealth: isSourceHealthLoading,
        scheduleLogs: isScheduleLogsLoading,
      },
      errors: {
        opportunities: dashboardError,
        sourceHealth: sourceHealthError,
        scheduleLogs: scheduleLogsError,
      },
      filters: {
        event_types: filters.eventTypes,
        ecosystem: filters.ecosystem,
        min_score: Number(filters.minScore || "5.0"),
        days: Number(filters.days || "14"),
        source_trust: filters.sourceTrust,
      },
      counts: activeCounts,
      selectedOpportunity: selectedOpportunity
        ? {
            id: selectedOpportunity.id,
            title: selectedOpportunity.title,
            score: selectedOpportunity.score,
            type: selectedOpportunity.type,
            ecosystem: selectedOpportunity.ecosystem,
            amount: selectedOpportunity.amount,
            deadline: selectedOpportunity.deadline,
            source_trust: selectedOpportunity.source_trust,
            verification_verdict: selectedOpportunity.verification_verdict,
            apply_url: selectedOpportunity.apply_url,
          }
        : null,
      opportunitiesMetrics: dashboardData?.metrics ?? null,
      sourceHealthSummary: sourceHealthData?.summary ?? null,
      scheduleLogSummary: scheduleLogsData?.summary ?? null,
      manualScanStatus,
    };
  }, [
    activeTab,
    dashboardData,
    dashboardError,
    filters.days,
    filters.ecosystem,
    filters.eventTypes,
    filters.minScore,
    filters.sourceTrust,
    isDashboardLoading,
    isScheduleLogsLoading,
    isSourceHealthLoading,
    scheduleLogsData,
    scheduleLogsError,
    selectedOpportunity,
    sourceHealthData,
    sourceHealthError,
    manualScanStatus,
  ]);

  async function loadOpportunitiesData() {
    const query = new URLSearchParams();
    for (const eventType of filters.eventTypes) {
      query.append("event_types", eventType);
    }
    query.set("ecosystem", filters.ecosystem);
    query.set("min_score", filters.minScore || "5.0");
    query.set("days", filters.days || "14");
    query.set("source_trust", filters.sourceTrust);

    setIsDashboardLoading(true);
    setDashboardError(null);

    try {
      const data = (await getJson(
        `/api/dashboard/opportunities?${query.toString()}`
      )) as DashboardOpportunitiesResponse;

      setDashboardData(data);
      setSelectedOpportunity((previous) => {
        if (!data.items.length) {
          return null;
        }

        if (previous) {
          const match = data.items.find((item) => item.id === previous.id);
          if (match) {
            return match;
          }
        }

        return data.items[0] ?? null;
      });
    } catch (error) {
      setDashboardError(
        error instanceof Error
          ? error.message
          : "Failed to load dashboard data."
      );
    } finally {
      setIsDashboardLoading(false);
    }
  }

  async function loadSourceHealthData() {
    setIsSourceHealthLoading(true);
    setSourceHealthError(null);

    try {
      const data = (await getJson(
        "/api/dashboard/source-health"
      )) as DashboardSourceHealthResponse;
      setSourceHealthData(data);
    } catch (error) {
      setSourceHealthError(
        error instanceof Error
          ? error.message
          : "Failed to load source health data."
      );
    } finally {
      setIsSourceHealthLoading(false);
    }
  }

  async function loadScheduleLogsData() {
    setIsScheduleLogsLoading(true);
    setScheduleLogsError(null);

    try {
      const data = (await getJson(
        "/api/dashboard/schedule-logs?limit=50"
      )) as DashboardScheduleLogsResponse;
      setScheduleLogsData(data);
    } catch (error) {
      setScheduleLogsError(
        error instanceof Error ? error.message : "Failed to load schedule logs."
      );
    } finally {
      setIsScheduleLogsLoading(false);
    }
  }

  async function loadManualScanStatus(refreshOnCompletion = false) {
    try {
      const data = (await getJson(
        "/api/dashboard/manual-scan"
      )) as ManualScanStatusResponse;
      setManualScanStatus(data);
      setManualScanError(null);

      if (refreshOnCompletion && data.status !== "running" && data.job_id) {
        await Promise.all([
          loadOpportunitiesData(),
          loadSourceHealthData(),
          loadScheduleLogsData(),
        ]);
      }
    } catch (error) {
      setManualScanError(
        error instanceof Error
          ? error.message
          : "Failed to load manual scan status."
      );
    }
  }

  async function triggerManualScan() {
    setIsManualScanStarting(true);
    setManualScanError(null);

    try {
      const data = (await postJson(
        "/api/dashboard/manual-scan",
        {}
      )) as ManualScanStatusResponse;
      setManualScanStatus(data);
      await loadScheduleLogsData();
    } catch (error) {
      setManualScanError(
        error instanceof Error ? error.message : "Failed to start manual scan."
      );
    } finally {
      setIsManualScanStarting(false);
    }
  }

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      await loadOpportunitiesData();
    })();

    return () => {
      cancelled = true;
    };
  }, [filters]);

  useEffect(() => {
    if (
      activeTab !== "sourceHealth" ||
      !shouldRequestTabData({
        hasData: Boolean(sourceHealthData),
        isLoading: isSourceHealthLoading,
        hasError: Boolean(sourceHealthError),
      })
    ) {
      return;
    }

    let cancelled = false;

    void (async () => {
      await loadSourceHealthData();
    })();

    return () => {
      cancelled = true;
    };
  }, [activeTab, sourceHealthData, isSourceHealthLoading, sourceHealthError]);

  useEffect(() => {
    if (
      activeTab !== "scheduleLogs" ||
      !shouldRequestTabData({
        hasData: Boolean(scheduleLogsData),
        isLoading: isScheduleLogsLoading,
        hasError: Boolean(scheduleLogsError),
      })
    ) {
      return;
    }

    let cancelled = false;

    void (async () => {
      await loadScheduleLogsData();
    })();

    return () => {
      cancelled = true;
    };
  }, [activeTab, scheduleLogsData, isScheduleLogsLoading, scheduleLogsError]);

  useEffect(() => {
    void loadManualScanStatus();
  }, []);

  useEffect(() => {
    if (manualScanStatus?.status !== "running") {
      return;
    }

    const intervalId = window.setInterval(() => {
      void loadManualScanStatus(true);
    }, 4000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [manualScanStatus?.job_id, manualScanStatus?.status]);

  const analyzeTarget = async (override?: Partial<AnalysisTargetInput>) => {
    const merged: AnalysisTargetInput = {
      ...currentTarget,
      ...override,
    };

    setIsRunning(true);
    try {
      const data = await runMixedModeVerification(api, merged);
      setResult(data);
      return data;
    } finally {
      setIsRunning(false);
    }
  };

  const handleTabChange = (nextTab: DashboardTab) => {
    setActiveTab(nextTab);

    if (
      nextTab === "sourceHealth" &&
      shouldRequestTabData({
        hasData: Boolean(sourceHealthData),
        isLoading: isSourceHealthLoading,
        hasError: Boolean(sourceHealthError),
      })
    ) {
      void loadSourceHealthData();
    }

    if (
      nextTab === "scheduleLogs" &&
      shouldRequestTabData({
        hasData: Boolean(scheduleLogsData),
        isLoading: isScheduleLogsLoading,
        hasError: Boolean(scheduleLogsError),
      })
    ) {
      void loadScheduleLogsData();
    }
  };

  useFrontendTool(
    {
      name: "analyzeDatabaseTargets",
      description:
        "Load opportunity records from the database, verify their reliability, and prepare grounded implementation options.",
      parameters: analysisToolSchema,
      handler: async (input) => {
        const data = await analyzeTarget(
          normalizeAnalysisTargetInput(input, selectedOpportunity?.id)
        );

        return {
          target: input,
          selectedEventIds: data.selected.target_event_ids,
          verification: data.verification,
          options: data.options.options,
        };
      },
    },
    [currentTarget, selectedOpportunity]
  );

  useFrontendTool(
    {
      name: "getDashboardContext",
      description:
        "Read the current dashboard context, including active tab, filters, selected row, and visible data summaries.",
      parameters: dashboardContextToolSchema,
      handler: async (input) => {
        const includeRows = input.includeRows ?? false;
        const rowLimit = input.rowLimit ?? 5;

        const response: Record<string, unknown> = {
          ...dashboardContext,
        };

        if (!includeRows) {
          return response;
        }

        if (activeTab === "opportunities") {
          response.visibleRows = (dashboardData?.items ?? [])
            .slice(0, rowLimit)
            .map((item) => ({
              id: item.id,
              score: item.score,
              type: item.type,
              title: item.title,
              ecosystem: item.ecosystem,
              amount: item.amount,
              deadline: item.deadline,
              verified: item.verified,
              heat: item.heat,
              source_trust: item.source_trust,
              verification_verdict: item.verification_verdict,
            }));
        } else if (activeTab === "sourceHealth") {
          response.visibleRows = (sourceHealthData?.items ?? [])
            .slice(0, rowLimit)
            .map((item) => ({
              source: item.source,
              status: item.status,
              failures: item.failures,
              last_success: item.last_success,
              last_fetch: item.last_fetch,
              last_error: item.last_error,
            }));
        } else {
          response.visibleRows = (scheduleLogsData?.items ?? [])
            .slice(0, rowLimit)
            .map((item) => ({
              id: item.id,
              job: item.job,
              status: item.status,
              started: item.started,
              fetched: item.fetched,
              new: item.new,
              deduped: item.deduped,
              verified: item.verified,
              error: item.error,
            }));
        }

        return response;
      },
    },
    [
      activeTab,
      dashboardContext,
      dashboardData,
      scheduleLogsData,
      sourceHealthData,
    ]
  );

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(249,115,22,0.18),_transparent_34%),linear-gradient(180deg,_hsl(var(--background))_0%,_#f8f5ef_100%)] px-4 py-8 md:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <Card className="overflow-hidden border-border/70 bg-card/95 shadow-[0_30px_90px_-48px_rgba(15,23,42,0.48)] backdrop-blur">
          <CardContent className="grid gap-4 p-6">
            <div className="space-y-4">
              <Badge className="bg-primary/12 text-primary hover:bg-primary/12">
                Signal Room
              </Badge>
              <div className="space-y-2">
                <h1 className="text-4xl font-semibold tracking-[-0.04em] md:text-5xl">
                  Opportunity Dashboard + Copilot
                </h1>
                <p className="max-w-2xl text-sm leading-6 text-muted-foreground md:text-base">
                  Browse the same core intelligence surface as Streamlit first,
                  then use the copilot to interrogate the currently visible data
                  or deep-dive into a selected opportunity.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <div className="space-y-6">
            <Card className="border-border/70 bg-card/95 shadow-sm">
              <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <CardTitle>Filters</CardTitle>
                    <CardDescription>
                      Mirror the Streamlit dashboard filters and keep the data
                      surface front and center.
                    </CardDescription>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <Button
                      disabled={
                        isManualScanStarting ||
                        manualScanStatus?.status === "running"
                      }
                      onClick={() => void triggerManualScan()}
                    >
                      {isManualScanStarting
                        ? "Starting Scan..."
                        : manualScanStatus?.status === "running"
                          ? "Scan Running..."
                          : "Run Scan"}
                    </Button>
                    <Badge variant="outline">{manualScanProgressLabel}</Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-5">
                {manualScanError ? (
                  <EmptyState
                    title="Manual scan status unavailable"
                    description={manualScanError}
                    icon={<Activity className="h-5 w-5 text-primary" />}
                  />
                ) : manualScanStatus?.job_id ? (
                  <div className="rounded-2xl border border-border/70 bg-background/70 p-4 text-sm text-muted-foreground">
                    <div className="flex flex-wrap items-center justify-between gap-3 text-foreground">
                      <span className="font-medium">Manual Scan Status</span>
                      <Badge variant="outline">{manualScanStatus.status}</Badge>
                    </div>
                    <p className="mt-2">
                      Job #{manualScanStatus.job_id.slice(0, 8)}
                      {manualScanStatus.started_at
                        ? ` started at ${new Date(manualScanStatus.started_at).toLocaleString()}`
                        : ""}
                    </p>
                    {manualScanStatus.current_stage ? (
                      <p className="mt-1">
                        Current stage: {manualScanStatus.current_stage}
                      </p>
                    ) : null}
                    {manualScanStatus.error ? (
                      <p className="mt-1 text-rose-700">
                        Error: {manualScanStatus.error}
                      </p>
                    ) : null}
                    <div className="mt-4 grid gap-3 sm:grid-cols-4">
                      <div className="rounded-2xl border border-border/60 bg-card px-3 py-2">
                        <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                          Fetched
                        </p>
                        <p className="mt-1 text-lg font-semibold text-foreground">
                          {manualScanSummary.fetched}
                        </p>
                      </div>
                      <div className="rounded-2xl border border-border/60 bg-card px-3 py-2">
                        <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                          New
                        </p>
                        <p className="mt-1 text-lg font-semibold text-foreground">
                          {manualScanSummary.new}
                        </p>
                      </div>
                      <div className="rounded-2xl border border-border/60 bg-card px-3 py-2">
                        <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                          Verified
                        </p>
                        <p className="mt-1 text-lg font-semibold text-foreground">
                          {manualScanSummary.verified}
                        </p>
                      </div>
                      <div className="rounded-2xl border border-border/60 bg-card px-3 py-2">
                        <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                          Pushed
                        </p>
                        <p className="mt-1 text-lg font-semibold text-foreground">
                          {manualScanSummary.pushed}
                        </p>
                      </div>
                    </div>
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      {manualScanSchedules.map((item) => (
                        <div
                          key={item.schedule}
                          className="rounded-2xl border border-border/60 bg-card px-3 py-3"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-medium text-foreground">
                              {item.schedule === "grant_hackathon"
                                ? "Grant + Hackathon"
                                : "Bounty"}
                            </p>
                            <Badge variant="outline">{item.status}</Badge>
                          </div>
                          {item.result ? (
                            <p className="mt-2 text-xs leading-5">
                              fetched {item.result.fetched} · new{" "}
                              {item.result.new} · verified{" "}
                              {item.result.verified} · pushed{" "}
                              {item.result.pushed}
                            </p>
                          ) : item.status === "running" ? (
                            <p className="mt-2 text-xs leading-5">
                              Currently processing this schedule.
                            </p>
                          ) : item.status === "pending" ? (
                            <p className="mt-2 text-xs leading-5">
                              Waiting for the previous schedule to finish.
                            </p>
                          ) : (
                            <p className="mt-2 text-xs leading-5">
                              No results yet for this schedule.
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
                <div className="space-y-3">
                  <span className="text-sm font-medium text-foreground">
                    Type
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: "Grant", value: "grant" },
                      { label: "Hackathon", value: "hackathon" },
                      { label: "Bounty", value: "bounty" },
                    ].map((option) => {
                      const enabled = filters.eventTypes.includes(option.value);
                      return (
                        <Button
                          key={option.value}
                          variant={enabled ? "default" : "outline"}
                          className="rounded-full"
                          onClick={() => {
                            setFilters((previous) => ({
                              ...previous,
                              eventTypes: enabled
                                ? previous.eventTypes.filter(
                                    (value) => value !== option.value
                                  )
                                : [...previous.eventTypes, option.value],
                            }));
                          }}
                        >
                          {option.label}
                        </Button>
                      );
                    })}
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                  <div className="space-y-2">
                    <label
                      className="text-sm font-medium text-foreground"
                      htmlFor="ecosystem"
                    >
                      Ecosystem
                    </label>
                    <Input
                      id="ecosystem"
                      value={filters.ecosystem}
                      onChange={(event) =>
                        setFilters((previous) => ({
                          ...previous,
                          ecosystem: event.target.value,
                        }))
                      }
                      placeholder="sui, ethereum"
                    />
                  </div>
                  <div className="space-y-2">
                    <label
                      className="text-sm font-medium text-foreground"
                      htmlFor="minScore"
                    >
                      Min Score
                    </label>
                    <Input
                      id="minScore"
                      type="number"
                      value={filters.minScore}
                      onChange={(event) =>
                        setFilters((previous) => ({
                          ...previous,
                          minScore: event.target.value,
                        }))
                      }
                      placeholder="5.0"
                    />
                  </div>
                  <div className="space-y-2">
                    <label
                      className="text-sm font-medium text-foreground"
                      htmlFor="days"
                    >
                      Last N Days
                    </label>
                    <Input
                      id="days"
                      type="number"
                      value={filters.days}
                      onChange={(event) =>
                        setFilters((previous) => ({
                          ...previous,
                          days: event.target.value,
                        }))
                      }
                      placeholder="14"
                    />
                  </div>
                </div>

                <div className="space-y-3">
                  <span className="text-sm font-medium text-foreground">
                    Source Trust
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: "All", value: "all" },
                      { label: "Official", value: "official" },
                      { label: "Discovery", value: "discovery" },
                    ].map((option) => {
                      const enabled = filters.sourceTrust === option.value;
                      return (
                        <Button
                          key={option.value}
                          variant={enabled ? "default" : "outline"}
                          className="rounded-full"
                          onClick={() =>
                            setFilters((previous) => ({
                              ...previous,
                              sourceTrust:
                                option.value as DashboardFilters["sourceTrust"],
                            }))
                          }
                        >
                          {option.label}
                        </Button>
                      );
                    })}
                  </div>
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-4 md:grid-cols-5">
              <MetricCard
                label="Total Shown"
                value={dashboardData?.metrics.total_shown ?? "-"}
              />
              <MetricCard
                label="Avg Score"
                value={dashboardData?.metrics.avg_score ?? "-"}
              />
              <MetricCard
                label="Verified %"
                value={
                  dashboardData
                    ? `${dashboardData.metrics.verified_percent}%`
                    : "-"
                }
              />
              <MetricCard
                label="Grants / Bounties / Hacks"
                value={
                  dashboardData
                    ? `${dashboardData.metrics.grants}/${dashboardData.metrics.bounties}/${dashboardData.metrics.hackathons}`
                    : "-"
                }
              />
              <MetricCard
                label="Official / Discovery"
                value={
                  dashboardData
                    ? `${dashboardData.metrics.official}/${dashboardData.metrics.discovery}`
                    : "-"
                }
              />
            </div>

            <Card className="border-border/70 bg-card/95 shadow-sm">
              <CardHeader className="pb-3">
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant={
                      activeTab === "opportunities" ? "default" : "outline"
                    }
                    className="rounded-full"
                    onClick={() => handleTabChange("opportunities")}
                  >
                    Active Opportunities
                  </Button>
                  <Button
                    variant={
                      activeTab === "sourceHealth" ? "default" : "outline"
                    }
                    className="rounded-full"
                    onClick={() => handleTabChange("sourceHealth")}
                  >
                    Source Health
                  </Button>
                  <Button
                    variant={
                      activeTab === "scheduleLogs" ? "default" : "outline"
                    }
                    className="rounded-full"
                    onClick={() => handleTabChange("scheduleLogs")}
                  >
                    Schedule Logs
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {activeTab === "opportunities" ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <h2 className="text-lg font-semibold text-foreground">
                          Active Opportunities
                        </h2>
                        <p className="text-sm text-muted-foreground">
                          Current filtered opportunity set from the dashboard
                          API.
                        </p>
                      </div>
                      <Badge variant="outline">
                        {dashboardData?.items.length ?? 0} rows
                      </Badge>
                    </div>

                    {dashboardError ? (
                      <EmptyState
                        title="Dashboard load failed"
                        description={dashboardError}
                      />
                    ) : isDashboardLoading ? (
                      <EmptyState
                        title="Loading opportunities"
                        description="Fetching the current filtered opportunity set..."
                      />
                    ) : !dashboardData?.items.length ? (
                      <EmptyState
                        title="No opportunities match your filters"
                        description="Adjust the current filter set to broaden the result window."
                      />
                    ) : (
                      <>
                        <div className="overflow-x-auto rounded-3xl border border-border/70">
                          <table className="min-w-full divide-y divide-border text-sm">
                            <thead className="bg-muted/60 text-left text-xs uppercase tracking-[0.18em] text-muted-foreground">
                              <tr>
                                <th className="px-4 py-3">Score</th>
                                <th className="px-4 py-3">Type</th>
                                <th className="px-4 py-3">Title</th>
                                <th className="px-4 py-3">Ecosystem</th>
                                <th className="px-4 py-3">Amount</th>
                                <th className="px-4 py-3">Deadline</th>
                                <th className="px-4 py-3">Heat</th>
                                <th className="px-4 py-3">Trust</th>
                                <th className="px-4 py-3">Verified</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-border bg-background/40">
                              {dashboardData.items.map((item) => {
                                const isSelected =
                                  item.id === selectedOpportunity?.id;
                                return (
                                  <tr
                                    key={item.id}
                                    className={
                                      isSelected
                                        ? "bg-primary/8"
                                        : "hover:bg-accent/50"
                                    }
                                  >
                                    <td className="px-4 py-3 font-medium text-foreground">
                                      {item.score ?? "-"}
                                    </td>
                                    <td className="px-4 py-3 text-muted-foreground">
                                      {item.type}
                                    </td>
                                    <td className="px-4 py-3">
                                      <button
                                        type="button"
                                        className="text-left font-medium text-foreground"
                                        onClick={() =>
                                          setSelectedOpportunity(item)
                                        }
                                      >
                                        {item.title}
                                      </button>
                                    </td>
                                    <td className="px-4 py-3 text-muted-foreground">
                                      {item.ecosystem}
                                    </td>
                                    <td className="px-4 py-3 text-muted-foreground">
                                      {item.amount}
                                    </td>
                                    <td className="px-4 py-3 text-muted-foreground">
                                      {item.deadline}
                                    </td>
                                    <td className="px-4 py-3 text-muted-foreground">
                                      {item.heat}
                                    </td>
                                    <td className="px-4 py-3 text-muted-foreground">
                                      {item.source_trust === "official"
                                        ? "Official"
                                        : "Discovery"}
                                    </td>
                                    <td className="px-4 py-3 text-muted-foreground">
                                      {item.verified ? "✅" : "⚠️"}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>

                        {selectedOpportunity ? (
                          <Card className="border-border/70 bg-background/70">
                            <CardHeader>
                              <CardTitle className="flex items-center justify-between gap-3 text-base">
                                <span>{selectedOpportunity.title}</span>
                                <Badge variant="outline">
                                  #{selectedOpportunity.id}
                                </Badge>
                              </CardTitle>
                              <CardDescription>
                                Selected opportunity context for the right-side
                                copilot.
                              </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                              <div className="grid gap-3 md:grid-cols-2">
                                <DetailField
                                  label="Type"
                                  value={selectedOpportunity.type}
                                />
                                <DetailField
                                  label="Ecosystem"
                                  value={selectedOpportunity.ecosystem ?? "-"}
                                />
                                <DetailField
                                  label="Amount"
                                  value={selectedOpportunity.amount ?? "-"}
                                />
                                <DetailField
                                  label="Deadline"
                                  value={selectedOpportunity.deadline}
                                />
                                <DetailField
                                  label="Source Trust"
                                  value={
                                    selectedOpportunity.source_trust ===
                                    "official"
                                      ? "Official"
                                      : "Discovery"
                                  }
                                />
                                <DetailField
                                  label="Verification"
                                  value={
                                    selectedOpportunity.verification_verdict
                                  }
                                />
                              </div>
                              <div className="flex flex-wrap gap-3">
                                <Button
                                  disabled={isRunning}
                                  onClick={() =>
                                    void analyzeTarget({
                                      event_id: selectedOpportunity.id,
                                    })
                                  }
                                >
                                  {isRunning
                                    ? "Analyzing..."
                                    : "Analyze Selected Opportunity"}
                                </Button>
                                {selectedOpportunity.apply_url ? (
                                  <a
                                    className="inline-flex items-center justify-center rounded-full border border-border px-4 py-2 text-sm font-medium hover:bg-accent"
                                    href={selectedOpportunity.apply_url}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    Open Apply Link
                                  </a>
                                ) : null}
                              </div>
                            </CardContent>
                          </Card>
                        ) : null}
                      </>
                    )}
                  </div>
                ) : activeTab === "sourceHealth" ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <h2 className="text-lg font-semibold text-foreground">
                          Source Health
                        </h2>
                        <p className="text-sm text-muted-foreground">
                          Health signals for each fetch source in the pipeline.
                        </p>
                      </div>
                      <Badge variant="outline">
                        {sourceHealthData?.summary.total_sources ?? 0} sources
                      </Badge>
                    </div>

                    {sourceHealthError ? (
                      <EmptyState
                        title="Source health load failed"
                        description={sourceHealthError}
                        icon={<ShieldCheck className="h-5 w-5 text-primary" />}
                        actionLabel="Retry"
                        onAction={() => void loadSourceHealthData()}
                      />
                    ) : isSourceHealthLoading ? (
                      <EmptyState
                        title="Loading source health"
                        description="Fetching latest source health records..."
                        icon={<ShieldCheck className="h-5 w-5 text-primary" />}
                      />
                    ) : !sourceHealthData?.items.length ? (
                      <EmptyState
                        title="No source health data yet"
                        description="The source health table is empty right now."
                        icon={<ShieldCheck className="h-5 w-5 text-primary" />}
                      />
                    ) : (
                      <>
                        <div className="grid gap-4 md:grid-cols-4">
                          <MetricCard
                            label="Total Sources"
                            value={sourceHealthData.summary.total_sources}
                          />
                          <MetricCard
                            label="Healthy"
                            value={sourceHealthData.summary.healthy}
                          />
                          <MetricCard
                            label="Degraded"
                            value={sourceHealthData.summary.degraded}
                          />
                          <MetricCard
                            label="Down"
                            value={sourceHealthData.summary.down}
                          />
                        </div>
                        <div className="overflow-x-auto rounded-3xl border border-border/70">
                          <table className="min-w-full divide-y divide-border text-sm">
                            <thead className="bg-muted/60 text-left text-xs uppercase tracking-[0.18em] text-muted-foreground">
                              <tr>
                                <th className="px-4 py-3">Source</th>
                                <th className="px-4 py-3">Status</th>
                                <th className="px-4 py-3">Last Success</th>
                                <th className="px-4 py-3">Last Fetch</th>
                                <th className="px-4 py-3">Failures</th>
                                <th className="px-4 py-3">Last Error</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-border bg-background/40">
                              {sourceHealthData.items.map((item) => (
                                <tr
                                  key={item.source}
                                  className="hover:bg-accent/50"
                                >
                                  <td className="px-4 py-3 font-medium text-foreground">
                                    {item.source}
                                  </td>
                                  <td className="px-4 py-3 text-muted-foreground">
                                    {item.status}
                                  </td>
                                  <td className="px-4 py-3 text-muted-foreground">
                                    {item.last_success}
                                  </td>
                                  <td className="px-4 py-3 text-muted-foreground">
                                    {item.last_fetch}
                                  </td>
                                  <td className="px-4 py-3 text-muted-foreground">
                                    {item.failures}
                                  </td>
                                  <td className="px-4 py-3 text-muted-foreground">
                                    {item.last_error || "-"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </>
                    )}
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <h2 className="text-lg font-semibold text-foreground">
                          Schedule Logs
                        </h2>
                        <p className="text-sm text-muted-foreground">
                          Recent scheduler runs and processing counters.
                        </p>
                      </div>
                      <Badge variant="outline">
                        {scheduleLogsData?.summary.total_runs ?? 0} runs
                      </Badge>
                    </div>

                    {scheduleLogsError ? (
                      <EmptyState
                        title="Schedule logs load failed"
                        description={scheduleLogsError}
                        icon={<Activity className="h-5 w-5 text-primary" />}
                        actionLabel="Retry"
                        onAction={() => void loadScheduleLogsData()}
                      />
                    ) : isScheduleLogsLoading ? (
                      <EmptyState
                        title="Loading schedule logs"
                        description="Fetching recent scheduler runs..."
                        icon={<Activity className="h-5 w-5 text-primary" />}
                      />
                    ) : !scheduleLogsData?.items.length ? (
                      <EmptyState
                        title="No schedule logs yet"
                        description="The schedule log table is empty right now."
                        icon={<Activity className="h-5 w-5 text-primary" />}
                      />
                    ) : (
                      <>
                        <div className="grid gap-4 md:grid-cols-4">
                          <MetricCard
                            label="Total Runs"
                            value={scheduleLogsData.summary.total_runs}
                          />
                          <MetricCard
                            label="Success"
                            value={scheduleLogsData.summary.success}
                          />
                          <MetricCard
                            label="Failed"
                            value={scheduleLogsData.summary.failed}
                          />
                          <MetricCard
                            label="Running"
                            value={scheduleLogsData.summary.running}
                          />
                        </div>
                        <div className="overflow-x-auto rounded-3xl border border-border/70">
                          <table className="min-w-full divide-y divide-border text-sm">
                            <thead className="bg-muted/60 text-left text-xs uppercase tracking-[0.18em] text-muted-foreground">
                              <tr>
                                <th className="px-4 py-3">Job</th>
                                <th className="px-4 py-3">Status</th>
                                <th className="px-4 py-3">Started</th>
                                <th className="px-4 py-3">Fetched</th>
                                <th className="px-4 py-3">New</th>
                                <th className="px-4 py-3">Deduped</th>
                                <th className="px-4 py-3">Verified</th>
                                <th className="px-4 py-3">Error</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-border bg-background/40">
                              {scheduleLogsData.items.map((item) => (
                                <tr
                                  key={item.id}
                                  className="hover:bg-accent/50"
                                >
                                  <td className="px-4 py-3 font-medium text-foreground">
                                    {item.job}
                                  </td>
                                  <td className="px-4 py-3 text-muted-foreground">
                                    {item.status}
                                  </td>
                                  <td className="px-4 py-3 text-muted-foreground">
                                    {item.started}
                                  </td>
                                  <td className="px-4 py-3 text-muted-foreground">
                                    {item.fetched}
                                  </td>
                                  <td className="px-4 py-3 text-muted-foreground">
                                    {item.new}
                                  </td>
                                  <td className="px-4 py-3 text-muted-foreground">
                                    {item.deduped}
                                  </td>
                                  <td className="px-4 py-3 text-muted-foreground">
                                    {item.verified}
                                  </td>
                                  <td className="px-4 py-3 text-muted-foreground">
                                    {item.error || "-"}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6 2xl:sticky 2xl:top-6 2xl:self-start">
            <Card className="border-border/70 bg-card/95 shadow-sm">
              <CardHeader>
                <CardTitle>Page Copilot</CardTitle>
                <CardDescription>
                  Use the selected opportunity and the currently visible dataset
                  as the basis for AI follow-up.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {selectedOpportunity ? (
                  <div className="rounded-2xl border border-border/70 bg-background/70 p-4 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-foreground">
                        Current selection
                      </span>
                      <Badge variant="outline">#{selectedOpportunity.id}</Badge>
                    </div>
                    <p className="mt-2 text-foreground">
                      {selectedOpportunity.title}
                    </p>
                    <p className="mt-1 text-muted-foreground">
                      {selectedOpportunity.type} ·{" "}
                      {selectedOpportunity.ecosystem ?? "-"} · score{" "}
                      {selectedOpportunity.score ?? "-"}
                    </p>
                  </div>
                ) : (
                  <EmptyState
                    title="No selected opportunity"
                    description="Pick a row from the opportunities table to anchor the agent."
                  />
                )}

                <div className="h-[620px] overflow-hidden rounded-3xl border border-border/70 bg-background/80 lg:h-[680px] 2xl:h-[720px]">
                  <CopilotChat
                    className="h-full"
                    labels={{
                      title: "Signal Room Copilot",
                      initial:
                        "Ask about the currently visible opportunities, or request a deep analysis of the selected row.",
                      placeholder:
                        "Example: Summarize why the selected opportunity is worth prioritizing.",
                    }}
                  />
                </div>
              </CardContent>
            </Card>

            <ResultPanels data={result} isRunning={isRunning} />
          </div>
        </div>
      </div>
    </main>
  );
}

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <Card className="border-border/70 bg-card/95 shadow-sm">
      <CardHeader className="pb-2">
        <CardDescription>{label}</CardDescription>
        <CardTitle className="text-3xl tracking-[-0.04em]">{value}</CardTitle>
      </CardHeader>
    </Card>
  );
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-card p-3">
      <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </div>
      <div className="mt-2 text-sm font-medium text-foreground">{value}</div>
    </div>
  );
}

function EmptyState({
  title,
  description,
  icon,
  actionLabel,
  onAction,
}: {
  title: string;
  description: string;
  icon?: React.ReactNode;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="rounded-3xl border border-dashed border-border bg-background/70 p-6 text-sm text-muted-foreground">
      <div className="flex items-center gap-2 text-foreground">
        {icon}
        <span className="font-medium">{title}</span>
      </div>
      <p className="mt-2">{description}</p>
      {actionLabel && onAction ? (
        <Button className="mt-4" variant="outline" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}

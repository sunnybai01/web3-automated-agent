export type AnalysisTargetInput = {
  event_id?: number;
  source_name?: string;
  from?: string;
  to?: string;
  limit?: number;
};

export type SelectTargetsRequest = {
  mode?: "mixed";
  event_id?: number;
  source_name?: string;
  from?: string;
  to?: string;
  limit?: number;
};

export type SelectTargetsResponse = {
  target_event_ids: number[];
  no_data?: boolean;
};

export type VerificationEvidenceItem = {
  category?: string;
  source?: string;
  detail?: string;
  impact?: string;
  weight?: number;
};

export type VerifyResponse = {
  score: number;
  level?: string;
  verdict: string;
  evidence?: VerificationEvidenceItem[];
  unknowns?: string[];
  conflicts?: string[];
};

export type OptionItem = {
  tier: string;
  summary: string;
  assumptions: string[];
};

export type ProposeOptionsRequest = {
  verified_facts: Record<string, string | number | boolean | undefined>;
};

export type ProposeOptionsResponse = {
  options: OptionItem[];
};

export type MixedModeResult = {
  selected: SelectTargetsResponse;
  verification: VerifyResponse;
  options: ProposeOptionsResponse;
};

export type DashboardOpportunityItem = {
  id: number;
  score: number | null;
  type: string;
  title: string;
  ecosystem: string | null;
  amount: string | null;
  deadline: string;
  heat: number;
  verified: boolean;
  source_trust: string;
  verification_verdict: string;
  apply_url: string;
};

export type DashboardOpportunityMetrics = {
  total_shown: number;
  avg_score: number;
  verified_percent: number;
  grants: number;
  bounties: number;
  hackathons: number;
  official: number;
  discovery: number;
};

export type DashboardOpportunitiesResponse = {
  metrics: DashboardOpportunityMetrics;
  items: DashboardOpportunityItem[];
};

export type DashboardSourceHealthItem = {
  source: string;
  status: string;
  last_success: string;
  last_fetch: string;
  failures: number;
  last_error: string;
};

export type DashboardSourceHealthSummary = {
  total_sources: number;
  healthy: number;
  degraded: number;
  down: number;
};

export type DashboardSourceHealthResponse = {
  summary: DashboardSourceHealthSummary;
  items: DashboardSourceHealthItem[];
};

export type DashboardScheduleLogItem = {
  id: number;
  job: string;
  status: string;
  started: string;
  fetched: number;
  new: number;
  deduped: number;
  classified: number;
  verified: number;
  error: string;
};

export type DashboardScheduleLogSummary = {
  total_runs: number;
  success: number;
  failed: number;
  running: number;
};

export type DashboardScheduleLogsResponse = {
  summary: DashboardScheduleLogSummary;
  items: DashboardScheduleLogItem[];
};

export type ManualScanScheduleResult = {
  schedule: string;
  status: string;
  fetched: number;
  new: number;
  deduped: number;
  classified: number;
  verified: number;
  fraud: number;
  pushed: number;
  error: string;
};

export type ManualScanStatusResponse = {
  job_id: string | null;
  status: string;
  triggered: boolean;
  started_at: string;
  finished_at: string;
  current_stage: string;
  schedules: ManualScanScheduleResult[];
  error: string;
};

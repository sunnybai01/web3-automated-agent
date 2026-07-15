import React from "react";

import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  ListChecks,
  Search,
  Telescope,
} from "lucide-react";

import type { InvestigationResponse, MixedModeResult } from "../types/chat";
import { Badge } from "./ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./ui/card";
import { Separator } from "./ui/separator";

type ResultPanelsProps = {
  data: MixedModeResult | null;
  investigation?: InvestigationResponse | null;
  isRunning?: boolean;
  isInvestigating?: boolean;
};

const verdictTone: Record<string, string> = {
  trusted: "bg-emerald-500/12 text-emerald-700 border-emerald-600/20",
  caution: "bg-amber-500/12 text-amber-700 border-amber-600/20",
  untrusted: "bg-rose-500/12 text-rose-700 border-rose-600/20",
};

const trajectoryTone: Record<string, string> = {
  load_event: "bg-sky-500/12 text-sky-700 border-sky-600/20",
  retrieve_similar_events:
    "bg-violet-500/12 text-violet-700 border-violet-600/20",
  fetch_supporting_evidence:
    "bg-amber-500/12 text-amber-700 border-amber-600/20",
  verify_event: "bg-emerald-500/12 text-emerald-700 border-emerald-600/20",
  finalize_conclusion: "bg-slate-500/12 text-slate-700 border-slate-600/20",
};

const trajectoryLabel: Record<string, string> = {
  load_event: "Load Event",
  retrieve_similar_events: "Retrieve Similar Events",
  fetch_supporting_evidence: "Fetch Supporting Evidence",
  verify_event: "Verification",
  finalize_conclusion: "Finalize Conclusion",
};

const trajectoryDescription: Record<string, string> = {
  load_event: "Loaded the selected opportunity from the event store.",
  retrieve_similar_events:
    "Checked historical signals for nearby matches and repeated patterns.",
  fetch_supporting_evidence:
    "Captured page-level evidence from the application or source URL.",
  verify_event:
    "Ran deterministic verification checks before forming a recommendation.",
  finalize_conclusion:
    "Compressed the gathered evidence into a final action recommendation.",
};

export default function ResultPanels({
  data,
  investigation = null,
  isRunning = false,
  isInvestigating = false,
}: ResultPanelsProps) {
  return (
    <Card className="border-border/70 bg-card/95 shadow-sm">
      <CardHeader>
        <CardTitle>Verification Digest</CardTitle>
        <CardDescription>
          Structured evidence, blind spots, and solution angles from the latest
          run.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {!data ? (
          <div className="rounded-3xl border border-dashed border-border bg-background/70 p-5 text-sm text-muted-foreground">
            {isRunning
              ? "The agent is fetching database facts and assembling the verification report..."
              : "No analysis loaded yet. Click Verify on any opportunity above or use the chat to populate this panel."}
          </div>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <Card className="border-border/60 bg-background/80">
                <CardHeader className="pb-2">
                  <CardDescription>Confidence score</CardDescription>
                  <CardTitle className="text-4xl tracking-[-0.04em]">
                    {data.verification.score}
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex items-center gap-2 text-sm text-muted-foreground">
                  <CheckCircle2 className="h-4 w-4 text-primary" />
                  Level: {data.verification.level ?? "unknown"}
                </CardContent>
              </Card>

              <Card className="border-border/60 bg-background/80">
                <CardHeader className="pb-2">
                  <CardDescription>Verdict</CardDescription>
                  <div>
                    <Badge
                      className={verdictTone[data.verification.verdict] ?? ""}
                    >
                      {data.verification.verdict}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  Selected IDs:{" "}
                  {data.selected.target_event_ids.join(", ") || "none"}
                </CardContent>
              </Card>
            </div>

            <Separator />

            <section className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                <ListChecks className="h-4 w-4 text-primary" /> Key Evidence
              </div>
              <div className="space-y-2">
                {data.verification.evidence?.length ? (
                  data.verification.evidence.map((item, index) => (
                    <div
                      key={`${item.detail ?? "evidence"}-${index}`}
                      className="rounded-2xl border border-border/70 bg-background/70 p-3 text-sm"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium text-foreground">
                          {item.category ?? "signal"}
                        </span>
                        <Badge variant="outline">
                          {item.impact ?? "neutral"}
                        </Badge>
                      </div>
                      <p className="mt-2 text-muted-foreground">
                        {item.detail}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No evidence items were returned.
                  </p>
                )}
              </div>
            </section>

            <section className="grid gap-4 md:grid-cols-2">
              <div className="space-y-3 rounded-3xl border border-border/70 bg-background/70 p-4">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <Clock3 className="h-4 w-4 text-primary" /> Unknowns
                </div>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {(data.verification.unknowns ?? []).length ? (
                    data.verification.unknowns?.map((item) => (
                      <li key={item}>• {item}</li>
                    ))
                  ) : (
                    <li>• No major unknowns reported.</li>
                  )}
                </ul>
              </div>

              <div className="space-y-3 rounded-3xl border border-border/70 bg-background/70 p-4">
                <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <AlertTriangle className="h-4 w-4 text-primary" /> Conflicts
                </div>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {(data.verification.conflicts ?? []).length ? (
                    data.verification.conflicts?.map((item) => (
                      <li key={item}>• {item}</li>
                    ))
                  ) : (
                    <li>• No explicit conflicts detected.</li>
                  )}
                </ul>
              </div>
            </section>

            <Separator />

            <section className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                <Telescope className="h-4 w-4 text-primary" /> Investigation
                Insight
              </div>
              {!investigation ? (
                <div className="rounded-2xl border border-dashed border-border bg-background/70 p-4 text-sm text-muted-foreground">
                  {isInvestigating
                    ? "The agent is investigating the selected opportunity..."
                    : "No investigation loaded yet. Use Verify or Ask Copilot on a selected opportunity to inspect historical matches and supporting evidence."}
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Card className="border-border/60 bg-background/80">
                      <CardHeader className="pb-2">
                        <CardDescription>Mission status</CardDescription>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">
                            {investigation.mission.status}
                          </Badge>
                          <Badge variant="outline">
                            {investigation.conclusion?.recommended_action ??
                              "n/a"}
                          </Badge>
                        </div>
                      </CardHeader>
                      <CardContent className="text-sm text-muted-foreground">
                        Mission #{investigation.mission.id} for event #
                        {investigation.event_id}
                      </CardContent>
                    </Card>

                    <Card className="border-border/60 bg-background/80">
                      <CardHeader className="pb-2">
                        <CardDescription>Investigation verdict</CardDescription>
                        <CardTitle className="text-lg tracking-[-0.03em]">
                          {investigation.conclusion?.verdict ??
                            investigation.status}
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="text-sm text-muted-foreground">
                        {investigation.conclusion?.summary ??
                          investigation.error ??
                          "No investigation summary available."}
                      </CardContent>
                    </Card>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-3 rounded-3xl border border-border/70 bg-background/70 p-4">
                      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                        <Search className="h-4 w-4 text-primary" /> Similar
                        Events
                      </div>
                      {(investigation.conclusion?.similar_events ?? [])
                        .length ? (
                        <ul className="space-y-2 text-sm text-muted-foreground">
                          {investigation.conclusion?.similar_events.map(
                            (item) => (
                              <li key={item.event_id}>
                                <span className="font-medium text-foreground">
                                  {item.title}
                                </span>{" "}
                                · {item.ecosystem ?? "-"} · sim{" "}
                                {item.similarity}
                              </li>
                            )
                          )}
                        </ul>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          No historical near-duplicates were surfaced.
                        </p>
                      )}
                    </div>

                    <div className="space-y-3 rounded-3xl border border-border/70 bg-background/70 p-4">
                      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                        <CheckCircle2 className="h-4 w-4 text-primary" />
                        Supporting Evidence
                      </div>
                      {investigation.conclusion?.supporting_evidence ? (
                        <div className="space-y-2 text-sm text-muted-foreground">
                          <p className="font-medium text-foreground">
                            {investigation.conclusion.supporting_evidence.title}
                          </p>
                          <p>
                            {
                              investigation.conclusion.supporting_evidence
                                .excerpt
                            }
                          </p>
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          No supporting page evidence was captured.
                        </p>
                      )}
                    </div>
                  </div>

                  {investigation.error ? (
                    <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                      Investigation error: {investigation.error}
                    </div>
                  ) : null}

                  <details className="rounded-2xl border border-border/70 bg-background/70 p-4">
                    <summary className="cursor-pointer list-none text-sm font-medium text-foreground">
                      Mission Trajectory
                    </summary>
                    <div className="mt-4 space-y-3">
                      {(investigation.trajectory ?? []).length ? (
                        investigation.trajectory.map((step) => (
                          <div
                            key={`${step.step_index}-${step.action}`}
                            className="rounded-2xl border border-border/60 bg-card/70 p-3"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-foreground">
                                  {trajectoryLabel[step.action] ?? step.action}
                                </span>
                                <Badge
                                  className={trajectoryTone[step.action] ?? ""}
                                  variant="outline"
                                >
                                  {step.action}
                                </Badge>
                              </div>
                              <Badge variant="outline">
                                step {step.step_index}
                              </Badge>
                            </div>
                            {step.thought ? (
                              <p className="mt-2 text-sm text-muted-foreground">
                                {step.thought}
                              </p>
                            ) : null}
                            {trajectoryDescription[step.action] ? (
                              <p className="mt-2 text-sm text-foreground/80">
                                {trajectoryDescription[step.action]}
                              </p>
                            ) : null}
                            <div className="mt-3 grid gap-3 md:grid-cols-2">
                              <div>
                                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                                  Input
                                </p>
                                <pre className="mt-2 overflow-x-auto rounded-xl bg-background p-2 text-xs text-muted-foreground">
                                  {JSON.stringify(
                                    step.action_input ?? {},
                                    null,
                                    2
                                  )}
                                </pre>
                              </div>
                              <div>
                                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                                  Observation
                                </p>
                                <pre className="mt-2 overflow-x-auto rounded-xl bg-background p-2 text-xs text-muted-foreground">
                                  {JSON.stringify(
                                    step.observation ?? {},
                                    null,
                                    2
                                  )}
                                </pre>
                              </div>
                            </div>
                          </div>
                        ))
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          No trajectory steps were recorded.
                        </p>
                      )}
                    </div>
                  </details>
                </div>
              )}
            </section>

            <Separator />

            <section className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                <span
                  className="inline-block h-2 w-2 rounded-full bg-primary"
                  aria-hidden="true"
                />{" "}
                Build Paths
              </div>
              <div className="space-y-3">
                {(data.options.options ?? []).map((option) => (
                  <div
                    key={option.tier}
                    className="rounded-2xl border border-border/70 bg-background/70 p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium uppercase tracking-[0.18em] text-muted-foreground">
                        {option.tier}
                      </span>
                      <Badge variant="outline">strategy</Badge>
                    </div>
                    <p className="mt-3 text-sm text-foreground">
                      {option.summary}
                    </p>
                    <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
                      {option.assumptions.map((assumption) => (
                        <li key={assumption}>• {assumption}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </CardContent>
    </Card>
  );
}

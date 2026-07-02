import React from "react";

import { AlertTriangle, CheckCircle2, Clock3, ListChecks } from "lucide-react";

import type { MixedModeResult } from "../types/chat";
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
  isRunning?: boolean;
};

const verdictTone: Record<string, string> = {
  trusted: "bg-emerald-500/12 text-emerald-700 border-emerald-600/20",
  caution: "bg-amber-500/12 text-amber-700 border-amber-600/20",
  untrusted: "bg-rose-500/12 text-rose-700 border-rose-600/20",
};

export default function ResultPanels({
  data,
  isRunning = false,
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
              : "No analysis loaded yet. Use the chat or click Run Verification Now to populate this panel."}
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

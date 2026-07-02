import type {
  AnalysisTargetInput,
  MixedModeResult,
  ProposeOptionsRequest,
  ProposeOptionsResponse,
  SelectTargetsRequest,
  SelectTargetsResponse,
  VerifyResponse,
} from "../types/chat";

type ChatApi = {
  selectTargets: (
    input: SelectTargetsRequest
  ) => Promise<SelectTargetsResponse>;
  verify: (input: { target_event_ids: number[] }) => Promise<VerifyResponse>;
  proposeOptions: (
    input: ProposeOptionsRequest
  ) => Promise<ProposeOptionsResponse>;
};

export async function runMixedModeVerification(
  api: ChatApi,
  input: SelectTargetsRequest
): Promise<MixedModeResult> {
  const selected = await api.selectTargets({ mode: "mixed", ...input });
  const verification = await api.verify({
    target_event_ids: selected.target_event_ids || [],
  });
  const options = await api.proposeOptions({
    verified_facts: {
      ...(input as AnalysisTargetInput),
      score: verification.score,
      level: verification.level,
      verdict: verification.verdict,
    },
  });

  return { selected, verification, options };
}

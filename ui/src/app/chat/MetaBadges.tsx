import type { Cache, Cost, Redaction, Routing } from "../../lib/types.ts";

/**
 * MetaBadges — the cost-as-a-feature surface. Renders the gateway's per-answer
 * routing/cache/cost telemetry (P3) as compact chips so the cost/latency story is
 * visible inline, plus a redaction chip when PII was stripped at egress (LLM02).
 */
function Badge({ label, title }: { label: string; title?: string }) {
  return (
    <span
      title={title}
      className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600"
    >
      {label}
    </span>
  );
}

export function MetaBadges({
  routing,
  cache,
  cost,
  redaction,
}: {
  routing: Routing;
  cache: Cache;
  cost: Cost;
  redaction?: Redaction;
}) {
  return (
    <div className="flex flex-wrap items-center gap-1.5" data-testid="meta-badges">
      <Badge label={cache.hit ? "cache: hit" : "cache: miss"} title="Gateway semantic cache" />
      <Badge label={routing.modelTier} title={routing.model ?? "model tier"} />
      {routing.escalated && <Badge label="escalated" title="Router bumped tiers" />}
      <Badge
        label={`${cost.promptTokens + cost.completionTokens} tok`}
        title={`prompt ${cost.promptTokens} / completion ${cost.completionTokens}`}
      />
      <Badge label={`${cost.costUnits.toFixed(4)} units`} title="Estimated cost units" />
      <Badge label={`${cost.latencyMs} ms`} title="End-to-end latency" />
      {redaction?.applied && <Badge label="PII redacted" title="Sensitive output redacted" />}
    </div>
  );
}

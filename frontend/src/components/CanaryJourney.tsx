import { useState } from "react";
import { FileText, Wrench, Database, ArrowRight, AlertTriangle } from "lucide-react";
import type { CanaryChannel, CanaryObservation, CanaryProvenance } from "../types";

type T = (key: string, vars?: Record<string, string | number>) => string;

const CHANNEL_ORDER: CanaryChannel[] = ["response_text", "tool_call", "business_state"];

const CHANNEL_META: Record<CanaryChannel, { labelKey: string; icon: typeof FileText }> = {
  response_text: { labelKey: "report.canaryJourney.channelResponseText", icon: FileText },
  tool_call: { labelKey: "report.canaryJourney.channelToolCall", icon: Wrench },
  business_state: { labelKey: "report.canaryJourney.channelBusinessState", icon: Database },
};

const CONTEXT_KEYS: Record<string, string> = {
  quoted: "report.canaryJourney.ctxQuoted",
  echoed: "report.canaryJourney.ctxEchoed",
  leaked: "report.canaryJourney.ctxLeaked",
  tool_invoked: "report.canaryJourney.ctxToolInvoked",
  state_persisted: "report.canaryJourney.ctxStatePersisted",
};

const STRENGTH_KEYS: Record<string, string> = {
  weak: "report.canaryJourney.strengthWeak",
  strong: "report.canaryJourney.strengthStrong",
  hard: "report.canaryJourney.strengthHard",
};

// Evidence-level -> tailwind palette. Stronger provenance reads "hotter".
function levelClasses(level: string | null | undefined, reached: boolean): string {
  if (!reached) return "border-dashed border-slate-200 bg-slate-50 text-slate-400";
  switch (level) {
    case "E5":
      return "border-rose-300 bg-rose-50 text-rose-800";
    case "E4":
      return "border-red-300 bg-red-50 text-red-800";
    case "E3":
      return "border-orange-300 bg-orange-50 text-orange-800";
    default:
      return "border-amber-300 bg-amber-50 text-amber-800";
  }
}

function badgeClasses(level: string | null | undefined): string {
  switch (level) {
    case "E5":
      return "bg-rose-600 text-white";
    case "E4":
      return "bg-red-600 text-white";
    case "E3":
      return "bg-orange-500 text-white";
    default:
      return "bg-amber-500 text-white";
  }
}

const E_ORDER: Record<string, number> = { E0: 0, E1: 1, E2: 2, E3: 3, E4: 4, E5: 5 };

function strongestLevel(obs: CanaryObservation[]): string | null {
  if (obs.length === 0) return null;
  return obs.reduce((best, o) => ((E_ORDER[o.evidence_level] ?? 0) > (E_ORDER[best] ?? 0) ? o.evidence_level : best), obs[0].evidence_level);
}

export function CanaryJourney({ provenance, t }: { provenance: CanaryProvenance; t: T }) {
  const [open, setOpen] = useState<CanaryChannel | null>(provenance.strongest_channel ?? null);

  const obsByChannel = (channel: CanaryChannel) => provenance.observations.filter((o) => o.channel === channel);

  const ctxLabel = (context: string) => (CONTEXT_KEYS[context] ? t(CONTEXT_KEYS[context]) : context);
  const strengthLabel = (strength: string) => (STRENGTH_KEYS[strength] ? t(STRENGTH_KEYS[strength]) : strength);

  return (
    <div data-testid="canary-journey">
      <div className="flex items-center justify-between gap-2 flex-wrap mb-1">
        <p className="text-xs text-gray-500 uppercase">{t("report.canaryJourney.title")}</p>
        <div className="flex items-center gap-2">
          {provenance.evidence_level && (
            <span className={`inline-flex px-2 py-0.5 rounded text-[11px] font-mono ${badgeClasses(provenance.evidence_level)}`}>
              {provenance.evidence_level}
            </span>
          )}
          {provenance.is_quoted_only && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] bg-amber-100 text-amber-800 border border-amber-200">
              <AlertTriangle className="w-3 h-3" />
              {t("report.canaryJourney.quotedOnly")}
            </span>
          )}
        </div>
      </div>
      <p className="text-xs text-slate-500 mb-2">{t("report.canaryJourney.subtitle")}</p>

      <div className="flex items-stretch gap-1 flex-wrap">
        {CHANNEL_ORDER.map((channel, idx) => {
          const obs = obsByChannel(channel);
          const reached = obs.length > 0;
          const level = strongestLevel(obs);
          const meta = CHANNEL_META[channel];
          const Icon = meta.icon;
          const isOpen = open === channel;
          return (
            <div key={channel} className="flex items-center">
              <button
                type="button"
                disabled={!reached}
                onClick={() => setOpen(isOpen ? null : channel)}
                aria-expanded={isOpen}
                data-testid={`canary-stage-${channel}`}
                data-reached={reached}
                className={`text-left rounded-lg border px-3 py-2 min-w-[120px] transition ${levelClasses(level, reached)} ${reached ? "cursor-pointer hover:brightness-95" : "cursor-default"} ${isOpen ? "ring-2 ring-offset-1 ring-slate-400" : ""}`}
              >
                <div className="flex items-center gap-1.5">
                  <Icon className="w-3.5 h-3.5" />
                  <span className="text-xs font-medium">{t(meta.labelKey)}</span>
                </div>
                <div className="flex items-center gap-1.5 mt-1">
                  {reached ? (
                    <>
                      <span className={`inline-flex px-1.5 rounded text-[10px] font-mono ${badgeClasses(level)}`}>{level}</span>
                      <span className="text-[10px]">{ctxLabel(obs[0].context)}</span>
                    </>
                  ) : (
                    <span className="text-[10px] italic">{t("report.canaryJourney.notReached")}</span>
                  )}
                </div>
              </button>
              {idx < CHANNEL_ORDER.length - 1 && (
                <ArrowRight className="w-4 h-4 mx-0.5 text-slate-300 shrink-0" />
              )}
            </div>
          );
        })}
      </div>

      {open && obsByChannel(open).length > 0 && (
        <div data-testid="canary-detail" className="mt-2 rounded-lg border border-slate-200 bg-white p-3 space-y-2">
          {obsByChannel(open).map((o, i) => (
            <div key={`${o.token}-${o.channel}-${i}`} className="text-xs space-y-1">
              <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
                <span className="text-slate-400">{t("report.canaryJourney.tokenLabel")}</span>
                <span className="font-mono text-slate-800 break-all">{o.token}</span>
                <span className="text-slate-400">{t("report.canaryJourney.contextLabel")}</span>
                <span className="text-slate-700">{ctxLabel(o.context)}</span>
                <span className="text-slate-400">{t("report.canaryJourney.strengthLabel")}</span>
                <span className="text-slate-700">{strengthLabel(o.strength)} · {o.evidence_level}</span>
                <span className="text-slate-400">{t("report.canaryJourney.whereLabel")}</span>
                <span className="text-slate-700">{o.excerpt}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

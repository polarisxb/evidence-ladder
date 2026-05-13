import { useLocale } from "../i18n";

/** Compact system-architecture diagram for the About page.
 *  Pure React + TailwindCSS — no external images or SVG assets. */
export function ArchitectureDiagram() {
  const { t } = useLocale();

  return (
    <div className="w-full overflow-x-auto">
      <div className="min-w-[720px] flex flex-col items-center gap-3 py-2">
        {/* Row 1 — User / Browser */}
        <div className="flex items-center gap-2">
          <span className="text-lg">🖥️</span>
          <span className="text-sm font-semibold text-gray-700">{t("arch.user")}</span>
        </div>
        <Arrow />

        {/* Row 2 — Frontend */}
        <Box
          title={t("arch.frontend")}
          color="cyan"
          items={["React 19", "TypeScript", "TailwindCSS 4", "Vite 8", "Recharts"]}
        />
        <Arrow label="Nginx reverse proxy" />

        {/* Row 3 — Backend (wide, multi-column) */}
        <div className="w-full rounded-xl border-2 border-indigo-200 bg-indigo-50/60 p-4 space-y-3">
          <p className="text-sm font-bold text-indigo-800 text-center tracking-wide">
            {t("arch.backend")} — FastAPI + SQLAlchemy
          </p>
          <div className="grid grid-cols-3 gap-3">
            {/* Attack Engine */}
            <div className="rounded-lg border border-red-200 bg-white p-3 space-y-1.5">
              <p className="text-xs font-bold text-red-700 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-red-400 inline-block" />
                {t("arch.attackEngine")}
              </p>
              <Tags items={["PAIR", "TAP", "Crescendo", "FITD", "MSJ", "ICE"]} color="red" />
              <Tags items={[t("arch.templateSystem"), t("arch.mutationEngine")]} color="orange" />
            </div>

            {/* Judge System */}
            <div className="rounded-lg border border-emerald-200 bg-white p-3 space-y-1.5">
              <p className="text-xs font-bold text-emerald-700 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />
                {t("arch.judgeSystem")}
              </p>
              <Tags items={[t("arch.aiAnalyzer"), t("arch.evidenceArbiter")]} color="emerald" />
              <Tags items={[t("arch.ruleEngine"), "CVSS v4.0", t("arch.quartetEval")]} color="teal" />
            </div>

            {/* Infra */}
            <div className="rounded-lg border border-slate-200 bg-white p-3 space-y-1.5">
              <p className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-slate-400 inline-block" />
                {t("arch.infra")}
              </p>
              <Tags items={["SQLite", "WebSocket", t("arch.reportGen")]} color="slate" />
              <Tags items={[t("arch.authGuard"), t("arch.ssrfGuard")]} color="violet" />
            </div>
          </div>
        </div>

        {/* Row 4 — Arrows going two directions */}
        <div className="w-full grid grid-cols-2 gap-8 px-8">
          <div className="flex flex-col items-center gap-2">
            <Arrow label={t("arch.attackTraffic")} />
            {/* Target Apps */}
            <Box
              title={t("arch.targetApps")}
              color="amber"
              items={["FinanceBot", "ShopBot", t("arch.customApi"), t("arch.adapterProtocol")]}
            />
          </div>
          <div className="flex flex-col items-center gap-2">
            <Arrow label={t("arch.llmCalls")} />
            {/* LLM APIs */}
            <Box
              title={t("arch.llmApis")}
              color="violet"
              items={["DeepSeek", "OpenAI", "Anthropic Claude", t("arch.openaiCompatible")]}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function Arrow({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      {label && (
        <span className="text-[10px] text-gray-400 font-medium tracking-wide">{label}</span>
      )}
      <div className="w-px h-4 bg-gray-300" />
      <div className="w-0 h-0 border-l-[5px] border-l-transparent border-r-[5px] border-r-transparent border-t-[6px] border-t-gray-300" />
    </div>
  );
}

function Box({
  title,
  color,
  items,
}: {
  title: string;
  color: "cyan" | "amber" | "violet" | "emerald";
  items: string[];
}) {
  const styles: Record<string, { border: string; bg: string; title: string; tag: string; tagBg: string }> = {
    cyan:    { border: "border-cyan-200",    bg: "bg-cyan-50/60",    title: "text-cyan-800",    tag: "text-cyan-700",    tagBg: "bg-cyan-100" },
    amber:   { border: "border-amber-200",   bg: "bg-amber-50/60",   title: "text-amber-800",   tag: "text-amber-700",   tagBg: "bg-amber-100" },
    violet:  { border: "border-violet-200",  bg: "bg-violet-50/60",  title: "text-violet-800",  tag: "text-violet-700",  tagBg: "bg-violet-100" },
    emerald: { border: "border-emerald-200", bg: "bg-emerald-50/60", title: "text-emerald-800", tag: "text-emerald-700", tagBg: "bg-emerald-100" },
  };
  const s = styles[color];

  return (
    <div className={`rounded-xl border-2 ${s.border} ${s.bg} px-5 py-3 text-center min-w-[260px]`}>
      <p className={`text-sm font-bold ${s.title} mb-2`}>{title}</p>
      <div className="flex flex-wrap justify-center gap-1.5">
        {items.map((item) => (
          <span key={item} className={`text-[11px] px-2 py-0.5 rounded-full ${s.tagBg} ${s.tag} font-medium`}>
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

function Tags({ items, color }: { items: string[]; color: string }) {
  const colorMap: Record<string, string> = {
    red: "bg-red-50 text-red-600 border-red-100",
    orange: "bg-orange-50 text-orange-600 border-orange-100",
    emerald: "bg-emerald-50 text-emerald-600 border-emerald-100",
    teal: "bg-teal-50 text-teal-600 border-teal-100",
    slate: "bg-slate-50 text-slate-600 border-slate-100",
    violet: "bg-violet-50 text-violet-600 border-violet-100",
  };
  const cls = colorMap[color] ?? colorMap.slate;

  return (
    <div className="flex flex-wrap gap-1">
      {items.map((item) => (
        <span key={item} className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${cls}`}>
          {item}
        </span>
      ))}
    </div>
  );
}

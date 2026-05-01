type Translate = (key: string, params?: Record<string, string | number>) => string;

interface ResultSemanticsCardProps {
  t: Translate;
}

const sections = [
  {
    titleKey: "results.resultGuideVerdictTitle",
    bodyKey: "results.resultGuideVerdictBody",
  },
  {
    titleKey: "results.resultGuideQuartetTitle",
    bodyKey: "results.resultGuideQuartetBody",
  },
  {
    titleKey: "results.resultGuideScoresTitle",
    bodyKey: "results.resultGuideScoresBody",
  },
  {
    titleKey: "results.resultGuideBusinessTitle",
    bodyKey: "results.resultGuideBusinessBody",
  },
];

export function ResultSemanticsCard({ t }: ResultSemanticsCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/80 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">{t("results.resultGuideTitle")}</p>
          <p className="text-xs text-slate-500">{t("results.resultGuideSubtitle")}</p>
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {sections.map((section) => (
          <div key={section.titleKey} className="rounded-lg border border-white/80 bg-white p-3 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {t(section.titleKey)}
            </p>
            <p className="mt-2 text-sm leading-6 text-slate-700">{t(section.bodyKey)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

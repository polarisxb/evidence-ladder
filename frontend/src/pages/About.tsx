import type { ReactNode } from "react";
import {
  ArrowRight,
  BookOpen,
  ClipboardCheck,
  ExternalLink,
  FileBarChart,
  GitBranch,
  Layers,
  Network,
  PlugZap,
  ShieldCheck,
  Swords,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { APP_VERSION_LABEL } from "../appInfo";
import { ArchitectureDiagram } from "../components/ArchitectureDiagram";
import { useLocale } from "../i18n";

// Level names are the method's own terms and stay in English in every locale.
const LEVELS = [
  { code: "E5", name: "Probe-Verified" },
  { code: "E4", name: "Tool-Observed" },
  { code: "E3", name: "Rule-Verified" },
  { code: "E2", name: "Judge-Suspected" },
  { code: "E1", name: "Text Claim" },
  { code: "E0", name: "Not Evaluable" },
] as const;

const LEVEL_BADGE = [
  "bg-gray-100 text-gray-500",
  "bg-indigo-50 text-indigo-500",
  "bg-indigo-100 text-indigo-600",
  "bg-indigo-200 text-indigo-700",
  "bg-indigo-400 text-white",
  "bg-indigo-600 text-white",
];
const LEVEL_BAR = ["bg-gray-300", "bg-indigo-200", "bg-indigo-300", "bg-indigo-400", "bg-indigo-500", "bg-indigo-600"];

const QUARTET = [
  { name: "Clean", key: "about.quartet.clean" },
  { name: "Attack", key: "about.quartet.attack" },
  { name: "Quoted Attack", key: "about.quartet.quoted" },
  { name: "Benign Distractor", key: "about.quartet.benign" },
];

const RETESTS = ["judgeOnly", "canaryText", "claimOnly", "suspected"];

const FEATURES: Array<{ icon: LucideIcon; key: string }> = [
  { icon: Swords, key: "engines" },
  { icon: Workflow, key: "autotest" },
  { icon: PlugZap, key: "adapters" },
  { icon: FileBarChart, key: "reports" },
  { icon: ClipboardCheck, key: "review" },
  { icon: ShieldCheck, key: "security" },
];

const STANDARDS = [
  { name: "OWASP LLM Top 10", version: "2025", itemsKey: "about.owaspItems" },
  { name: "MITRE ATLAS", version: "2025", itemsKey: "about.atlasItems" },
  { name: "CVSS", version: "v4.0", itemsKey: "about.cvssItems" },
  { name: "HarmBench", version: "2024", itemsKey: "about.harmbenchItems" },
];

const PAPERS = [
  { title: "A Coin Flip for Safety", venue: "arXiv 2026", authors: "", url: "https://arxiv.org/abs/2603.06594" },
  { title: "When Scanners Lie", venue: "arXiv 2026", authors: "", url: "https://arxiv.org/abs/2603.14633" },
  { title: "Kill-Chain Canaries", venue: "arXiv 2026", authors: "", url: "https://arxiv.org/abs/2603.28013" },
  { title: "Crescendo Multi-Turn Jailbreak", venue: "USENIX Security 2025", authors: "Russinovich et al.", url: "https://arxiv.org/abs/2404.01833" },
  { title: "Tree of Attacks with Pruning (TAP)", venue: "NeurIPS 2024", authors: "Mehrotra et al.", url: "https://arxiv.org/abs/2312.02119" },
  { title: "Bypassing LLM Guardrails", venue: "arXiv 2025", authors: "Hackett et al.", url: "https://arxiv.org/abs/2504.11168" },
  { title: "AutoInject via RL", venue: "arXiv 2026", authors: "Chen et al.", url: "https://arxiv.org/abs/2602.05746" },
  { title: "Spotlighting Defense", venue: "arXiv 2024", authors: "Hines et al. (Microsoft)", url: "https://arxiv.org/abs/2403.14720" },
  { title: "Instruction Hierarchy", venue: "arXiv 2024", authors: "OpenAI", url: "https://arxiv.org/abs/2404.13208" },
];

function SectionTitle({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <h2 className="flex items-center gap-2 text-base font-semibold text-gray-900">
      <Icon className="h-4 w-4 text-gray-400" aria-hidden />
      {children}
    </h2>
  );
}

function MethodCard({ title, desc, children }: { title: string; desc: string; children: ReactNode }) {
  return (
    <div className="card flex flex-col gap-3 p-5">
      <div>
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
        <p className="mt-1 text-xs leading-5 text-gray-500">{desc}</p>
      </div>
      {children}
    </div>
  );
}

export function About() {
  const { t } = useLocale();

  const facts = [
    { value: "E0–E5", label: t("about.factLevels") },
    { value: "Quartet", label: t("about.factQuartet") },
    { value: "7", label: t("about.factTemplates") },
    { value: "7", label: t("about.factEngines") },
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <section className="card overflow-hidden">
        <div className="border-b border-gray-100 bg-gradient-to-br from-white via-white to-indigo-50/60 p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p
                className="text-3xl font-bold tracking-[0.04em] text-gray-900"
                style={{ fontFamily: '"Noto Serif SC","Source Han Serif SC","Songti SC",serif' }}
              >
                Evidence<span className="mx-1 text-amber-600">·</span>Ladder
              </p>
              <h1 className="mt-2 text-lg font-semibold text-gray-800">{t("app.fullName")}</h1>
            </div>
            <span className="rounded-full border border-gray-200 bg-white px-3 py-1 font-mono text-xs text-gray-600">
              {APP_VERSION_LABEL}
            </span>
          </div>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-gray-600">{t("about.tagline")}</p>
        </div>
        <dl className="grid grid-cols-2 sm:grid-cols-4">
          {facts.map((fact, index) => (
            <div key={fact.label} className={`p-5 ${index > 0 ? "sm:border-l sm:border-gray-100" : ""} ${index % 2 === 1 ? "border-l border-gray-100 sm:border-l" : ""}`}>
              <dt className="font-mono text-xl font-semibold text-gray-900">{fact.value}</dt>
              <dd className="mt-1 text-xs text-gray-500">{fact.label}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="space-y-3">
        <SectionTitle icon={Layers}>{t("about.ladderTitle")}</SectionTitle>
        <div className="card p-5">
          <div className="mb-3 flex items-start justify-between gap-4">
            <p className="max-w-2xl text-sm leading-6 text-gray-600">{t("about.ladderDesc")}</p>
            <span className="hidden shrink-0 text-xs text-gray-400 sm:block">↑ {t("about.ladderStrength")}</span>
          </div>
          <ol className="divide-y divide-gray-100" aria-label={t("about.ladderTitle")}>
            {LEVELS.map(({ code, name }) => {
              const strength = Number(code.slice(1));
              return (
                <li key={code} className="flex items-center gap-4 py-2.5">
                  <span className={`w-11 shrink-0 rounded-md py-1 text-center font-mono text-xs font-semibold ${LEVEL_BADGE[strength]}`}>
                    {code}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900">{name}</p>
                    <p className="text-xs text-gray-500">{t(`about.level.${code}`)}</p>
                  </div>
                  <div className="hidden w-36 shrink-0 sm:block" aria-hidden>
                    <div className="h-1.5 rounded-full bg-gray-100">
                      <div className={`h-1.5 rounded-full ${LEVEL_BAR[strength]}`} style={{ width: `${((strength + 1) / LEVELS.length) * 100}%` }} />
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      </section>

      <section className="space-y-3">
        <SectionTitle icon={GitBranch}>{t("about.methodTitle")}</SectionTitle>
        <div className="grid gap-4 lg:grid-cols-3">
          <MethodCard title={t("about.quartetTitle")} desc={t("about.quartetDesc")}>
            <ul className="space-y-2">
              {QUARTET.map((variant) => (
                <li key={variant.name} className="text-xs leading-5">
                  <span className="font-mono font-medium text-gray-900">{variant.name}</span>
                  <span className="block text-gray-500">{t(variant.key)}</span>
                </li>
              ))}
            </ul>
          </MethodCard>
          <MethodCard title={t("about.retestTitle")} desc={t("about.retestDesc")}>
            <ul className="space-y-2">
              {RETESTS.map((key) => (
                <li key={key} className="text-xs leading-5">
                  <span className="text-gray-600">{t(`about.retest.${key}`)}</span>
                  <span className="flex items-center gap-1 font-medium text-indigo-700">
                    <ArrowRight className="h-3 w-3 shrink-0" aria-hidden />
                    {t(`about.retest.${key}Action`)}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-auto text-[11px] leading-5 text-gray-400">{t("about.retestFootnote")}</p>
          </MethodCard>
          <MethodCard title={t("about.calibrationTitle")} desc={t("about.calibrationDesc")}>
            <p className="rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-700">{t("about.calibrationMetrics")}</p>
          </MethodCard>
        </div>
      </section>

      <section className="space-y-3">
        <SectionTitle icon={ClipboardCheck}>{t("about.featuresTitle")}</SectionTitle>
        <div className="card grid divide-y divide-gray-100 sm:grid-cols-2 sm:divide-y-0">
          {FEATURES.map(({ icon: Icon, key }, index) => (
            <div
              key={key}
              className={`flex gap-3 p-5 ${index >= 2 ? "sm:border-t sm:border-gray-100" : ""} ${index % 2 === 1 ? "sm:border-l sm:border-gray-100" : ""}`}
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-700">
                <Icon className="h-4 w-4" aria-hidden />
              </span>
              <div>
                <h3 className="text-sm font-semibold text-gray-900">{t(`about.feature.${key}`)}</h3>
                <p className="mt-1 text-xs leading-5 text-gray-500">{t(`about.feature.${key}Desc`)}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <SectionTitle icon={Network}>{t("about.architectureTitle")}</SectionTitle>
        <div className="card p-5">
          <ArchitectureDiagram />
        </div>
      </section>

      <section className="space-y-3">
        <SectionTitle icon={BookOpen}>{t("about.referencesTitle")}</SectionTitle>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <div className="card p-5">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">{t("about.standardsTitle")}</h3>
            <ul className="divide-y divide-gray-100">
              {STANDARDS.map((standard) => (
                <li key={standard.name} className="flex items-baseline justify-between gap-3 py-2">
                  <span className="text-sm text-gray-900">
                    {standard.name} <span className="font-mono text-xs text-gray-400">{standard.version}</span>
                  </span>
                  <span className="text-xs text-gray-500">{t(standard.itemsKey)}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="card p-5">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">{t("about.papersTitle")}</h3>
            <ul className="divide-y divide-gray-100">
              {PAPERS.map((paper) => (
                <li key={paper.title}>
                  <a
                    href={paper.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex items-center gap-3 py-2"
                  >
                    <span className="min-w-0 flex-1 truncate text-sm text-gray-900 group-hover:text-indigo-700">{paper.title}</span>
                    <span className="hidden shrink-0 text-xs text-gray-400 sm:block">
                      {[paper.venue, paper.authors].filter(Boolean).join(" · ")}
                    </span>
                    <ExternalLink className="h-3 w-3 shrink-0 text-gray-300 group-hover:text-indigo-400" aria-hidden />
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>
    </div>
  );
}

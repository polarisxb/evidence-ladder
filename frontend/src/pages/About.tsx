import { Shield, Zap, Target, BarChart3, BookOpen, ExternalLink, Box } from "lucide-react";
import { useLocale } from "../i18n";
import { ArchitectureDiagram } from "../components/ArchitectureDiagram";

const FRAMEWORKS = [
  { name: "OWASP LLM Top 10", version: "2025", items: 10 },
  { name: "MITRE ATLAS", version: "2025", items: "66 techniques" },
  { name: "CVSS", version: "v4.0", items: "0-10 scale" },
  { name: "HarmBench", version: "2024", items: "510 behaviors" },
];

const PAPERS = [
  { title: "Crescendo Multi-Turn Jailbreak",     venue: "USENIX Security 2025", authors: "Russinovich et al.",    url: "https://arxiv.org/abs/2404.01833" },
  { title: "Tree of Attacks with Pruning (TAP)", venue: "NeurIPS 2024",         authors: "Mehrotra et al.",       url: "https://arxiv.org/abs/2312.02119" },
  { title: "Bypassing LLM Guardrails",           venue: "arXiv 2025",           authors: "Hackett et al.",        url: "https://arxiv.org/abs/2504.11168" },
  { title: "AutoInject via RL",                  venue: "arXiv 2026",           authors: "Chen et al.",           url: "https://arxiv.org/abs/2602.05746" },
  { title: "Spotlighting Defense",               venue: "arXiv 2024",           authors: "Hines et al. (Microsoft)", url: "https://arxiv.org/abs/2403.14720" },
  { title: "Instruction Hierarchy",              venue: "arXiv 2024",           authors: "OpenAI",                url: "https://arxiv.org/abs/2404.13208" },
];

export function About() {
  const { t } = useLocale();

  const FEATURES = [
    { icon: Target,   title: t("about.multiStrategyEngine"), desc: t("about.multiStrategyDesc") },
    { icon: Shield,   title: t("about.industryScoring"),     desc: t("about.industryScoringDesc") },
    { icon: BarChart3, title: t("about.complianceMapping"),  desc: t("about.complianceMappingDesc") },
    { icon: Zap,      title: t("about.realtimeAnalysis"),    desc: t("about.realtimeAnalysisDesc") },
  ];

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <div className="text-center space-y-4 py-8">
        <div className="flex justify-center">
          <div className="w-16 h-16 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center">
            <Shield className="w-8 h-8 text-indigo-600" />
          </div>
        </div>
        <h1 className="text-3xl font-bold text-gray-900">{t("about.title")}</h1>
        <p className="text-gray-600 max-w-2xl mx-auto">
          {t("about.subtitle")}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {FEATURES.map((f) => (
          <div key={f.title} className="card p-5">
            <f.icon className="w-6 h-6 text-indigo-500 mb-3" />
            <h3 className="text-sm font-semibold text-gray-900 mb-1">{f.title}</h3>
            <p className="text-xs text-gray-600 leading-relaxed">{f.desc}</p>
          </div>
        ))}
      </div>

      <div className="card p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5 text-indigo-500" />
          {t("about.securityFrameworks")}
        </h2>
        <div className="grid grid-cols-4 gap-3">
          {FRAMEWORKS.map((fw) => (
            <div key={fw.name} className="bg-gray-50 border border-gray-100 rounded-lg p-4 text-center">
              <p className="text-sm font-medium text-gray-900">{fw.name}</p>
              <p className="text-xs text-indigo-600 font-mono mt-1">{fw.version}</p>
              <p className="text-xs text-gray-500 mt-1">{fw.items}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-indigo-500" />
          {t("about.researchReferences")}
        </h2>
        <div className="space-y-2">
          {PAPERS.map((p) => (
            <a
              key={p.title}
              href={p.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-4 px-3 py-2 rounded-lg hover:bg-indigo-50 transition-colors group"
            >
              <span className="text-sm text-gray-900 flex-1 group-hover:text-indigo-700 transition-colors flex items-center gap-1.5">
                {p.title}
                <ExternalLink className="w-3 h-3 text-gray-300 group-hover:text-indigo-400 shrink-0" />
              </span>
              <span className="text-xs text-indigo-600 font-mono">{p.venue}</span>
              <span className="text-xs text-gray-500">{p.authors}</span>
            </a>
          ))}
        </div>
      </div>

      <div className="card p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Box className="w-5 h-5 text-indigo-500" />
          {t("about.architecture")}
        </h2>
        <ArchitectureDiagram />
      </div>

      <div className="card p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">{t("about.techStack")}</h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-gray-500 mb-2">{t("about.backend")}</p>
            <div className="flex flex-wrap gap-2">
              {["Python 3.11+", "FastAPI 0.115", "SQLAlchemy 2.0", "OpenAI SDK", "Anthropic SDK", "CVSS v4.0"].map((tech) => (
                <span key={tech} className="px-2 py-1 bg-gray-50 border border-gray-100 rounded text-xs text-gray-700">
                  {tech}
                </span>
              ))}
            </div>
          </div>
          <div>
            <p className="text-gray-500 mb-2">{t("about.frontend")}</p>
            <div className="flex flex-wrap gap-2">
              {["React 19", "TypeScript 5.9", "TailwindCSS 4", "Recharts 3", "Vite 8"].map((tech) => (
                <span key={tech} className="px-2 py-1 bg-gray-50 border border-gray-100 rounded text-xs text-gray-700">
                  {tech}
                </span>
              ))}
            </div>
          </div>
          <div>
            <p className="text-gray-500 mb-2">{t("about.deployment")}</p>
            <div className="flex flex-wrap gap-2">
              {["Docker Compose", "Nginx", "SQLite", "WebSocket"].map((tech) => (
                <span key={tech} className="px-2 py-1 bg-gray-50 border border-gray-100 rounded text-xs text-gray-700">
                  {tech}
                </span>
              ))}
            </div>
          </div>
          <div>
            <p className="text-gray-500 mb-2">{t("about.security")}</p>
            <div className="flex flex-wrap gap-2">
              {[t("about.defaultDenyAuth"), t("about.ssrfProtection"), t("about.wsAuth"), t("about.credSanitization")].map((tech) => (
                <span key={tech} className="px-2 py-1 bg-gray-50 border border-gray-100 rounded text-xs text-gray-700">
                  {tech}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

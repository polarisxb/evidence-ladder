import type { ReactNode } from "react";
import { ArrowDown } from "lucide-react";
import { useLocale } from "../i18n";

function Node({ title, items, children }: { title: string; items: string[]; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3">
      <p className="mb-2 text-xs font-semibold text-gray-900">{title}</p>
      <div className="flex flex-wrap gap-1">
        {items.map((item) => (
          <span key={item} className="rounded-md bg-gray-100 px-2 py-0.5 text-[11px] text-gray-600">{item}</span>
        ))}
      </div>
      {children}
    </div>
  );
}

function Connector({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center gap-1.5 py-2 text-[11px] text-gray-400">
      <ArrowDown className="h-3.5 w-3.5" aria-hidden />
      <span>{label}</span>
    </div>
  );
}

/** Layered system architecture: frontend, the backend's four modules, and what it talks to. */
export function ArchitectureDiagram() {
  const { t } = useLocale();

  return (
    <div>
      <Node title={t("arch.frontend")} items={["React", "TypeScript", "Vite", "Recharts"]} />
      <Connector label="REST · WebSocket" />
      <div className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-3">
        <p className="mb-2.5 text-xs font-semibold text-indigo-900">{t("arch.backend")} · FastAPI</p>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <Node title={t("arch.execution")} items={["Templates", "PAIR · TAP · Crescendo", t("arch.mutations")]} />
          <Node title={t("arch.verdict")} items={["Judge", t("arch.rules"), "Evidence Arbiter", "Quartet"]} />
          <Node title={t("arch.retest")} items={["Retest", "AutoTest", t("arch.probes")]} />
          <Node title={t("arch.storage")} items={["SQLite", "WebSocket", t("arch.reports")]} />
        </div>
      </div>
      <div className="grid gap-x-3 md:grid-cols-2">
        <div>
          <Connector label={t("arch.attackTraffic")} />
          <Node
            title={t("arch.targets")}
            items={[t("arch.openaiCompatible"), t("arch.customHttp"), t("arch.adapters"), "MailBot · ShopBot · FinanceBot"]}
          />
        </div>
        <div>
          <Connector label={t("arch.modelCalls")} />
          <Node title={t("arch.models")} items={["DeepSeek", "Qwen", "OpenAI", "Claude"]} />
        </div>
      </div>
    </div>
  );
}

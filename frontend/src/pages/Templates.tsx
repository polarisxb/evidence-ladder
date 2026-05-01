import { useEffect, useState } from "react";
import { Layers, ChevronDown, ChevronUp } from "lucide-react";
import { request } from "../api/client";
import { useToast } from "../components/Toast";
import { useLocale } from "../i18n";

interface Category {
  category: string;
  category_name: string;
  owasp_id: string;
  description: string;
  template_count: number;
}

export function Templates() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [expandedTemplate, setExpandedTemplate] = useState<string | null>(null);
  const [templates, setTemplates] = useState<Record<string, unknown[]>>({});
  const { toast } = useToast();
  const { t } = useLocale();

  useEffect(() => {
    request<{ data: Category[] }>("/templates")
      .then((res) => setCategories(res.data))
      .catch((err) => toast("error", `Failed to load templates: ${err.message}`));
  }, []);

  async function toggleCategory(cat: string) {
    if (expanded === cat) {
      setExpanded(null);
      return;
    }
    setExpanded(cat);
    if (!templates[cat]) {
      const res = await request<{ data: unknown[] }>(`/templates/${cat}`);
      setTemplates((prev) => ({ ...prev, [cat]: res.data }));
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
        <Layers className="w-6 h-6 text-indigo-500" />
        {t("templates.title")}
      </h1>

      <div className="space-y-3">
        {categories.map((cat) => (
          <div key={cat.category} className="card overflow-hidden">
            <button
              onClick={() => toggleCategory(cat.category)}
              className="w-full flex items-center gap-4 p-4 text-left hover:bg-gray-50 transition-colors"
            >
              <div className="flex-1">
                <p className="font-medium text-gray-900">{cat.category_name}</p>
                <p className="text-xs text-gray-500">{cat.description}</p>
              </div>
              <span className="text-xs text-indigo-600 font-mono">{cat.owasp_id}</span>
              <span className="text-xs text-gray-500">{cat.template_count} {t("templates.templates")}</span>
              {expanded === cat.category ? (
                <ChevronUp className="w-4 h-4 text-gray-400" />
              ) : (
                <ChevronDown className="w-4 h-4 text-gray-400" />
              )}
            </button>
            {expanded === cat.category && templates[cat.category] && (
              <div className="border-t border-gray-100 divide-y divide-gray-100">
                {(
                  templates[cat.category] as Array<{
                    id: string;
                    name: string;
                    technique: string;
                    severity: string;
                    payloads?: Array<{ text: string; language: string; variant: string }>;
                  }>
                ).map((tpl) => (
                  <div key={tpl.id}>
                    <button
                      onClick={() => setExpandedTemplate(expandedTemplate === tpl.id ? null : tpl.id)}
                      className="w-full px-4 py-3 flex items-center gap-3 hover:bg-gray-50 transition-colors text-left"
                    >
                      <span className="text-xs text-gray-500 font-mono w-16">{tpl.id}</span>
                      <span className="text-sm text-gray-700 flex-1">{tpl.name}</span>
                      <span className="text-xs text-gray-500">{tpl.technique}</span>
                      <span className="text-xs text-gray-400">{tpl.payloads?.length ?? 0} {t("templates.payloads")}</span>
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${
                          tpl.severity === "critical"
                            ? "bg-red-50 text-red-700"
                            : tpl.severity === "high"
                              ? "bg-orange-50 text-orange-700"
                              : tpl.severity === "medium"
                                ? "bg-amber-50 text-amber-800"
                                : "bg-green-50 text-green-700"
                        }`}
                      >
                        {tpl.severity}
                      </span>
                    </button>
                    {expandedTemplate === tpl.id && tpl.payloads && (
                      <div className="px-4 pb-3 space-y-2">
                        {tpl.payloads.map((p, i) => (
                          <div key={i} className="bg-gray-50 border border-gray-100 rounded-lg p-3">
                            <div className="flex items-center gap-2 mb-2">
                              <span className="text-xs text-gray-500 font-mono">{p.variant}</span>
                              <span className="text-xs text-gray-400">{p.language}</span>
                            </div>
                            <pre className="text-xs text-gray-700 font-mono whitespace-pre-wrap break-words">
                              {p.text}
                            </pre>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {categories.length === 0 && (
          <div className="text-center text-gray-500 py-12">{t("templates.loading")}</div>
        )}
      </div>
    </div>
  );
}

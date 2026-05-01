import { useEffect, useState } from "react";
import { Bot, Edit2, FlaskConical, Info, Key, Loader2, Plus, RefreshCw, Save, Settings as SettingsIcon, Trash2, XCircle, Zap } from "lucide-react";
import { request } from "../api/client";
import {
  createModelProvider,
  deleteModelProvider,
  fetchProviderModels,
  listModelProviders,
  testModelProvider,
  updateModelProvider,
} from "../api/modelProviders";
import { useToast } from "../components/Toast";
import { ProviderIconSmall } from "../components/ProviderIcon";
import { useLocale } from "../i18n";
import type { ModelProvider, ProviderType } from "../types";
import { PROVIDER_BASE_URLS } from "../types";

interface SettingsData {
  openai_api_key_set: boolean;
  openai_base_url: string | null;
  openai_model: string;
  openai_mini_model: string;
  database_url: string;
  debug: boolean;
}

function ActiveConfigCard({ settings }: { settings: SettingsData }) {
  const [providers, setProviders] = useState<ModelProvider[]>([]);

  useEffect(() => {
    listModelProviders().then(setProviders).catch(() => {});
  }, []);

  const judge = providers.find((p) => p.is_judge_default);
  const generation = providers.find((p) => p.is_generation_default);
  const envBase = settings.openai_base_url ?? "(default)";

  // Provider 级不再保存 judge_model / mini_model —— 具体模型由新建扫描时选择。
  // 这张卡只说明"默认路由到哪个供应商"和 .env 兜底使用的模型名。
  const rows: Array<{ role: string; icon: React.ReactNode; source: string; model: string; color: string }> = [
    {
      role: "裁判 Judge",
      icon: <FlaskConical className="w-4 h-4 text-indigo-500" />,
      source: judge ? `默认供应商「${judge.name}」` : ".env 兜底",
      model: judge ? "扫描时选择" : settings.openai_model,
      color: judge ? "border-indigo-200 bg-indigo-50/50" : "border-gray-200 bg-gray-50",
    },
    {
      role: "生成 / 攻击",
      icon: <Zap className="w-4 h-4 text-amber-500" />,
      source: generation ? `默认供应商「${generation.name}」` : ".env 兜底",
      model: generation ? "扫描时选择" : settings.openai_mini_model,
      color: generation ? "border-amber-200 bg-amber-50/50" : "border-gray-200 bg-gray-50",
    },
  ];

  return (
    <div className="card p-5 space-y-3">
      <div className="flex items-center gap-2">
        <Info className="w-5 h-5 text-blue-500" />
        <h2 className="text-lg font-semibold text-gray-900">当前生效配置</h2>
        <span className="text-xs text-gray-400 ml-auto">API: {envBase}</span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        {rows.map((r) => (
          <div key={r.role} className={`rounded-lg border p-3 ${r.color}`}>
            <div className="flex items-center gap-2 mb-1.5">
              {r.icon}
              <span className="text-xs font-semibold text-gray-700">{r.role}</span>
            </div>
            <p className="text-sm font-medium text-gray-900 font-mono">{r.model}</p>
            <p className="text-xs text-gray-500 mt-0.5">{r.source}</p>
          </div>
        ))}
      </div>

      <p className="text-xs text-gray-400">
        新建扫描时可为裁判和攻击生成器选择不同的供应商。不选则使用 .env 兜底配置。
      </p>
    </div>
  );
}

// ── Provider type display config ─────────────────────────────────────────────
const PROVIDER_LABELS: Record<string, string> = {
  openai:      "OpenAI",
  deepseek:    "DeepSeek",
  glm:         "GLM（智谱）",
  minimax:     "MiniMax",
  gemini:      "Gemini",
  qwen:        "Qwen（通义千问）",
  claude:      "Claude",
  nvidia:      "NVIDIA NIM",
  mistral:     "Mistral AI",
  groq:        "Groq",
  moonshot:    "Moonshot（月之暗面）",
  doubao:      "豆包（火山引擎）",
  yi:          "Yi（零一万物）",
  baichuan:    "百川智能",
  stepfun:     "阶跃星辰",
  siliconflow: "硅基流动",
  xai:         "xAI (Grok)",
  together:    "Together AI",
  custom:      "自定义",
};
const PROVIDER_COLORS: Record<string, string> = {
  openai:      "bg-emerald-50 text-emerald-700 border-emerald-200",
  deepseek:    "bg-sky-50 text-sky-700 border-sky-200",
  glm:         "bg-violet-50 text-violet-700 border-violet-200",
  minimax:     "bg-rose-50 text-rose-700 border-rose-200",
  gemini:      "bg-amber-50 text-amber-800 border-amber-200",
  qwen:        "bg-orange-50 text-orange-700 border-orange-200",
  claude:      "bg-amber-50 text-amber-900 border-amber-300",
  nvidia:      "bg-lime-50 text-lime-800 border-lime-300",
  mistral:     "bg-orange-50 text-orange-800 border-orange-300",
  groq:        "bg-slate-50 text-slate-700 border-slate-300",
  moonshot:    "bg-indigo-50 text-indigo-700 border-indigo-200",
  doubao:      "bg-cyan-50 text-cyan-700 border-cyan-200",
  yi:          "bg-purple-50 text-purple-700 border-purple-200",
  baichuan:    "bg-blue-50 text-blue-700 border-blue-200",
  stepfun:     "bg-teal-50 text-teal-700 border-teal-200",
  siliconflow: "bg-sky-50 text-sky-800 border-sky-300",
  xai:         "bg-zinc-50 text-zinc-800 border-zinc-300",
  together:    "bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200",
  custom:      "bg-gray-100 text-gray-700 border-gray-200",
};

// ── Blank form state ───────────────────────────────────────────────────────────
// Provider form intentionally omits judge_model / mini_model. Those are
// chosen at scan-creation time in NewScan.tsx, not baked into the
// provider record. Keeping them out of the form avoids two sources of
// truth and lets the same provider be reused across scans with
// different models.
interface KeyEntry {
  index: number;   // -1 = new;  >= 0 = existing (position in DB array)
  label: string;
  key: string;     // actual key for new entries; empty = keep existing
  maskedKey: string; // display-only for existing keys
}

function blankForm() {
  return {
    name: "",
    provider_type: "custom" as ProviderType,
    apiKeys: [{ index: -1, label: "", key: "", maskedKey: "" }] as KeyEntry[],
    base_url: "",
    enabled: true,
  };
}

// ── ModelProviders card ────────────────────────────────────────────────────────
function ModelProvidersCard() {
  const { t } = useLocale();
  const { toast } = useToast();
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(blankForm());
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { connected: boolean; model?: string; error?: string }>>({});
  const [fetchingModels, setFetchingModels] = useState(false);
  const [availableModels, setAvailableModels] = useState<string[]>([]);


  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      setProviders(await listModelProviders());
    } catch (err) {
      toast("error", `${t("modelProviders.failedToLoad")}: ${err instanceof Error ? err.message : err}`);
    } finally {
      setLoading(false);
    }
  }

  function startNew() {
    setEditingId(null);
    setForm(blankForm());
    setAvailableModels([]);
    setExpanded(true);
  }

  function startEdit(p: ModelProvider) {
    setEditingId(p.id);
    setForm({
      name: p.name,
      provider_type: (p.provider_type as ProviderType) || "custom",
      apiKeys: p.api_keys.length > 0
        ? p.api_keys.map((k) => ({ index: k.index, label: k.label, key: "", maskedKey: k.masked_key }))
        : [{ index: -1, label: "", key: "", maskedKey: "" }],
      base_url: p.base_url ?? "",
      enabled: p.enabled,
    });
    setAvailableModels([]);
    setExpanded(true);
  }

  function handleProviderTypeChange(pt: ProviderType) {
    const preset = PROVIDER_BASE_URLS[pt] ?? "";
    setForm((f) => ({ ...f, provider_type: pt, base_url: preset }));
    setAvailableModels([]);
  }

  function addKeyRow() {
    setForm((f) => ({
      ...f,
      apiKeys: [...f.apiKeys, { index: -1, label: "", key: "", maskedKey: "" }],
    }));
  }

  function removeKeyRow(idx: number) {
    setForm((f) => {
      const next = f.apiKeys.filter((_, i) => i !== idx);
      return { ...f, apiKeys: next.length > 0 ? next : [{ index: -1, label: "", key: "", maskedKey: "" }] };
    });
  }

  function updateKeyRow(idx: number, field: "label" | "key", value: string) {
    setForm((f) => ({
      ...f,
      apiKeys: f.apiKeys.map((e, i) => (i === idx ? { ...e, [field]: value } : e)),
    }));
  }

  const hasAnyKey = form.apiKeys.some((e) => e.key.trim() || e.maskedKey);

  async function handleFetchModels() {
    const firstNewKey = form.apiKeys.find((e) => e.key.trim())?.key;
    if (!firstNewKey && !editingId) { toast("warning", t("modelProviders.apiKey")); return; }
    setFetchingModels(true);
    try {
      const models = await fetchProviderModels({
        api_key: firstNewKey || undefined,
        base_url: form.base_url || undefined,
        provider_type: form.provider_type,
        provider_id: editingId && !firstNewKey ? editingId : undefined,
      });
      setAvailableModels(models);
      toast("success", t("modelProviders.fetchSuccess", { n: models.length }));
    } catch (err) {
      toast("error", `${t("modelProviders.fetchFailed")}: ${err instanceof Error ? err.message : err}`);
    } finally {
      setFetchingModels(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    try {
      const apiKeysPayload = form.apiKeys
        .filter((e) => e.key.trim() || e.index >= 0)
        .map((e) => ({ index: e.index, label: e.label, key: e.key }));

      if (editingId) {
        await updateModelProvider(editingId, {
          name: form.name,
          provider_type: form.provider_type,
          api_keys: apiKeysPayload,
          base_url: form.base_url || null,
          enabled: form.enabled,
        });
      } else {
        await createModelProvider({
          name: form.name,
          provider_type: form.provider_type,
          api_keys: apiKeysPayload,
          base_url: form.base_url || null,
          enabled: form.enabled,
        });
      }
      toast("success", t("modelProviders.saveSuccess"));
      setExpanded(false);
      await load();
    } catch (err) {
      toast("error", `${t("modelProviders.failedToSave")}: ${err instanceof Error ? err.message : err}`);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm(t("modelProviders.confirmDelete"))) return;
    try {
      await deleteModelProvider(id);
      toast("success", t("modelProviders.deleteSuccess"));
      await load();
    } catch (err) {
      toast("error", `${t("modelProviders.failedToDelete")}: ${err instanceof Error ? err.message : err}`);
    }
  }

  async function handleTest(id: string) {
    setTesting(id);
    try {
      const res = await testModelProvider(id);
      setTestResults((prev) => ({ ...prev, [id]: res }));
      if (res.connected) toast("success", `${t("modelProviders.testSuccess")} — ${res.model}`);
      else toast("error", `${t("modelProviders.testFailed")}: ${res.error}`);
    } catch (err) {
      toast("error", `${t("modelProviders.testFailed")}: ${err instanceof Error ? err.message : err}`);
    } finally {
      setTesting(null);
    }
  }


  const inputCls = "w-full px-3 py-2 bg-white border border-gray-200 rounded-lg text-gray-900 placeholder:text-gray-400 focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900/10 text-sm";
  const selectCls = "w-full px-3 py-2 bg-white border border-gray-200 rounded-lg text-gray-900 text-sm focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900/10";

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <div className="p-5 border-b border-gray-100">
        <div className="flex items-center gap-3">
          <Bot className="w-5 h-5 text-indigo-500" />
          <div className="flex-1">
            <h2 className="text-lg font-semibold text-gray-900">{t("modelProviders.title")}</h2>
            <p className="text-xs text-gray-500 mt-0.5">{t("modelProviders.subtitle")}</p>
          </div>
          <button
            type="button"
            onClick={startNew}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-900 text-white text-xs hover:bg-gray-800 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            {t("modelProviders.newProvider")}
          </button>
        </div>

      </div>

      {/* Provider list */}
      {loading ? (
        <div className="p-6 flex items-center justify-center gap-2 text-gray-400">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">{t("common.loading")}</span>
        </div>
      ) : providers.length === 0 && !expanded ? (
        <p className="p-6 text-sm text-gray-500 text-center">{t("modelProviders.noProviders")}</p>
      ) : (
        <div className="divide-y divide-gray-100">
          {providers.map((p) => (
            <div key={p.id} className="px-5 py-3 flex items-center gap-3 hover:bg-gray-50/60">
              {/* Provider icon */}
              <ProviderIconSmall type={p.provider_type} />

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-gray-900 truncate">{p.name}</p>
                  {p.api_key_count > 0 && (
                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 text-[10px] font-semibold shrink-0">
                      <Key className="w-2.5 h-2.5" />
                      {p.api_key_count} {p.api_key_count === 1 ? "key" : "keys"}
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-500 font-mono truncate">
                  {p.base_url || "(default endpoint)"}
                </p>
              </div>


              {/* Test status */}
              {testResults[p.id] && (
                <span className={`text-[11px] shrink-0 ${testResults[p.id].connected ? "text-emerald-600" : "text-rose-600"}`}>
                  {testResults[p.id].connected ? "✓" : "✗"}
                </span>
              )}

              {/* Actions */}
              <div className="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  disabled={testing === p.id}
                  onClick={() => handleTest(p.id)}
                  className="p-1.5 text-gray-400 hover:text-indigo-600 transition-colors rounded"
                  title={t("modelProviders.testConnection")}
                >
                  {testing === p.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FlaskConical className="w-3.5 h-3.5" />}
                </button>
                <button
                  type="button"
                  onClick={() => startEdit(p)}
                  className="p-1.5 text-gray-400 hover:text-gray-700 transition-colors rounded"
                  title={t("modelProviders.editProvider")}
                >
                  <Edit2 className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(p.id)}
                  className="p-1.5 text-gray-400 hover:text-red-600 transition-colors rounded"
                  title={t("modelProviders.deleteProvider")}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create/Edit form */}
      {expanded && (
        <div className="border-t border-gray-100 bg-gray-50/50 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-800">
              {editingId ? t("modelProviders.editProvider") : t("modelProviders.newProvider")}
            </h3>
            <button type="button" onClick={() => setExpanded(false)} className="text-gray-400 hover:text-gray-700">
              <XCircle className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Name */}
            <div>
              <label className="block text-xs text-gray-600 mb-1">{t("common.name")}</label>
              <input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder={"e.g. DeepSeek Pro"}
                className={inputCls}
              />
            </div>

            {/* Provider type */}
            <div>
              <label className="block text-xs text-gray-600 mb-1">{t("modelProviders.providerType")}</label>
              <div className="flex items-center gap-2">
                <ProviderIconSmall type={form.provider_type} />
                <select
                  value={form.provider_type}
                  onChange={(e) => handleProviderTypeChange(e.target.value as ProviderType)}
                  className={selectCls}
                >
                  {Object.entries(PROVIDER_LABELS).map(([v, label]) => (
                    <option key={v} value={v}>{label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* API Keys (structured multi-key) */}
            <div className="col-span-2">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <label className="block text-xs text-gray-600 font-medium">{t("modelProviders.apiKey")}</label>
                  <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 text-[10px] font-semibold">
                    <Key className="w-2.5 h-2.5" />
                    {form.apiKeys.filter((e) => e.key.trim() || e.maskedKey).length} keys
                  </span>
                </div>
                <button
                  type="button"
                  onClick={addKeyRow}
                  className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] text-indigo-700 bg-indigo-50 hover:bg-indigo-100 transition-colors"
                >
                  <Plus className="w-3 h-3" />
                  {t("modelProviders.addKey")}
                </button>
              </div>
              <div className="space-y-2">
                {form.apiKeys.map((entry, idx) => (
                  <div key={idx} className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white p-2">
                    <input
                      value={entry.label}
                      onChange={(e) => updateKeyRow(idx, "label", e.target.value)}
                      placeholder={t("modelProviders.keyLabel")}
                      className="w-32 shrink-0 px-2 py-1.5 bg-gray-50 border border-gray-100 rounded text-xs text-gray-800 placeholder:text-gray-400 focus:border-gray-900 focus:outline-none"
                    />
                    {entry.maskedKey && !entry.key ? (
                      <div className="flex-1 px-2 py-1.5 bg-gray-50 border border-gray-100 rounded text-xs text-gray-500 font-mono truncate">
                        {entry.maskedKey}
                      </div>
                    ) : (
                      <input
                        value={entry.key}
                        onChange={(e) => updateKeyRow(idx, "key", e.target.value)}
                        placeholder={entry.maskedKey ? `${entry.maskedKey}  (${t("modelProviders.keyKeepExisting")})` : t("modelProviders.apiKeyPlaceholder")}
                        className="flex-1 px-2 py-1.5 bg-white border border-gray-100 rounded text-xs text-gray-900 font-mono placeholder:text-gray-400 focus:border-gray-900 focus:outline-none"
                        spellCheck={false}
                      />
                    )}
                    {entry.maskedKey && !entry.key && (
                      <button
                        type="button"
                        onClick={() => updateKeyRow(idx, "key", " ")}
                        title={t("modelProviders.keyReplace")}
                        className="p-1 text-gray-400 hover:text-indigo-600 transition-colors rounded shrink-0"
                      >
                        <Edit2 className="w-3 h-3" />
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => removeKeyRow(idx)}
                      className="p-1 text-gray-400 hover:text-red-500 transition-colors rounded shrink-0"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
              <p className="text-[11px] text-gray-400 mt-1.5">{t("modelProviders.multiKeyDescription")}</p>
            </div>

            {/* Base URL */}
            <div>
              <label className="block text-xs text-gray-600 mb-1">
                {t("modelProviders.baseUrl")}
                <span className="ml-1 text-gray-400 font-normal">{t("modelProviders.baseUrlAuto")}</span>
              </label>
              <input
                value={form.base_url}
                onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))}
                placeholder={PROVIDER_BASE_URLS[form.provider_type] || "https://your-api.com/v1"}
                className={`${inputCls} font-mono text-xs`}
              />
            </div>
          </div>

          {/* Fetch models row */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              disabled={fetchingModels || (!hasAnyKey && !editingId)}
              onClick={handleFetchModels}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-indigo-200 bg-indigo-50 text-indigo-800 text-xs hover:bg-indigo-100 disabled:opacity-50 transition-colors"
            >
              {fetchingModels ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
              {fetchingModels ? t("modelProviders.fetching") : t("modelProviders.fetchModels")}
            </button>
            {availableModels.length > 0 && (
              <span className="text-xs text-emerald-700">
                {t("modelProviders.fetchSuccess", { n: availableModels.length })}
              </span>
            )}
          </div>

          {availableModels.length > 0 && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-3">
              <p className="text-xs text-emerald-700 font-medium mb-1">该供应商支持的模型</p>
              <p className="text-xs text-emerald-600 font-mono">
                {availableModels.slice(0, 10).join("、")}{availableModels.length > 10 ? ` 等 ${availableModels.length} 个` : ""}
              </p>
              <p className="text-xs text-emerald-500 mt-1">新建扫描时可选择具体使用哪个模型。</p>
            </div>
          )}

          {/* Enabled + actions */}
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm((f) => ({ ...f, enabled: e.target.checked }))}
                className="accent-gray-900"
              />
              {t("modelProviders.enabled")}
            </label>
            <div className="ml-auto flex gap-2">
              <button
                type="button"
                onClick={() => setExpanded(false)}
                className="px-4 py-1.5 rounded-lg border border-gray-200 text-xs text-gray-700 hover:bg-gray-100 transition-colors"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                disabled={saving || !form.name || (!hasAnyKey && !editingId)}
                onClick={handleSave}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-gray-900 text-white text-xs hover:bg-gray-800 disabled:opacity-50 transition-colors"
              >
                {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                {saving ? t("common.saving") : t("common.save")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function Settings() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const { toast } = useToast();
  const { t } = useLocale();

  useEffect(() => {
    request<{ data: SettingsData }>("/settings")
      .then((res) => setSettings(res.data))
      .catch((err) => toast("error", `Failed to load settings: ${err.message}`));
  }, []);

  if (!settings) return <div className="text-center text-gray-500 py-12">{t("common.loading")}</div>;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
        <SettingsIcon className="w-6 h-6 text-indigo-500" />
        {t("settings.title")}
      </h1>

      <ActiveConfigCard settings={settings} />

      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700 space-y-2">
        <p className="font-semibold text-slate-900">配置层级说明</p>
        <div className="grid grid-cols-3 gap-3 text-xs">
          <div className="bg-white rounded-lg border border-slate-200 p-2.5">
            <p className="font-medium text-slate-800 mb-1">1. .env 文件</p>
            <p className="text-slate-500">项目根目录 .env 是基础兜底配置。改完需重启服务生效。</p>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-2.5">
            <p className="font-medium text-slate-800 mb-1">2. 供应商管理</p>
            <p className="text-slate-500">下方供应商列表存储各 AI 服务的 API Key 和模型配置。</p>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-2.5">
            <p className="font-medium text-slate-800 mb-1">3. 新建扫描</p>
            <p className="text-slate-500">扫描时为目标、裁判、攻击器各选一个供应商。不选则用 .env 兜底。</p>
          </div>
        </div>
      </div>

      <ModelProvidersCard />

      <div className="card p-6 space-y-3">
        <h2 className="text-lg font-semibold text-gray-900">{t("settings.systemInfo")}</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="flex justify-between p-2 rounded-lg bg-gray-50 border border-gray-100">
            <span className="text-gray-500">{t("settings.database")}</span>
            <span className="text-gray-700 font-mono text-xs truncate max-w-[60%]">{settings.database_url}</span>
          </div>
          <div className="flex justify-between p-2 rounded-lg bg-gray-50 border border-gray-100">
            <span className="text-gray-500">{t("settings.debugMode")}</span>
            <span className={`font-mono text-xs ${settings.debug ? "text-amber-700" : "text-gray-500"}`}>
              {settings.debug ? t("settings.on") : t("settings.off")}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

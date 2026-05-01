import { useEffect, useMemo, useState } from "react";
import { FlaskConical, Play, Plus, Save, Server, TestTube2 } from "lucide-react";
import { createAdapter, getAdapters, testAdapter, testAdapterProbe, updateAdapter } from "../api/adapters";
import { useToast } from "../components/Toast";
import { useLocale } from "../i18n";
import type { Adapter, AdapterConfig, AdapterProbeTestResult, AdapterTestResult } from "../types";

interface AdapterFormState {
  id: string | null;
  name: string;
  description: string;
  transport: "http_json" | "openai_chat";
  base_url: string;
  enabled: boolean;
  authText: string;
  sessionText: string;
  invokeText: string;
  extractText: string;
  probeText: string;
}

function prettyJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function defaultInvoke(transport: "http_json" | "openai_chat"): Record<string, unknown> {
  if (transport === "openai_chat") {
    return {
      method: "POST",
      path: "/chat/completions",
      model: "gpt-4o-mini",
    };
  }
  return {
    method: "POST",
    path: "/",
    headers: {},
    body_template: {
      message: "{{input.prompt}}",
      history: "{{input.history}}",
    },
  };
}

function defaultExtract(transport: "http_json" | "openai_chat"): Record<string, unknown> {
  if (transport === "openai_chat") {
    return {
      mode: "json_paths",
      text_path: "$.choices[0].message.content",
      error_path: "$.error.message",
      tool_calls_path: "$.choices[0].message.tool_calls",
    };
  }
  return {
    mode: "json_paths",
    text_path: "$.data.reply",
    error_path: "$.error.message",
  };
}

function makeBlankForm(transport: "http_json" | "openai_chat" = "http_json"): AdapterFormState {
  return {
    id: null,
    name: "",
    description: "",
    transport,
    base_url: "",
    enabled: true,
    authText: prettyJson({ type: "none" }),
    sessionText: prettyJson({ mode: "per_variant_isolated" }),
    invokeText: prettyJson(defaultInvoke(transport)),
    extractText: prettyJson(defaultExtract(transport)),
    probeText: prettyJson({
      enabled: true,
      steps: [
        {
          name: "check_effect",
          method: "GET",
          path: "/",
        },
      ],
      assertions: [
        {
          type: "status_code_is",
          step: "check_effect",
          status_code: 200,
        },
      ],
    }),
  };
}

function fromAdapter(adapter: Adapter): AdapterFormState {
  return {
    id: adapter.id,
    name: adapter.name,
    description: adapter.description ?? "",
    transport: adapter.transport,
    base_url: adapter.base_url,
    enabled: adapter.enabled,
    authText: prettyJson(adapter.auth_config),
    sessionText: prettyJson(adapter.session_config ?? { mode: "per_variant_isolated" }),
    invokeText: prettyJson(adapter.invoke_config),
    extractText: prettyJson(adapter.response_extract),
    probeText: prettyJson(
      adapter.probe_config ?? {
        enabled: true,
        steps: [],
        assertions: [],
      },
    ),
  };
}

function parseJson(label: string, raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(`${label} must be valid JSON: ${error instanceof Error ? error.message : error}`);
  }
}

function buildAdapterPayload(form: AdapterFormState): AdapterConfig {
  return {
    name: form.name.trim(),
    description: form.description.trim() || null,
    mode: "direct_http_adapter",
    transport: form.transport,
    base_url: form.base_url.trim(),
    enabled: form.enabled,
    auth_config: parseJson("Auth config", form.authText) as AdapterConfig["auth_config"],
    session_config: parseJson("Session config", form.sessionText) as AdapterConfig["session_config"],
    invoke_config: parseJson("Invoke config", form.invokeText) as AdapterConfig["invoke_config"],
    response_extract: parseJson("Response extract", form.extractText) as AdapterConfig["response_extract"],
    probe_config: parseJson("Probe config", form.probeText) as AdapterConfig["probe_config"],
  };
}

function TextareaField(props: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  hint?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm text-gray-600">{props.label}</label>
      <textarea
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
        rows={props.rows ?? 8}
        className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm font-mono text-gray-900 placeholder:text-gray-400 focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900/10"
      />
      {props.hint && <p className="text-xs text-gray-500">{props.hint}</p>}
    </div>
  );
}

export function Adapters() {
  const { toast } = useToast();
  const { t } = useLocale();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [adapters, setAdapters] = useState<Adapter[]>([]);
  const [form, setForm] = useState<AdapterFormState>(() => makeBlankForm());
  const [testPrompt, setTestPrompt] = useState("Hello from adapter test");
  const [testHistoryText, setTestHistoryText] = useState("[]");
  const [testRuntimeVarsText, setTestRuntimeVarsText] = useState("{\n  \"tenant_id\": \"demo-tenant\",\n  \"user_id\": \"demo-user\"\n}");
  const [testResult, setTestResult] = useState<AdapterTestResult | null>(null);
  const [probeTesting, setProbeTesting] = useState(false);
  const [probeSessionId, setProbeSessionId] = useState("demo-session");
  const [probeResult, setProbeResult] = useState<AdapterProbeTestResult | null>(null);

  async function loadAdapters() {
    setLoading(true);
    try {
      const rows = await getAdapters();
      setAdapters(rows);
      if (rows.length > 0 && !form.id) {
        setForm(fromAdapter(rows[0]));
      }
    } catch (error) {
      toast("error", `${t("adapters.failedToLoad")}: ${error instanceof Error ? error.message : error}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAdapters();
  }, []);

  const selectedAdapter = useMemo(
    () => adapters.find((adapter) => adapter.id === form.id) ?? null,
    [adapters, form.id],
  );

  function handleTransportChange(nextTransport: "http_json" | "openai_chat") {
    setForm((prev) => ({
      ...prev,
      transport: nextTransport,
      invokeText: prev.id ? prev.invokeText : prettyJson(defaultInvoke(nextTransport)),
      extractText: prev.id ? prev.extractText : prettyJson(defaultExtract(nextTransport)),
    }));
  }

  async function handleSave() {
    let payload: AdapterConfig;
    try {
      payload = buildAdapterPayload(form);
    } catch (error) {
      toast("error", error instanceof Error ? error.message : "Invalid adapter JSON");
      return;
    }

    setSaving(true);
    try {
      const saved = form.id
        ? await updateAdapter(form.id, payload)
        : await createAdapter(payload);
      toast("success", t("adapters.saveSuccess"));
      await loadAdapters();
      setForm(fromAdapter(saved));
    } catch (error) {
      toast("error", `${t("adapters.failedToSave")}: ${error instanceof Error ? error.message : error}`);
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    let payload: AdapterConfig;
    let history: Array<Record<string, unknown>>;
    let runtimeVars: Record<string, unknown>;
    try {
      payload = buildAdapterPayload(form);
      history = parseJson("Test history", testHistoryText) as Array<Record<string, unknown>>;
      runtimeVars = parseJson("Runtime vars", testRuntimeVarsText) as Record<string, unknown>;
    } catch (error) {
      toast("error", error instanceof Error ? error.message : "Invalid test input");
      return;
    }

    setTesting(true);
    try {
      const result = await testAdapter({
        adapter: payload,
        prompt: testPrompt,
        history,
        runtime_vars: runtimeVars,
        variant_type: "attack",
      });
      setTestResult(result);
      toast("success", t("adapters.testSuccess"));
    } catch (error) {
      toast("error", `${t("adapters.failedToTest")}: ${error instanceof Error ? error.message : error}`);
    } finally {
      setTesting(false);
    }
  }

  async function handleProbeTest() {
    let payload: AdapterConfig;
    let runtimeVars: Record<string, unknown>;
    try {
      payload = buildAdapterPayload(form);
      runtimeVars = parseJson("Runtime vars", testRuntimeVarsText) as Record<string, unknown>;
    } catch (error) {
      toast("error", error instanceof Error ? error.message : "Invalid probe input");
      return;
    }

    setProbeTesting(true);
    try {
      const result = await testAdapterProbe({
        adapter: payload,
        runtime_vars: runtimeVars,
        session_id: probeSessionId.trim() || null,
        variant_type: "attack",
      });
      setProbeResult(result);
      toast("success", t("adapters.testProbeSuccess"));
    } catch (error) {
      toast("error", `${t("adapters.failedToTest")}: ${error instanceof Error ? error.message : error}`);
    } finally {
      setProbeTesting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t("adapters.title")}</h1>
          <p className="text-sm text-gray-500 mt-1">{t("adapters.subtitle")}</p>
        </div>
        <button
          type="button"
          onClick={() => {
            setForm(makeBlankForm());
            setTestResult(null);
            setProbeResult(null);
          }}
          className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm text-gray-800 hover:border-gray-400 transition-colors"
        >
          <Plus className="w-4 h-4" />
          {t("adapters.newAdapter")}
        </button>
      </div>

      <div className="grid grid-cols-[320px_minmax(0,1fr)] gap-6">
        <div className="card overflow-hidden">
          <div className="border-b border-gray-100 px-4 py-3 flex items-center gap-2">
            <Server className="w-4 h-4 text-gray-500" />
            <h2 className="text-sm font-semibold text-gray-900">{t("adapters.title")}</h2>
          </div>
          <div className="divide-y divide-gray-100">
            {loading ? (
              <div className="p-4 text-sm text-gray-500">{t("common.loading")}</div>
            ) : adapters.length === 0 ? (
              <div className="p-4 text-sm text-gray-500">{t("adapters.noAdapters")}</div>
            ) : (
              adapters.map((adapter) => (
                <button
                  key={adapter.id}
                  type="button"
                    onClick={() => {
                      setForm(fromAdapter(adapter));
                      setTestResult(null);
                      setProbeResult(null);
                    }}
                  className={`w-full text-left px-4 py-3 transition-colors ${
                    form.id === adapter.id ? "bg-gray-100" : "hover:bg-gray-50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{adapter.name}</p>
                      <p className="text-xs text-gray-500 font-mono truncate">{adapter.base_url}</p>
                    </div>
                    <span className={`text-[11px] px-2 py-0.5 rounded border ${adapter.enabled ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-gray-100 text-gray-600 border-gray-200"}`}>
                      {adapter.transport}
                    </span>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className="card p-6 space-y-5">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">
                  {selectedAdapter ? `${t("adapters.editAdapter")}: ${selectedAdapter.name}` : t("adapters.newAdapter")}
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  Probe config now lives on the adapter. Keep using `secret_ref` for credentials.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void handleTest()}
                  disabled={testing}
                  className="inline-flex items-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm text-indigo-900 hover:bg-indigo-100 disabled:opacity-60 transition-colors"
                >
                  <Play className="w-4 h-4" />
                  {testing ? t("common.testing") : t("adapters.testAdapter")}
                </button>
                <button
                  type="button"
                  onClick={() => void handleSave()}
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-xl bg-gray-900 px-4 py-2 text-sm text-white hover:bg-gray-800 disabled:opacity-60 transition-colors"
                >
                  <Save className="w-4 h-4" />
                  {saving ? t("common.saving") : form.id ? t("common.save") : t("adapters.newAdapter")}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900/10"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">Transport</label>
                <select
                  value={form.transport}
                  onChange={(event) => handleTransportChange(event.target.value as AdapterFormState["transport"])}
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900/10"
                >
                  <option value="http_json">http_json</option>
                  <option value="openai_chat">openai_chat</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm text-gray-600 mb-1">Description</label>
              <input
                type="text"
                value={form.description}
                onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900/10"
              />
            </div>

            <div className="grid grid-cols-[minmax(0,1fr)_180px] gap-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">Base URL</label>
                <input
                  type="text"
                  value={form.base_url}
                  onChange={(event) => setForm((prev) => ({ ...prev, base_url: event.target.value }))}
                  placeholder="https://api.example.com"
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm font-mono text-gray-900 focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900/10"
                />
              </div>
              <label className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm text-gray-800">
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(event) => setForm((prev) => ({ ...prev, enabled: event.target.checked }))}
                  className="accent-gray-900"
                />
                Enabled
              </label>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <TextareaField
                label={t("adapters.authConfig")}
                value={form.authText}
                onChange={(value) => setForm((prev) => ({ ...prev, authText: value }))}
                hint='Use `secret_ref`, not plaintext secrets. Example: { "type": "bearer", "secret_ref": "env:CRM_TOKEN" }'
              />
              <TextareaField
                label={t("adapters.sessionConfig")}
                value={form.sessionText}
                onChange={(value) => setForm((prev) => ({ ...prev, sessionText: value }))}
                hint="Per-variant isolation stays the default in Phase 2."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <TextareaField
                label={t("adapters.invokeConfigLabel")}
                value={form.invokeText}
                onChange={(value) => setForm((prev) => ({ ...prev, invokeText: value }))}
              />
              <TextareaField
                label={t("adapters.responseExtractLabel")}
                value={form.extractText}
                onChange={(value) => setForm((prev) => ({ ...prev, extractText: value }))}
              />
            </div>

            <TextareaField
              label={t("adapters.probeConfigLabel")}
              value={form.probeText}
              onChange={(value) => setForm((prev) => ({ ...prev, probeText: value }))}
              rows={12}
              hint='Probe variables support `{{runtime.*}}`, `{{session.id}}`, and `{{probe.steps.<step>.captures.<name>}}`.'
            />
          </div>

          <div className="card p-6 space-y-4">
            <div className="flex items-center gap-2">
              <TestTube2 className="w-4 h-4 text-gray-500" />
              <h2 className="text-lg font-semibold text-gray-900">{t("adapters.testBench")}</h2>
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">{t("adapters.promptLabel")}</label>
              <textarea
                value={testPrompt}
                onChange={(event) => setTestPrompt(event.target.value)}
                rows={4}
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900/10"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <TextareaField label={t("adapters.historyJson")} value={testHistoryText} onChange={setTestHistoryText} rows={8} />
              <TextareaField label={t("adapters.runtimeVarsJson")} value={testRuntimeVarsText} onChange={setTestRuntimeVarsText} rows={8} />
            </div>

            {testResult && (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 space-y-4">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs border ${testResult.success ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-rose-50 text-rose-700 border-rose-200"}`}>
                    <FlaskConical className="w-3.5 h-3.5" />
                    {testResult.success ? t("adapters.invokeSucceeded") : t("adapters.invokeFailed")}
                  </span>
                  <span className="text-xs text-slate-500 font-mono">{testResult.response_status}</span>
                  {testResult.session_id && (
                    <span className="text-xs text-slate-500 font-mono">session={testResult.session_id}</span>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <pre className="min-h-[160px] rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-800 font-mono overflow-auto whitespace-pre-wrap">
                    {testResult.response_text || testResult.response_error || "(no output)"}
                  </pre>
                  <pre className="min-h-[160px] rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-800 font-mono overflow-auto whitespace-pre-wrap">
                    {prettyJson(testResult.transport_meta)}
                  </pre>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <pre className="rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-800 font-mono overflow-auto whitespace-pre-wrap">
                    {prettyJson(testResult.rendered_request ?? {})}
                  </pre>
                  <pre className="rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-800 font-mono overflow-auto whitespace-pre-wrap">
                    {prettyJson(testResult.steps)}
                  </pre>
                </div>
              </div>
            )}
          </div>

          <div className="card p-6 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <TestTube2 className="w-4 h-4 text-gray-500" />
                <h2 className="text-lg font-semibold text-gray-900">{t("adapters.probeBench")}</h2>
              </div>
              <button
                type="button"
                onClick={() => void handleProbeTest()}
                disabled={probeTesting}
                className="inline-flex items-center gap-2 rounded-xl border border-fuchsia-200 bg-fuchsia-50 px-4 py-2 text-sm text-fuchsia-900 hover:bg-fuchsia-100 disabled:opacity-60 transition-colors"
              >
                <Play className="w-4 h-4" />
                {probeTesting ? t("adapters.testingProbe") : t("adapters.testProbe")}
              </button>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">{t("adapters.sessionIdLabel")}</label>
                <input
                  type="text"
                  value={probeSessionId}
                  onChange={(event) => setProbeSessionId(event.target.value)}
                  className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm font-mono text-gray-900 focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900/10"
                />
              </div>
              <TextareaField
                label={t("adapters.runtimeVarsJson")}
                value={testRuntimeVarsText}
                onChange={setTestRuntimeVarsText}
                rows={5}
              />
            </div>

            {probeResult && (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 space-y-4">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs border ${probeResult.verified ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-rose-50 text-rose-700 border-rose-200"}`}>
                    <FlaskConical className="w-3.5 h-3.5" />
                    {probeResult.verified ? t("common.probeVerified") : t("common.probeFailed")}
                  </span>
                  {probeResult.failure_type && (
                    <span className="text-xs text-slate-500 font-mono">{probeResult.failure_type}</span>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <pre className="min-h-[160px] rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-800 font-mono overflow-auto whitespace-pre-wrap">
                    {prettyJson(probeResult.assertion_results)}
                  </pre>
                  <pre className="min-h-[160px] rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-800 font-mono overflow-auto whitespace-pre-wrap">
                    {prettyJson(probeResult.evidence)}
                  </pre>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <pre className="rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-800 font-mono overflow-auto whitespace-pre-wrap">
                    {probeResult.failure_reason || "(no failure reason)"}
                  </pre>
                  <pre className="rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-800 font-mono overflow-auto whitespace-pre-wrap">
                    {prettyJson(probeResult.step_results)}
                  </pre>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}



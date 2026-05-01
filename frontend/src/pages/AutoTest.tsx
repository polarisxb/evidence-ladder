import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BrainCircuit, CheckCircle2, Loader2, Play, Route, ShieldCheck, Zap } from "lucide-react";
import { getAdapters } from "../api/adapters";
import { createAutoTestDraft } from "../api/autotest";
import { createScan } from "../api/scans";
import { useToast } from "../components/Toast";
import { useLocale } from "../i18n";
import type { Adapter, AutoTestBudget, AutoTestDraft, AutoTestPlan, AutoTestTargetType, ScanConfig } from "../types";

const TARGET_TYPES: AutoTestTargetType[] = [
  "openai_compatible",
  "custom",
  "builtin_vulnerable",
  "adapter",
  "claude",
];

const CATEGORY_OPTIONS = [
  "prompt_injection",
  "system_prompt_extraction",
  "information_disclosure",
  "jailbreak",
  "indirect_injection",
  "excessive_agency",
];

function PillList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <span className="text-sm text-gray-400">-</span>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className="inline-flex items-center rounded-lg border border-gray-200 bg-white px-2.5 py-1 text-xs font-medium text-gray-700"
        >
          {item}
        </span>
      ))}
    </div>
  );
}

function enabledAdvancedItems(scanDraft: ScanConfig | null): string[] {
  const advanced = scanDraft?.advanced;
  if (!advanced) return [];

  return [
    advanced.enable_mutations ? "mutation" : null,
    advanced.enable_crescendo ? "crescendo" : null,
    advanced.enable_pair ? "pair" : null,
    advanced.enable_tap ? "tap" : null,
  ].filter((item): item is string => Boolean(item));
}

export function AutoTest() {
  const navigate = useNavigate();
  const { t } = useLocale();
  const { toast } = useToast();
  const [name, setName] = useState("AutoTest Evidence Scan");
  const [targetType, setTargetType] = useState<AutoTestTargetType>("openai_compatible");
  const [targetUrl, setTargetUrl] = useState("");
  const [adapterId, setAdapterId] = useState("");
  const [adapters, setAdapters] = useState<Adapter[]>([]);
  const [budget, setBudget] = useState<AutoTestBudget>("medium");
  const [categories, setCategories] = useState<string[]>([
    "prompt_injection",
    "system_prompt_extraction",
    "information_disclosure",
  ]);
  const [enableQuartet, setEnableQuartet] = useState(true);
  const [enableCanary, setEnableCanary] = useState(true);
  const [enableProbe, setEnableProbe] = useState(false);
  const [plan, setPlan] = useState<AutoTestPlan | null>(null);
  const [scanDraft, setScanDraft] = useState<ScanConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);

  const selectedCategories = useMemo(
    () => (categories.length > 0 ? categories : ["all"]),
    [categories],
  );
  const selectedAdapter = useMemo(
    () => adapters.find((adapter) => adapter.id === adapterId) ?? null,
    [adapterId, adapters],
  );
  const advancedItems = useMemo(() => enabledAdvancedItems(scanDraft), [scanDraft]);

  useEffect(() => {
    getAdapters()
      .then(setAdapters)
      .catch((error) => {
        toast("warning", `${t("autotest.adaptersLoadFailed")}: ${error instanceof Error ? error.message : error}`);
      });
  }, [toast, t]);

  useEffect(() => {
    if (targetType === "adapter" && !adapterId && adapters[0]) {
      setAdapterId(adapters[0].id);
    }
  }, [adapterId, adapters, targetType]);

  function toggleCategory(category: string) {
    setCategories((prev) => (
      prev.includes(category)
        ? prev.filter((item) => item !== category)
        : [...prev, category]
    ));
  }

  async function buildDraft(): Promise<AutoTestDraft> {
    if (targetType === "adapter" && !adapterId) {
      throw new Error(t("autotest.adapterRequired"));
    }
    if (targetType === "custom" && !targetUrl.trim()) {
      throw new Error(t("autotest.targetUrlRequired"));
    }

    return createAutoTestDraft({
      name,
      target_type: targetType,
      target_url: targetUrl,
      adapter_id: targetType === "adapter" ? adapterId : null,
      adapter: selectedAdapter ? { probe_config: selectedAdapter.probe_config ?? null } : null,
      attack_categories: selectedCategories,
      budget,
      enable_quartet: enableQuartet,
      enable_canary: enableCanary,
      enable_probe: enableProbe,
    });
  }

  async function handleGeneratePlan() {
    setLoading(true);
    try {
      const draft = await buildDraft();
      setPlan(draft.plan);
      setScanDraft(draft.scan_config);
      toast("success", t("autotest.draftGenerated"));
    } catch (error) {
      toast("error", error instanceof Error ? error.message : t("autotest.planFailed"));
    } finally {
      setLoading(false);
    }
  }

  async function handleStartScan() {
    setStarting(true);
    try {
      const draft = await buildDraft();
      setPlan(draft.plan);
      setScanDraft(draft.scan_config);
      const { task_id } = await createScan(draft.scan_config);
      toast("success", t("autotest.scanStarted"));
      navigate(`/scan/${task_id}`);
    } catch (error) {
      toast("error", error instanceof Error ? error.message : t("autotest.scanFailed"));
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-gray-500">
            <BrainCircuit className="h-4 w-4" />
            <span>{t("autotest.eyebrow")}</span>
          </div>
          <h1 className="mt-2 text-2xl font-bold text-gray-900">{t("autotest.title")}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-gray-500">{t("autotest.subtitle")}</p>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[420px_1fr]">
        <section className="card space-y-5 p-6">
          <div className="flex items-center gap-2">
            <Route className="h-5 w-5 text-gray-700" />
            <h2 className="text-base font-semibold text-gray-900">{t("autotest.planConfig")}</h2>
          </div>

          <label className="block space-y-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              {t("common.name")}
            </span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus:border-gray-400 focus:outline-none"
            />
          </label>

          <label className="block space-y-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              {t("autotest.targetType")}
            </span>
            <select
              value={targetType}
              onChange={(event) => setTargetType(event.target.value as AutoTestTargetType)}
              className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus:border-gray-400 focus:outline-none"
            >
              {TARGET_TYPES.map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </label>

          {targetType === "custom" || targetType === "openai_compatible" ? (
            <label className="block space-y-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                {t("autotest.targetUrl")}
              </span>
              <input
                value={targetUrl}
                onChange={(event) => setTargetUrl(event.target.value)}
                placeholder="https://api.example.com/chat"
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus:border-gray-400 focus:outline-none"
              />
            </label>
          ) : null}

          {targetType === "adapter" ? (
            <label className="block space-y-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                {t("autotest.adapter")}
              </span>
              <select
                value={adapterId}
                onChange={(event) => setAdapterId(event.target.value)}
                className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus:border-gray-400 focus:outline-none"
              >
                <option value="">{t("autotest.selectAdapter")}</option>
                {adapters.map((adapter) => (
                  <option key={adapter.id} value={adapter.id}>
                    {adapter.name} ({adapter.transport})
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          <label className="block space-y-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              {t("autotest.budget")}
            </span>
            <select
              value={budget}
              onChange={(event) => setBudget(event.target.value as AutoTestBudget)}
              className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 focus:border-gray-400 focus:outline-none"
            >
              <option value="small">{t("autotest.budgetSmall")}</option>
              <option value="medium">{t("autotest.budgetMedium")}</option>
              <option value="full">{t("autotest.budgetFull")}</option>
            </select>
          </label>

          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              {t("autotest.riskCategories")}
            </p>
            <div className="grid grid-cols-1 gap-2">
              {CATEGORY_OPTIONS.map((category) => (
                <label
                  key={category}
                  className="flex cursor-pointer items-center gap-2 rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700"
                >
                  <input
                    type="checkbox"
                    checked={categories.includes(category)}
                    onChange={() => toggleCategory(category)}
                    className="h-4 w-4 rounded border-gray-300 text-gray-900"
                  />
                  <span>{category}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-2">
            {[
              [t("autotest.enableQuartet"), enableQuartet, setEnableQuartet],
              [t("autotest.enableCanary"), enableCanary, setEnableCanary],
              [t("autotest.enableProbe"), enableProbe, setEnableProbe],
            ].map(([label, value, setter]) => (
              <label
                key={String(label)}
                className="flex cursor-pointer items-center justify-between rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700"
              >
                <span>{label as string}</span>
                <input
                  type="checkbox"
                  checked={value as boolean}
                  onChange={(event) => (setter as (value: boolean) => void)(event.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-gray-900"
                />
              </label>
            ))}
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            <button
              type="button"
              onClick={handleGeneratePlan}
              disabled={loading || starting}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm font-semibold text-gray-900 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Route className="h-4 w-4" />}
              {t("autotest.generateDraft")}
            </button>
            <button
              type="button"
              onClick={handleStartScan}
              disabled={loading || starting}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-gray-900 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {starting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              {t("autotest.startScan")}
            </button>
          </div>
        </section>

        <section className="space-y-5">
          <div className="grid gap-4 md:grid-cols-3">
            <div className="card p-5">
              <div className="flex items-center gap-2 text-gray-500">
                <ShieldCheck className="h-4 w-4" />
                <span className="text-xs font-semibold uppercase tracking-wide">
                  {t("autotest.probeAvailable")}
                </span>
              </div>
              <p className="mt-3 text-2xl font-bold text-gray-900">
                {plan?.probe_available ? t("common.yes") : t("common.no")}
              </p>
            </div>
            <div className="card p-5">
              <div className="flex items-center gap-2 text-gray-500">
                <Zap className="h-4 w-4" />
                <span className="text-xs font-semibold uppercase tracking-wide">
                  {t("autotest.maxRetestRounds")}
                </span>
              </div>
              <p className="mt-3 text-2xl font-bold text-gray-900">
                {plan?.max_retest_rounds ?? "-"}
              </p>
            </div>
            <div className="card p-5">
              <div className="flex items-center gap-2 text-gray-500">
                <CheckCircle2 className="h-4 w-4" />
                <span className="text-xs font-semibold uppercase tracking-wide">
                  {t("autotest.quartetMode")}
                </span>
              </div>
              <p className="mt-3 text-2xl font-bold text-gray-900">
                {scanDraft?.advanced?.quartet_mode ?? "-"}
              </p>
            </div>
          </div>

          <div className="card space-y-5 p-6">
            <div>
              <h2 className="text-base font-semibold text-gray-900">{t("autotest.planPreview")}</h2>
              <p className="mt-1 text-sm text-gray-500">{t("autotest.planPreviewDesc")}</p>
            </div>

            {plan ? (
              <div className="grid gap-5 lg:grid-cols-3">
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    {t("autotest.phases")}
                  </p>
                  <PillList items={plan.phases} />
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    {t("autotest.strategies")}
                  </p>
                  <PillList items={plan.strategies} />
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    {t("autotest.riskCategories")}
                  </p>
                  <PillList items={plan.risk_categories} />
                </div>
              </div>
            ) : (
              <div className="flex min-h-[220px] items-center justify-center rounded-2xl border border-dashed border-gray-200 bg-gray-50">
                <p className="text-sm text-gray-400">{t("autotest.emptyPlan")}</p>
              </div>
            )}
          </div>

          <div className="card space-y-5 p-6">
            <div>
              <h2 className="text-base font-semibold text-gray-900">{t("autotest.scanDraft")}</h2>
              <p className="mt-1 text-sm text-gray-500">{t("autotest.scanDraftDesc")}</p>
            </div>

            {scanDraft ? (
              <div className="grid gap-5 lg:grid-cols-3">
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    {t("autotest.targetType")}
                  </p>
                  <PillList items={[scanDraft.target_type]} />
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    {t("autotest.advancedStrategies")}
                  </p>
                  <PillList items={advancedItems} />
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    {t("autotest.parallelAttacks")}
                  </p>
                  <PillList items={[String(scanDraft.advanced?.parallel_attacks ?? "-")]} />
                </div>
              </div>
            ) : (
              <div className="flex min-h-[160px] items-center justify-center rounded-2xl border border-dashed border-gray-200 bg-gray-50">
                <p className="text-sm text-gray-400">{t("autotest.emptyDraft")}</p>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

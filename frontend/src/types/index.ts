export interface ScanTask {
  id: string;
  name: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  target_url: string;
  target_type: "openai_compatible" | "custom" | "builtin_vulnerable" | "adapter" | "claude";
  adapter_id?: string | null;
  attack_categories: string[];
  total_attacks: number;
  completed_attacks: number;
  vulnerabilities_found: number;
  overall_score: number | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  target_health?: TargetHealth | null;
  health_probe_passed?: boolean | null;
  health_failure_reason?: string | null;
  recent_health_signature?: string | null;
  invalid_response_ratio?: number | null;
}

export type TargetHealth = "healthy" | "degraded" | "unhealthy";

export interface TargetOriginRules {
  exact?: string[];
  contains?: string[];
  regex?: string[];
}

export interface TargetConfig {
  /** 关联已配置的供应商 ID，自动使用其 API Key / Base URL / 模型 */
  provider_id?: string;
  api_key?: string;
  model?: string;
  system_prompt?: string;
  canary_tokens?: string[];
  headers?: Record<string, string>;
  timeout_s?: number;
  vulnerable_level?: number;
  origin_rules?: TargetOriginRules;
}

export interface AdvancedConfig {
  enable_crescendo: boolean;
  enable_fitd: boolean;
  fitd_num_levels: number;
  enable_msj: boolean;
  msj_shot_count: number;
  enable_ice: boolean;
  enable_tap: boolean;
  enable_pair: boolean;
  enable_self_explanation: boolean;
  enable_mutations: boolean;
  /** Quartet control mode. Supersedes enable_control_variants. */
  quartet_mode: "full" | "adaptive" | "off";
  /** @deprecated Use quartet_mode instead. Kept for backward compat. */
  enable_control_variants?: boolean | null;
  parallel_attacks: number;
  crescendo_max_turns: number;
  tap_branching_factor: number;
  tap_max_depth: number;
  pair_max_rounds: number;
  self_explanation_rounds: number;
  mutation_strategies: string[];
  health_window_size?: number;
  health_invalid_threshold?: number;
  health_signature_streak?: number;
}

export interface ScanConfig {
  name: string;
  target_url: string;
  target_type: "openai_compatible" | "custom" | "builtin_vulnerable" | "adapter" | "claude";
  adapter_id?: string | null;
  target_config?: TargetConfig;
  runtime_vars?: Record<string, unknown>;
  attack_categories: string[];
  advanced?: AdvancedConfig;
  judge_provider_id?: string | null;
  judge_model?: string | null;
  generation_provider_id?: string | null;
  generation_model?: string | null;
}

export type AutoTestBudget = "small" | "medium" | "full";
export type AutoTestTargetType = ScanConfig["target_type"];

export interface AutoTestPlanRequest {
  name?: string | null;
  target_type?: AutoTestTargetType;
  target_url?: string;
  adapter_id?: string | null;
  target_config?: TargetConfig | null;
  runtime_vars?: Record<string, unknown> | null;
  attack_categories?: string[];
  budget?: AutoTestBudget;
  enable_quartet?: boolean;
  enable_canary?: boolean;
  enable_probe?: boolean;
  max_retest_rounds?: number | null;
  adapter?: Record<string, unknown> | null;
  adapter_payload?: Record<string, unknown> | null;
  probe_config?: Record<string, unknown> | null;
  judge_provider_id?: string | null;
  judge_model?: string | null;
  generation_provider_id?: string | null;
  generation_model?: string | null;
}

export interface AutoTestPlan {
  target_type: AutoTestTargetType | string;
  budget: AutoTestBudget;
  risk_categories: string[];
  strategies: string[];
  phases: string[];
  probe_available: boolean;
  max_retest_rounds: number;
}

export interface AutoTestDraft {
  plan: AutoTestPlan;
  scan_config: ScanConfig;
}

export interface AutoTestMetrics {
  total_results: number;
  evaluable_results: number;
  evaluable_attack_results: number;
  evaluable_clean_results: number;
  not_evaluable_count: number;
  not_evaluable_rate: number | null;
  raw_asr: number | null;
  judge_asr: number | null;
  text_claim_asr: number | null;
  rule_verified_asr: number | null;
  tool_observed_asr: number | null;
  probe_verified_asr: number | null;
  evidence_verified_asr: number | null;
  quartet_validated_asr: number | null;
  utility_rate: number | null;
  over_defense_rate: number | null;
  weak_evidence_count: number;
  strong_evidence_count: number;
  retest_triggered_count: number;
  overturned_count: number;
  extra_query_count: number;
}

export interface AutoTestSummaryItem {
  result_id: string;
  category: string;
  attack_name: string;
  verdict_status?: string | null;
  business_verification_status?: string | null;
  evidence_level?: "E0" | "E1" | "E2" | "E3" | "E4" | "E5" | null;
  evidence_label: string;
  is_evaluable: boolean;
  is_strong_evidence: boolean;
  needs_retest: boolean;
  conflict_types: string[];
  not_evaluable_reason?: string | null;
  evidence_sources: string[];
}

export interface AutoTestRetestActionGroup {
  result_id: string;
  category: string;
  attack_name: string;
  actions: Array<{ action_type: string; reason: string }>;
}

export interface AutoTestRetestDraft {
  source_scan_id: string;
  source_result_ids: string[];
  retest_reason: string;
  action_count: number;
  scan_config: ScanConfig;
}

export type AutoTestRetestOutcome =
  | "confirmed_by_retest"
  | "overturned_by_retest"
  | "manual_review_needed";

export interface AutoTestRetestSource {
  source_scan_id: string;
  source_result_ids: string[];
  retest_reason: string;
  retest_type?: string | null;
}

export interface AutoTestRetestComparison {
  source_result_id: string;
  source_category: string;
  source_attack_name: string;
  source_evidence_level?: "E0" | "E1" | "E2" | "E3" | "E4" | "E5" | null;
  source_conflict_types: string[];
  matching_retest_result_ids: string[];
  retest_evidence_levels: string[];
  outcome: AutoTestRetestOutcome;
  outcome_reason: string;
}

export interface AutoTestRetestRunRecord {
  id: string;
  source_scan_id: string;
  retest_scan_id: string;
  source_result_ids: string[];
  retest_reason: string;
  retest_type: string;
  status: string;
  outcome_counts: Partial<Record<AutoTestRetestOutcome, number>>;
  comparison_snapshot: AutoTestRetestComparison[];
  created_at: string;
  updated_at: string;
}

export interface AutoTestSummary {
  scan_id: string;
  scan_name: string;
  scan_status: string;
  metrics: AutoTestMetrics;
  items: AutoTestSummaryItem[];
  retest_actions: AutoTestRetestActionGroup[];
  retest_source?: AutoTestRetestSource | null;
  retest_comparisons?: AutoTestRetestComparison[];
  retest_outcome_counts?: Partial<Record<AutoTestRetestOutcome, number>>;
  retest_run?: AutoTestRetestRunRecord | null;
}

export type BusinessVerificationStatus =
  | "not_applicable"
  | "text_claim_only"
  | "probe_verified"
  | "probe_failed"
  | "probe_inconclusive";

export interface BaselineProbeResult {
  status?: "ok" | "failed" | string | null;
  reason?: string | null;
  http_status?: number | null;
  probed_at?: string | null;
  cached?: boolean | null;
}

export interface ResponseEvaluation {
  response_origin?: "model" | "app_fallback" | "transport_error" | "adapter_error" | "gateway_error" | "unknown" | string | null;
  origin_confidence?: "high" | "medium" | "low" | string | null;
  evaluation_validity?: "evaluable" | "not_evaluable" | string | null;
  invalid_reason?: string | null;
  matched_signature?: string | null;
  transport_ok?: boolean | null;
  http_status?: number | null;
  content_type?: string | null;
  evidence_codes?: string[];
  baseline_probe?: BaselineProbeResult | null;
  // Two-dimensional Provenance fields
  model_invoked?: boolean | null;
  post_processed?: boolean | null;
  block_reason?: string | null;
  post_reason?: string | null;
  provenance_source?: string | null;
}

export interface AdapterAuthConfig {
  type: "none" | "bearer" | "header" | "query";
  secret_ref?: string | null;
  name?: string | null;
  scheme?: string | null;
}

export interface AdapterRequestConfig {
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  path: string;
  headers?: Record<string, unknown> | null;
  query?: Record<string, unknown> | null;
  body_template?: Record<string, unknown> | unknown[] | string | null;
}

export interface AdapterSessionCreateConfig extends AdapterRequestConfig {
  extract: {
    session_id: string;
  };
}

export interface AdapterSessionConfig {
  mode: "per_variant_isolated";
  create?: AdapterSessionCreateConfig | null;
  close?: AdapterRequestConfig | null;
}

export interface AdapterInvokeConfig extends AdapterRequestConfig {
  model?: string | null;
  system_prompt?: string | null;
}

export interface ProbeCaptureConfig {
  json_path: string;
}

export interface ProbeStepConfig extends AdapterRequestConfig {
  name: string;
  captures?: Record<string, ProbeCaptureConfig>;
}

export interface ProbeAssertion {
  type:
    | "json_path_exists"
    | "json_path_equals"
    | "json_path_contains"
    | "status_code_is"
    | "text_contains";
  step?: string | null;
  path?: string | null;
  expected?: unknown;
  contains?: string | null;
  status_code?: number | null;
}

export interface AdapterProbeConfig {
  enabled?: boolean;
  steps: ProbeStepConfig[];
  assertions: ProbeAssertion[];
}

export interface AdapterResponseExtract {
  mode: "json_paths" | "raw_text";
  text_path?: string | null;
  error_path?: string | null;
  tool_calls_path?: string | null;
}

export interface Adapter {
  id: string;
  name: string;
  description?: string | null;
  mode: "direct_http_adapter";
  transport: "http_json" | "openai_chat";
  base_url: string;
  auth_config: AdapterAuthConfig;
  session_config?: AdapterSessionConfig | null;
  invoke_config: AdapterInvokeConfig;
  response_extract: AdapterResponseExtract;
  probe_config?: AdapterProbeConfig | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface AdapterConfig {
  name: string;
  description?: string | null;
  mode: "direct_http_adapter";
  transport: "http_json" | "openai_chat";
  base_url: string;
  auth_config: AdapterAuthConfig;
  session_config?: AdapterSessionConfig | null;
  invoke_config: AdapterInvokeConfig;
  response_extract: AdapterResponseExtract;
  probe_config?: AdapterProbeConfig | null;
  enabled: boolean;
}

export interface AdapterTestStep {
  name: string;
  ok: boolean;
  detail?: string | null;
  status_code?: number | null;
}

export interface AdapterTestRequest {
  adapter_id?: string | null;
  adapter?: AdapterConfig;
  prompt: string;
  history?: Array<Record<string, unknown>>;
  runtime_vars?: Record<string, unknown>;
  variant_type?: string;
  scan_id?: string | null;
  case_id?: string | null;
}

export interface AdapterTestResult {
  success: boolean;
  response_status: string;
  response_text?: string | null;
  response_error?: string | null;
  session_id?: string | null;
  transport_meta: Record<string, unknown>;
  rendered_request?: Record<string, unknown> | null;
  steps: AdapterTestStep[];
}

export interface ProbeStepResult {
  name: string;
  ok: boolean;
  status_code?: number | null;
  failure_type?: string | null;
  failure_reason?: string | null;
  captures: Record<string, unknown>;
  rendered_request?: Record<string, unknown> | null;
  response_preview?: string | null;
}

export interface ProbeAssertionResult {
  type: string;
  step?: string | null;
  ok: boolean;
  actual?: unknown;
  expected?: unknown;
  failure_reason?: string | null;
  evidence: Record<string, unknown>;
}

export interface ProbeEvidence {
  step: string;
  kind: string;
  value?: unknown;
}

export interface ProbeTestRequest {
  adapter_id?: string | null;
  adapter?: AdapterConfig;
  probe_config?: AdapterProbeConfig | null;
  runtime_vars?: Record<string, unknown>;
  session_id?: string | null;
  variant_type?: string;
  scan_id?: string | null;
  case_id?: string | null;
}

export interface AdapterProbeTestResult {
  success: boolean;
  verified: boolean;
  assertion_results: ProbeAssertionResult[];
  evidence: ProbeEvidence[];
  failure_reason?: string | null;
  failure_type?: string | null;
  step_results: ProbeStepResult[];
}

export interface AdapterScanConfig extends ScanConfig {
  target_type: "adapter";
  adapter_id: string;
  runtime_vars: Record<string, unknown>;
}

export type CanaryChannel = "response_text" | "tool_call" | "business_state";

export interface CanaryObservation {
  token: string;
  channel: CanaryChannel;
  context: string;
  evidence_level: string;
  kill_chain_stage: string;
  strength: string;
  excerpt: string;
}

export interface CanaryProvenance {
  observations: CanaryObservation[];
  evidence_level: string | null;
  kill_chain_stage: string | null;
  is_quoted_only: boolean;
  strongest_channel: CanaryChannel | null;
}

export interface AttackResult {
  id: string;
  template_id: string;
  category: string;
  technique: string;
  attack_name: string;
  payload_text: string;
  target_response: string | null;
  attack_successful: boolean;
  confidence: number;
  risk_level: "critical" | "high" | "medium" | "low" | "none";
  evidence: string | null;
  leaked_info: string | null;
  explanation: string | null;
  remediation: string | null;
  owasp_id: string | null;
  risk_score: number;
  verdict_status?:
    | "passed"
    | "rule_verified"
    | "manual_verified"
    | "ai_suspected"
    | "manual_review_needed"
    | "false_positive"
    | "not_evaluable"
    | null;
  verdict_reason?: string | null;
  rule_hits?: Array<{ rule: string; evidence: string }>;
  canary_provenance?: CanaryProvenance | null;
  execution_mode?: "DISCUSSING_ATTACK" | "EXECUTING_ATTACK" | "UNCERTAIN" | null;
  blackbox_outcome?:
    | "NO_INJECTION_SUCCESS"
    | "ATTACK_DISCUSSION_ONLY"
    | "PARTIAL_INJECTION_SUCCESS"
    | "FULL_INJECTION_SUCCESS"
    | null;
  behavior_flags?: {
    discussion_only?: boolean;
    attack_obedience?: boolean;
    task_deviation?: boolean;
    secret_disclosure?: boolean;
    unauthorized_action_claim?: boolean;
    original_task_completed?: boolean | null;
  } | null;
  attack_goal_score?: number | null;
  utility_score?: number | null;
  utility_explanation?: string | null;
  control_assessment?:
    | "attack_delta_supported"
    | "discussion_supported"
    | "controls_inconclusive"
    | "controls_missing"
    | null;
  control_summary?: string | null;
  case_id?: string | null;
  case_final_outcome?:
    | "rule_verified_finding"
    | "attack_delta_supported"
    | "discussion_supported"
    | "controls_inconclusive"
    | "controls_missing"
    | "passed"
    | "not_evaluable"
    | null;
  quartet_present?: boolean | null;
  business_verification_status?: BusinessVerificationStatus | null;
  probe_summary?: Record<string, unknown> | null;
  probe_evidence_preview?: Array<Record<string, unknown>>;
  response_evaluation?: ResponseEvaluation | null;
  analysis_raw?: {
    cvss_metrics?: {
      attack_vector: string;
      attack_complexity: string;
      privileges_required: string;
      user_interaction: string;
      confidentiality: string;
      integrity: string;
      availability: string;
    };
    [key: string]: unknown;
  };
  created_at: string;
}

export interface AttackCaseVariant {
  id: string;
  variant_type: "attack" | "clean" | "quoted_attack" | "benign_distractor" | string;
  position: number;
  request_text: string;
  response_text: string | null;
  response_error: string | null;
  response_status: string | null;
  latency_ms: number | null;
  response_evaluation?: ResponseEvaluation | null;
  analysis_raw?: Record<string, unknown> | null;
  is_primary: boolean;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface AttackCaseLegacyResultSummary {
  id: string;
  attack_successful: boolean;
  confidence: number;
  risk_level: "critical" | "high" | "medium" | "low" | "none" | string;
  risk_score: number;
  target_response: string | null;
  verdict_status?: AttackResult["verdict_status"];
  verdict_reason?: string | null;
  response_evaluation?: ResponseEvaluation | null;
  created_at: string;
}

export interface AttackCase {
  id: string;
  scan_task_id: string;
  template_id: string;
  category: string;
  technique: string;
  attack_name: string;
  protocol_version: string;
  case_status: string;
  case_final_outcome:
    | "rule_verified_finding"
    | "attack_delta_supported"
    | "discussion_supported"
    | "controls_inconclusive"
    | "controls_missing"
    | "passed"
    | "not_evaluable"
    | string
    | null;
  attack_variant_response: string | null;
  control_assessment?: AttackResult["control_assessment"];
  control_summary?: string | null;
  verdict_status?: AttackResult["verdict_status"];
  verdict_reason?: string | null;
  legacy_attack_result_id: string | null;
  primary_attack_successful: boolean | null;
  quartet_present: boolean;
  variant_count: number;
  business_verification_status?: BusinessVerificationStatus | null;
  probe_summary?: Record<string, unknown> | null;
  probe_evidence_preview?: Array<Record<string, unknown>>;
  response_evaluation?: ResponseEvaluation | null;
  summary_json?: Record<string, unknown> | null;
  // Phase 4: judge calibration
  judge_snapshot?: Record<string, unknown> | null;
  review_required?: boolean | null;
  reportable?: boolean | null;
  created_at: string;
  updated_at: string;
}

// ── Judge Calibration ────────────────────────────────────────────────────────

export interface JudgeGoldLabel {
  reportable: boolean;
  verdict_status: string;
  execution_mode?: string | null;
  blackbox_outcome?: string | null;
}

export interface JudgeCalibrationSample {
  id: string;
  source_type: string;
  attack_case_id: string | null;
  judge_input_snapshot: Record<string, unknown> | null;
  judge_output: Record<string, unknown> | null;
  gold_label: Record<string, unknown> | null;
  gold_rationale: string | null;
  labeler: string | null;
  label_version: string;
  sampling_reason: string | null;
  is_drift_sample: boolean;
  created_at: string;
  updated_at: string;
}

export interface JudgeMisclassificationPreview {
  sample_id: string;
  attack_case_id: string | null;
  scan_id: string | null;
  judge_verdict: string | null;
  gold_verdict: string | null;
  judge_reportable: boolean | null;
  gold_reportable: boolean | null;
  mismatch_type: string;
}

export interface JudgeCalibrationBreakdownItem {
  key: string;
  sample_count: number;
  precision: number | null;
  false_positive_rate: number | null;
  recall: number | null;
}

export interface JudgeConfusionMatrix {
  true_positive: number;
  false_positive: number;
  true_negative: number;
  false_negative: number;
  evaluated: number;
}

export interface JudgeCalibrationSummary {
  sample_count: number;
  labeled_count: number;
  judge_precision_at_gold: number | null;
  judge_recall_at_gold: number | null;
  judge_false_positive_rate: number | null;
  manual_review_overturn_rate: number | null;
  confusion_matrix: JudgeConfusionMatrix | null;
  by_category: JudgeCalibrationBreakdownItem[];
  by_source_type: JudgeCalibrationBreakdownItem[];
  by_target_type: JudgeCalibrationBreakdownItem[];
  by_judge_version: JudgeCalibrationBreakdownItem[];
  by_business_verification_status: JudgeCalibrationBreakdownItem[];
  misclassified_samples: JudgeMisclassificationPreview[];
}

export interface JudgeCalibrationRun {
  id: string;
  name: string | null;
  run_mode: string;
  filters_json: Record<string, unknown> | null;
  sample_count: number;
  summary_json: Record<string, unknown> | null;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface AttackCaseDetail extends AttackCase {
  variants: AttackCaseVariant[];
  legacy_result: AttackCaseLegacyResultSummary | null;
  probe_evidence_json?: Record<string, unknown> | null;
}

export interface CategoryScore {
  category: string;
  category_name: string;
  owasp_id: string;
  score: number;
  pass_rate: number;
  attack_success_rate: number;
  total_tests: number;
  successful_attacks: number;
  failed_attacks: number;
  risk_level: string;
}

export interface SecurityReport {
  scan_id: string;
  scan_name: string;
  target_url: string;
  overall_score: number;
  security_posture_score: number;
  risk_level: string;
  total_attacks: number;
  completed_attacks: number;
  successful_attacks: number;
  attack_success_rate: number;
  severity_ratio: number;
  average_finding_severity: number | null;
  average_attack_goal_score: number | null;
  average_utility_score: number | null;
  utility_scored_results: number;
  finding_breakdown: {
    rule_verified: number;
    manual_verified: number;
    ai_suspected: number;
    manual_review_needed: number;
    false_positive: number;
    not_evaluable: number;
  };
  /** Verdict-based six-bucket distribution shared with the backend
   *  `finding_classifier`. Unlike `finding_breakdown` (keyed by raw verdict
   *  status), each case is mapped to exactly one bucket here. */
  finding_counts?: {
    confirmed: number;
    suspected: number;
    needs_review: number;
    passed: number;
    not_evaluable: number;
    false_positive: number;
  };
  /** confirmed + suspected — matches `ScanTask.vulnerabilities_found`. */
  confirmed_findings?: number;
  needs_review_count?: number;
  false_positive_count?: number;
  blackbox_outcome_breakdown: {
    full_injection_success: number;
    partial_injection_success: number;
    attack_discussion_only: number;
    no_injection_success: number;
    unclassified: number;
  };
  business_verification_breakdown?: {
    probe_verified: number;
    text_claim_only: number;
    probe_failed: number;
    not_applicable: number;
  };
  target_health?: string | null;
  health_probe_passed?: boolean | null;
  health_failure_reason?: string | null;
  recent_health_signature?: string | null;
  invalid_response_ratio?: number | null;
  category_scores: CategoryScore[];
  critical_findings: AttackResult[];
  high_findings: AttackResult[];
  medium_findings: AttackResult[];
  low_findings: AttackResult[];
  recommendations: string[];
}

export interface ScanEvent {
  type: string;
  template_id?: string;
  attack_name?: string;
  category?: string;
  successful?: boolean;
  risk_level?: string;
  completed?: number;
  total?: number;
  vulnerabilities_found?: number;
  overall_score?: number;
  probe_runtime_state?: "pending" | "verified" | "failed" | "inconclusive" | "skipped";
  probe_case_id?: string;
  target_health?: TargetHealth | null;
  health_probe_passed?: boolean | null;
  health_failure_reason?: string | null;
  recent_health_signature?: string | null;
  invalid_response_ratio?: number | null;
  error?: string;
  // Client-side timestamp stamped when the WebSocket receives the event.
  // Used by the UI to show how long a still-running attack has been active.
  received_at?: number;
}

export interface BuiltinTarget {
  level: number;
  name: string;
  description: string;
  protection: string;
}

export type RiskLevel = "critical" | "high" | "medium" | "low" | "none";

// ── Model Providers ───────────────────────────────────────────────────────────

export type ProviderType =
  | "openai" | "deepseek" | "glm" | "minimax" | "gemini" | "qwen" | "claude"
  | "nvidia" | "mistral" | "groq" | "moonshot" | "doubao" | "yi"
  | "baichuan" | "stepfun" | "siliconflow" | "xai" | "together"
  | "custom";

export interface ApiKeyInfo {
  index: number;
  label: string;
  masked_key: string;
}

export interface ModelProvider {
  id: string;
  name: string;
  provider_type: ProviderType | string;
  api_key_set: boolean;
  api_key_count: number;
  api_keys: ApiKeyInfo[];
  base_url: string | null;
  judge_model: string | null;
  mini_model: string | null;
  is_judge_default: boolean;
  is_generation_default: boolean;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApiKeyInput {
  index: number;
  label: string;
  key: string;
}

export interface ModelProviderCreate {
  name: string;
  provider_type: ProviderType;
  api_key?: string;
  api_keys?: ApiKeyInput[];
  base_url?: string | null;
  judge_model?: string | null;
  mini_model?: string | null;
  enabled?: boolean;
}

export interface ModelProviderUpdate {
  name?: string;
  provider_type?: ProviderType;
  api_key?: string;
  api_keys?: ApiKeyInput[];
  base_url?: string | null;
  judge_model?: string | null;
  mini_model?: string | null;
  enabled?: boolean;
}

/** Preset base URLs keyed by provider_type */
export const PROVIDER_BASE_URLS: Record<ProviderType, string> = {
  openai:      "https://api.openai.com/v1",
  deepseek:    "https://api.deepseek.com",
  glm:         "https://open.bigmodel.cn/api/paas/v4",
  minimax:     "https://api.minimax.chat/v1",
  gemini:      "https://generativelanguage.googleapis.com/v1beta/openai",
  qwen:        "https://dashscope.aliyuncs.com/compatible-mode/v1",
  // Claude uses the Anthropic SDK — base_url is informational only
  claude:      "https://api.anthropic.com",
  // ── Additional well-known providers (all OpenAI-compatible) ──
  nvidia:      "https://integrate.api.nvidia.com/v1",
  mistral:     "https://api.mistral.ai/v1",
  groq:        "https://api.groq.com/openai/v1",
  moonshot:    "https://api.moonshot.cn/v1",
  doubao:      "https://ark.cn-beijing.volces.com/api/v3",
  yi:          "https://api.lingyiwanwu.com/v1",
  baichuan:    "https://api.baichuan-ai.com/v1",
  stepfun:     "https://api.stepfun.com/v1",
  siliconflow: "https://api.siliconflow.cn/v1",
  xai:         "https://api.x.ai/v1",
  together:    "https://api.together.xyz/v1",
  custom:      "",
};

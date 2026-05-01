import { request } from "./client";

export interface OverviewStats {
  total_scans: number;
  completed_scans: number;
  total_attacks: number;
  successful_attacks: number;
  avg_score: number | null;
  attack_success_rate: number;
}

export interface ScoreTrendPoint {
  scan_id: string;
  name: string;
  score: number;
  date: string;
}

export interface RiskDistribution {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface CategoryRate {
  category: string;
  total: number;
  successful: number;
  rate: number;
}

export interface ComplianceData {
  owasp_coverage: number;
  atlas_coverage: number;
  owasp_results: Array<{
    id: string;
    name: string;
    testable: boolean;
    tested: boolean;
    total_tests: number;
    passed: number;
    failed: number;
    score: number | null;
  }>;
  tested_atlas_ids: string[];
  overall_score: number | null;
}

export async function getOverviewStats(): Promise<OverviewStats> {
  const res = await request<{ data: OverviewStats }>("/stats/overview");
  return res.data;
}

export async function getScoreTrend(limit = 20): Promise<ScoreTrendPoint[]> {
  const res = await request<{ data: ScoreTrendPoint[] }>(`/stats/score-trend?limit=${limit}`);
  return res.data;
}

export async function getRiskDistribution(): Promise<RiskDistribution> {
  const res = await request<{ data: RiskDistribution }>("/stats/risk-distribution");
  return res.data;
}

export async function getCategorySuccessRate(): Promise<CategoryRate[]> {
  const res = await request<{ data: CategoryRate[] }>("/stats/category-success-rate");
  return res.data;
}

export async function getComplianceScore(scanId: string): Promise<ComplianceData> {
  const res = await request<{ data: ComplianceData }>(`/stats/compliance/${scanId}`);
  return res.data;
}

export interface CompareResult {
  scan_a: ScanSummary;
  scan_b: ScanSummary;
  score_diff: number;
  new_vulnerabilities: string[];
  fixed_vulnerabilities: string[];
  persistent_vulnerabilities: string[];
}

interface ScanSummary {
  scan_id: string;
  name: string;
  overall_score: number | null;
  total_attacks: number;
  vulnerabilities_found: number;
  created_at: string | null;
  categories: Record<string, { total: number; successful: number; rate: number }>;
}

export async function compareScans(scanA: string, scanB: string): Promise<CompareResult> {
  const res = await request<{ data: CompareResult }>(`/stats/compare?scan_a=${scanA}&scan_b=${scanB}`);
  return res.data;
}

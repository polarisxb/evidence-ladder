import type { RiskLevel } from "../types";

export const riskColors: Record<RiskLevel, { bg: string; text: string; border: string }> = {
  critical: { bg: "bg-red-500/10", text: "text-red-500", border: "border-red-500" },
  high: { bg: "bg-orange-500/10", text: "text-orange-500", border: "border-orange-500" },
  medium: { bg: "bg-yellow-500/10", text: "text-yellow-500", border: "border-yellow-500" },
  low: { bg: "bg-green-500/10", text: "text-green-500", border: "border-green-500" },
  none: { bg: "bg-gray-100", text: "text-gray-600", border: "border-gray-300" },
};

export function scoreToRisk(score: number): RiskLevel {
  if (score >= 90) return "low";
  if (score >= 70) return "medium";
  if (score >= 50) return "high";
  return "critical";
}

export function riskLabel(level: RiskLevel): string {
  const labels: Record<RiskLevel, string> = {
    critical: "CRITICAL",
    high: "HIGH",
    medium: "MEDIUM",
    low: "LOW",
    none: "SAFE",
  };
  return labels[level];
}

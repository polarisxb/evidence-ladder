"""Compare findings only when the counterpart actually evaluated the same case."""
from collections import defaultdict
from collections.abc import Sequence

from app.models import AttackResult
from app.services.evidence_arbiter import arbitrate_evidence
from app.services.finding_classifier import classify_finding, is_confirmed_finding
from app.services.risk_scorer import is_not_evaluable_result, scoring_result_payload


def compare_finding_names(a: Sequence[AttackResult], b: Sequence[AttackResult]) -> dict[str, list[str]]:
    def payloads(rows: Sequence[AttackResult]) -> list[dict]:
        return [
            {**scoring_result_payload(row), "name": row.attack_name, "key": (row.template_id, row.payload_text)}
            for row in rows
        ]

    def positive_names(rows: list[dict]) -> set[str]:
        return {row["name"] for row in rows if is_confirmed_finding(row)}

    def contradicted_names(source: list[dict], counterpart: list[dict]) -> set[str]:
        by_key: dict[tuple, list[dict]] = defaultdict(list)
        positive_by_name: dict[str, list[dict]] = defaultdict(list)
        for row in counterpart:
            by_key[row["key"]].append(row)
        for row in source:
            if is_confirmed_finding(row):
                positive_by_name[row["name"]].append(row)
        return {
            name for name, positives in positive_by_name.items()
            if all(
                by_key.get(row["key"]) and all(
                    not is_not_evaluable_result(other)
                    and not arbitrate_evidence(other).is_strong_evidence
                    and classify_finding(other) in {"passed", "false_positive"}
                    for other in by_key[row["key"]]
                )
                for row in positives
            )
        }

    a_rows, b_rows = payloads(a), payloads(b)
    a_names, b_names = positive_names(a_rows), positive_names(b_rows)
    fixed = (a_names - b_names) & contradicted_names(a_rows, b_rows)
    new = (b_names - a_names) & contradicted_names(b_rows, a_rows)
    persistent = a_names & b_names
    return {
        "new_vulnerabilities": sorted(new),
        "fixed_vulnerabilities": sorted(fixed),
        "persistent_vulnerabilities": sorted(persistent),
        "uncompared_vulnerabilities": sorted((a_names | b_names) - fixed - new - persistent),
    }

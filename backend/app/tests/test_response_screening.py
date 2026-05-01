import unittest

from app.services.response_screening import (
    KNOWN_FALLBACK_SIGNATURES,
    TargetResponseEnvelope,
    screen_response_origin,
)


class ResponseScreeningTests(unittest.TestCase):
    def test_known_fallback_is_not_evaluable(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="I'm experiencing technical difficulties. Please contact our support line.",
                response_status="completed",
                target_type="adapter",
                transport_ok=True,
            )
        )

        self.assertEqual(evaluation.evaluation_validity, "not_evaluable")
        self.assertEqual(evaluation.response_origin, "app_fallback")
        self.assertEqual(evaluation.matched_signature, "technical_difficulties_support_line")
        self.assertEqual(
            KNOWN_FALLBACK_SIGNATURES[evaluation.matched_signature],
            "i'm experiencing technical difficulties. please contact our support line.",
        )

    def test_configured_exact_origin_rule_is_not_evaluable(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="Service temporarily warming up.",
                response_status="completed",
                target_type="custom",
                transport_ok=True,
            ),
            origin_rules={"exact": ["service temporarily warming up."]},
        )

        self.assertEqual(evaluation.evaluation_validity, "not_evaluable")
        self.assertEqual(evaluation.invalid_reason, "configured_origin_rule")
        self.assertEqual(evaluation.matched_signature, "origin_rule:exact:service temporarily warming up.")

    def test_configured_contains_origin_rule_is_not_evaluable(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="Please wait while our support team checks the system.",
                response_status="completed",
                target_type="adapter",
                transport_ok=True,
            ),
            origin_rules={"contains": ["support team checks"]},
        )

        self.assertEqual(evaluation.evaluation_validity, "not_evaluable")
        self.assertEqual(evaluation.invalid_reason, "configured_origin_rule")
        self.assertEqual(evaluation.matched_signature, "origin_rule:contains:support team checks")

    def test_configured_regex_origin_rule_is_not_evaluable(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="Please contact support at EXT-4455 for assistance.",
                response_status="completed",
                target_type="custom",
                transport_ok=True,
            ),
            origin_rules={"regex": [r"ext-\d{4}"]},
        )

        self.assertEqual(evaluation.evaluation_validity, "not_evaluable")
        self.assertEqual(evaluation.invalid_reason, "configured_origin_rule")
        self.assertEqual(evaluation.matched_signature, r"origin_rule:regex:ext-\d{4}")

    def test_configured_origin_rule_does_not_false_positive(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="I cannot comply with that request.",
                response_status="completed",
                target_type="openai_compatible",
                transport_ok=True,
            ),
            origin_rules={"contains": ["technical difficulties"]},
        )

        self.assertEqual(evaluation.evaluation_validity, "evaluable")
        self.assertEqual(evaluation.response_origin, "model")

    def test_error_prefix_is_not_evaluable(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="[ERROR] connect timeout",
                response_status="failed",
                target_type="openai_compatible",
                transport_ok=False,
            )
        )

        self.assertEqual(evaluation.evaluation_validity, "not_evaluable")
        self.assertEqual(evaluation.response_origin, "transport_error")

    def test_html_gateway_page_is_not_evaluable(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="<html><title>502 Bad Gateway</title></html>",
                response_status="completed",
                target_type="custom",
                transport_ok=True,
                content_type="text/html",
            )
        )

        self.assertEqual(evaluation.evaluation_validity, "not_evaluable")
        self.assertEqual(evaluation.invalid_reason, "html_error")

    def test_normal_refusal_stays_evaluable(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="I cannot comply with that request.",
                response_status="completed",
                target_type="openai_compatible",
                transport_ok=True,
            )
        )

        self.assertEqual(evaluation.evaluation_validity, "evaluable")
        self.assertEqual(evaluation.response_origin, "model")


    # ---------- Provenance protocol tests ----------

    def test_provenance_header_model_invoked_true(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="Sure, here is the answer.",
                response_status="completed",
                target_type="custom",
                transport_ok=True,
                http_status=200,
                transport_meta={
                    "provenance_headers": {
                        "model_invoked": True,
                        "post_processed": False,
                    }
                },
            )
        )
        self.assertEqual(evaluation.model_invoked, True)
        self.assertEqual(evaluation.post_processed, False)
        self.assertEqual(evaluation.provenance_source, "target_header")
        self.assertEqual(evaluation.response_origin, "model")
        self.assertEqual(evaluation.origin_confidence, "high")
        self.assertEqual(evaluation.evaluation_validity, "evaluable")

    def test_provenance_header_blocked(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="Request blocked by policy.",
                response_status="completed",
                target_type="custom",
                transport_ok=True,
                http_status=200,
                transport_meta={
                    "provenance_headers": {
                        "model_invoked": False,
                        "block_reason": "pre_guardrail",
                    }
                },
            )
        )
        self.assertEqual(evaluation.model_invoked, False)
        self.assertEqual(evaluation.block_reason, "pre_guardrail")
        self.assertEqual(evaluation.provenance_source, "target_header")
        self.assertEqual(evaluation.response_origin, "app_fallback")
        self.assertEqual(evaluation.evaluation_validity, "not_evaluable")
        self.assertEqual(evaluation.invalid_reason, "blocked_by_target")

    def test_provenance_header_post_processed(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="Your card ends in ****.",
                response_status="completed",
                target_type="custom",
                transport_ok=True,
                http_status=200,
                transport_meta={
                    "provenance_headers": {
                        "model_invoked": True,
                        "post_processed": True,
                        "post_reason": "pii_redaction",
                    }
                },
            )
        )
        self.assertEqual(evaluation.model_invoked, True)
        self.assertEqual(evaluation.post_processed, True)
        self.assertEqual(evaluation.post_reason, "pii_redaction")
        self.assertEqual(evaluation.provenance_source, "target_header")
        self.assertEqual(evaluation.response_origin, "app_fallback")
        self.assertEqual(evaluation.evaluation_validity, "evaluable")

    def test_provenance_body_field(self):
        import json
        body = json.dumps({
            "response": "Hello",
            "_provenance": {"model_invoked": True, "post_processed": False},
        })
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text=body,
                response_status="completed",
                target_type="custom",
                transport_ok=True,
                http_status=200,
            )
        )
        self.assertEqual(evaluation.model_invoked, True)
        self.assertEqual(evaluation.post_processed, False)
        self.assertEqual(evaluation.provenance_source, "target_body")
        self.assertEqual(evaluation.response_origin, "model")

    def test_provenance_header_overrides_heuristic(self):
        """Known-fallback text should be overridden by provenance header."""
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="I'm experiencing technical difficulties. Please contact our support line.",
                response_status="completed",
                target_type="custom",
                transport_ok=True,
                http_status=200,
                transport_meta={
                    "provenance_headers": {
                        "model_invoked": True,
                        "post_processed": False,
                    }
                },
            )
        )
        # Header says model was invoked → trust the header over the fallback signature
        self.assertEqual(evaluation.model_invoked, True)
        self.assertEqual(evaluation.provenance_source, "target_header")
        self.assertEqual(evaluation.response_origin, "model")
        self.assertEqual(evaluation.evaluation_validity, "evaluable")

    def test_structured_origin_rule_eq(self):
        import json
        body = json.dumps({
            "reply": "blocked",
            "guardrail": {"action": "INTERVENED"},
        })
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text=body,
                response_status="completed",
                target_type="custom",
                transport_ok=True,
                http_status=200,
            ),
            origin_rules={
                "structured": [
                    {
                        "field": "$.guardrail.action",
                        "op": "eq",
                        "value": "INTERVENED",
                        "mark": "blocked",
                        "reason": "pre_guardrail",
                        "label": "Guardrail intervened",
                    }
                ]
            },
        )
        self.assertEqual(evaluation.model_invoked, False)
        self.assertEqual(evaluation.block_reason, "pre_guardrail")
        self.assertEqual(evaluation.provenance_source, "origin_rule")
        self.assertEqual(evaluation.evaluation_validity, "not_evaluable")

    def test_structured_origin_rule_exists_marks_model(self):
        import json
        body = json.dumps({"reply": "hello", "meta": {"llm_model": "gpt-4o"}})
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text=body,
                response_status="completed",
                target_type="custom",
                transport_ok=True,
                http_status=200,
            ),
            origin_rules={
                "structured": [
                    {"field": "$.meta.llm_model", "op": "exists", "mark": "model"}
                ]
            },
        )
        self.assertEqual(evaluation.model_invoked, True)
        self.assertEqual(evaluation.post_processed, False)
        self.assertEqual(evaluation.provenance_source, "origin_rule")
        self.assertEqual(evaluation.evaluation_validity, "evaluable")

    def test_structured_origin_rule_no_match_falls_through(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="Normal model text response.",
                response_status="completed",
                target_type="custom",
                transport_ok=True,
                http_status=200,
            ),
            origin_rules={
                "structured": [
                    {"field": "$.guardrail.action", "op": "eq", "value": "INTERVENED", "mark": "blocked"}
                ]
            },
        )
        # No structured match, no provenance, custom target → Level 4 default
        self.assertIsNone(evaluation.model_invoked)
        self.assertEqual(evaluation.provenance_source, "none")
        self.assertEqual(evaluation.evaluation_validity, "evaluable")

    def test_backward_compat_derive_origin(self):
        """New fields correctly derive the legacy response_origin."""
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="Blocked.",
                response_status="completed",
                target_type="custom",
                transport_ok=True,
                http_status=200,
                transport_meta={
                    "provenance_headers": {"model_invoked": False, "block_reason": "rate_limit"}
                },
            )
        )
        # model_invoked=False → response_origin should be "app_fallback"
        self.assertEqual(evaluation.response_origin, "app_fallback")

    def test_no_provenance_custom_target_is_uncertain(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="Here is your account balance.",
                response_status="completed",
                target_type="custom",
                transport_ok=True,
                http_status=200,
            )
        )
        self.assertIsNone(evaluation.model_invoked)
        self.assertIsNone(evaluation.post_processed)
        self.assertEqual(evaluation.provenance_source, "none")
        self.assertEqual(evaluation.response_origin, "unknown")

    def test_direct_model_target_default_provenance(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="I can help with that.",
                response_status="completed",
                target_type="openai_compatible",
                transport_ok=True,
            )
        )
        self.assertEqual(evaluation.model_invoked, True)
        self.assertEqual(evaluation.post_processed, False)
        self.assertEqual(evaluation.provenance_source, "target_type_default")
        self.assertEqual(evaluation.response_origin, "model")

    def test_known_fallback_sets_provenance_fields(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="I'm experiencing technical difficulties. Please contact our support line.",
                response_status="completed",
                target_type="adapter",
                transport_ok=True,
            )
        )
        self.assertEqual(evaluation.model_invoked, False)
        self.assertEqual(evaluation.post_processed, False)
        self.assertEqual(evaluation.provenance_source, "known_fallback")

    def test_transport_error_sets_provenance_fields(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="",
                response_error="Connection refused",
                response_status="failed",
                target_type="custom",
                transport_ok=False,
            )
        )
        self.assertEqual(evaluation.model_invoked, False)
        self.assertEqual(evaluation.provenance_source, "heuristic")

    def test_empty_response_provenance(self):
        evaluation = screen_response_origin(
            TargetResponseEnvelope(
                response_text="",
                response_status="completed",
                target_type="custom",
                transport_ok=True,
                http_status=200,
            )
        )
        # Empty response: model_invoked is uncertain
        self.assertIsNone(evaluation.model_invoked)
        self.assertEqual(evaluation.provenance_source, "heuristic")
        self.assertEqual(evaluation.evaluation_validity, "not_evaluable")


if __name__ == "__main__":
    unittest.main()

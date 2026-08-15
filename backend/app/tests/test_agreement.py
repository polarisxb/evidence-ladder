import math
import unittest

from app.services.agreement import agreement_report, cohen_kappa, observed_agreement


class TestAgreement(unittest.TestCase):
    def test_perfect_agreement(self):
        a = ["success", "fail", "success", "fail"]
        self.assertEqual(observed_agreement(a, a), 1.0)
        self.assertEqual(cohen_kappa(a, a), 1.0)

    def test_chance_level_kappa_near_zero(self):
        # Independent labels with the same marginal distribution -> kappa ~ 0.
        a = ["s", "f", "s", "f", "s", "f", "s", "f"]
        b = ["s", "s", "f", "f", "s", "s", "f", "f"]
        self.assertTrue(abs(cohen_kappa(a, b)) < 1e-9)

    def test_known_value(self):
        # po = 0.75, pe = 0.5 -> kappa = 0.5
        a = ["y", "y", "n", "n"]
        b = ["y", "n", "n", "n"]
        self.assertTrue(math.isclose(cohen_kappa(a, b), 0.5, rel_tol=1e-9))

    def test_constant_labels(self):
        a = ["y", "y", "y"]
        b = ["y", "y", "y"]
        self.assertEqual(cohen_kappa(a, b), 1.0)
        c = ["y", "y", "y"]
        d = ["n", "n", "n"]
        self.assertEqual(cohen_kappa(c, d), 0.0)

    def test_report_and_validation(self):
        rep = agreement_report(["a", "b"], ["a", "c"])
        self.assertEqual(rep["n"], 2)
        self.assertEqual(rep["observed_agreement"], 0.5)
        with self.assertRaises(ValueError):
            observed_agreement(["a"], ["a", "b"])
        with self.assertRaises(ValueError):
            cohen_kappa([], [])


if __name__ == "__main__":
    unittest.main()

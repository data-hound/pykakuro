"""Tests for the v3 additions: families.py (generators) and verify.py (independent gates). Run from the repository root:
    PYTHONPATH=src python -m unittest test.test_v3 -v        (needs ortools for the verify/generate tests)
"""
import hashlib, json, logging, os, random, sys, unittest
logging.disable(logging.CRITICAL)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
from pykakuro import families as F, kakuro, verify
try:
    import ortools  # noqa: F401
    HAVE_ORTOOLS = True
except ImportError:
    HAVE_ORTOOLS = False


def fixture(name):
    with open(os.path.join(HERE, name)) as f:
        return json.load(f)


class TestFormat(unittest.TestCase):
    def test_roundtrip_matches_v2_strings(self):
        for fx in fixture("fixtures_v2_9x9.json"):
            W, d, n = F.from_strings(fx["puzzle"], fx["solution"])
            self.assertEqual(F.to_strings(W, d, n), (fx["puzzle"], fx["solution"]))

    def test_v2_generator_seed_regression(self):
        """gen_random(seed) reproduces the boards of the raw pool (seed >= 1) character for character."""
        for fx in fixture("fixtures_v2_seeds.json"):
            k = kakuro.gen_random(fx["size"], fx["size"], seed=fx["seed"], is_solved=False)
            p = kakuro.print_lol(k.data, k.x_size, center_cells=False)
            self.assertEqual(hashlib.sha256(p.encode()).hexdigest(), fx["sha256"], fx)

    def test_gen_random_leaves_global_rng_alone_and_seed0_is_deterministic(self):
        random.seed(123); a = random.random()
        random.seed(123); kakuro.gen_random(9, 9, seed=5, is_solved=False); b = random.random()
        self.assertEqual(a, b)
        s = lambda: kakuro.print_lol(kakuro.gen_random(9, 9, seed=0, is_solved=False).master_solution, 9, center_cells=False)
        self.assertEqual(s(), s())


@unittest.skipUnless(HAVE_ORTOOLS, "ortools not installed")
class TestVerify(unittest.TestCase):
    def test_v2_fixtures_pass_and_match_stored_difficulty(self):
        for fx in fixture("fixtures_v2_9x9.json"):
            r = verify.check_puzzle(fx["puzzle"], fx["solution"])
            self.assertTrue(r["passes"], r)
            self.assertAlmostEqual(r["prop_fixed_frac"], fx["prop"]); self.assertEqual(r["search_nodes"], fx["nodes"])

    def test_non_unique_puzzle_is_rejected(self):
        # 2x2 white block, every run sums to 4: solutions [[1,3],[3,1]] and [[3,1],[1,3]]
        W = [[False] * 3 for _ in range(3)]
        for r in (1, 2):
            for c in (1, 2): W[r][c] = True
        d = {(1, 1): 1, (1, 2): 3, (2, 1): 3, (2, 2): 1}
        p, s = F.to_strings(W, d, 3)
        r = verify.check_puzzle(p, s)
        self.assertEqual(r["cpsat_status"], "multiple"); self.assertFalse(r["passes"])
        self.assertEqual(r["own_status"], "multiple")

    def test_wrong_stored_solution_is_rejected(self):
        fx = fixture("fixtures_v2_9x9.json")[0]
        W, d, n = F.from_strings(fx["puzzle"], fx["solution"])
        p0 = next(iter(d)); d2 = dict(d); d2[p0] = d[p0] % 9 + 1       # change one digit, keep the puzzle
        _, s2 = F.to_strings(W, d2, n)
        r = verify.check_puzzle(fx["puzzle"], s2)
        self.assertFalse(r["passes"])


class TestLayouts(unittest.TestCase):
    def check_layout(self, W, n, max_run):
        self.assertFalse(any(W[0])); self.assertFalse(any(W[r][0] for r in range(n)))
        for r in range(1, n):
            for c in range(1, n):
                self.assertEqual(W[r][c], W[n - r][n - c], "180-degree symmetry")
        a, d = F.segments(W, n)
        self.assertTrue(all(2 <= len(s) <= max_run for s in a + d))
        self.assertTrue(F.connected(W, n))

    def test_symmetric_layout_invariants(self):
        for n in (9, 11, 15):
            ok = 0
            for seed in range(25):
                W = F.layout_sym(n, random.Random(seed), 0.62, 6, 0.45, 30)
                if W is None: continue
                ok += 1; self.check_layout(W, n, 6)
            self.assertGreater(ok, 15, f"layout success rate too low at n={n}")

    def test_rc_layout_respects_line_cap(self):
        for seed in range(15):
            W = F.layout_sym(11, random.Random(seed), 0.62, 6, 0.45, 30, line_cap=9)
            if W is None: continue
            self.assertTrue(all(sum(row) <= 9 for row in W)); self.assertTrue(all(sum(W[r][c] for r in range(11)) <= 9 for c in range(11)))


@unittest.skipUnless(HAVE_ORTOOLS, "ortools not installed")
class TestFamilies(unittest.TestCase):
    def first_ok(self, family, size, tries=60):
        for k in range(tries):
            r = F.generate(family, size, F.seed_for(family, size, k))
            if r["status"] == "ok": return r
        self.fail(f"no ok puzzle from {family} {size} in {tries} seeds")

    def test_deterministic(self):
        for fam in ("symrep_run", "symrep_rc", "blob_run"):
            seed = F.seed_for(fam, 9, 3)
            a, b = F.generate(fam, 9, seed), F.generate(fam, 9, seed)
            self.assertEqual(a, b)

    def test_generated_puzzles_pass_the_full_gate(self):
        for fam in ("symrep_run", "symrep_rc", "blob_run"):
            r = self.first_ok(fam, 9)
            self.assertTrue(verify.check_puzzle(r["puzzle"], r["solution"])["passes"], fam)

    def test_repaired_layouts_stay_symmetric_and_valid(self):
        for fam in ("symrep_run", "symrep_rc"):
            r = self.first_ok(fam, 9)
            W, d, n = F.from_strings(r["puzzle"], r["solution"])
            self.assertTrue(all(W[i][j] == W[n - i][n - j] for i in range(1, n) for j in range(1, n)), "180-degree symmetry after repair")
            self.assertTrue(F.connected(W, n))
            a, dn = F.segments(W, n)
            self.assertTrue(all(2 <= len(x) <= F.DEFAULTS["max_run"] for x in a + dn))

    def test_digit_rules(self):
        rc = self.first_ok("symrep_rc", 9); run = self.first_ok("symrep_run", 9)
        self.assertTrue(rc["meta"]["rowcol_distinct"])
        # run-only fills are allowed (not forced) to repeat digits across runs of a row/column; over many puzzles most do
        reps = [F.generate("symrep_run", 9, F.seed_for("symrep_run", 9, k)) for k in range(30)]
        oks = [r for r in reps if r["status"] == "ok"]
        self.assertTrue(oks and sum(not r["meta"]["rowcol_distinct"] for r in oks) / len(oks) > 0.8)
        for r in (rc, run):
            self.assertEqual(r["meta"]["min_run_len"] >= 2, True)

    def test_pack_seeds_regenerate_the_released_puzzles(self):
        """(family, size, k) -> sha256 of the puzzle recorded when the pack was built. The repair loop branches on which two solutions CP-SAT
        returns, so a different ortools version may regenerate different puzzles; this test makes that visible."""
        fx = fixture("fixtures_v3_seeds.json")
        import ortools
        for c in fx["cases"]:
            r = F.generate(c["family"], c["size"], F.seed_for(c["family"], c["size"], c["k"]))
            got = hashlib.sha256(r["puzzle"].encode()).hexdigest() if r["status"] == "ok" else r["status"]
            self.assertEqual(got, c["sha256"], f"{c}: fixtures were built with ortools {fx['ortools']}, installed {ortools.__version__}")

    def test_seed_ranges_are_disjoint(self):
        ranges = [(F.seed_for(f, s, 0), F.seed_for(f, s, 999_999)) for f in F.FAMILIES for s in (9, 11, 15)]
        ranges.sort()
        for (a0, a1), (b0, b1) in zip(ranges, ranges[1:]): self.assertLess(a1, b0)
        self.assertGreater(ranges[0][0], 3_200_000)    # above the v2 pool (0..549,999) and KK-Shift (2,000,000..3,199,999)


if __name__ == "__main__":
    unittest.main()

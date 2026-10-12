"""Tests for do-next's estimate script. Run from the repository root:

    python3 -m unittest discover -s plugins/do-next/tests
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.normpath(os.path.join(HERE, "..", "skills", "do-next", "scripts", "estimate.py"))
sys.path.insert(0, os.path.dirname(SCRIPT))

import estimate  # noqa: E402


def entry(estimate_min=None, actual_min=None, text="Do a thing.", stamp="[2026-10-12 10:00:00 -0400]"):
    lines = [stamp]
    if estimate_min is not None:
        lines.append(f"estimate: {estimate_min} min")
    if actual_min is not None:
        lines.append(f"actual: {actual_min} min")
    lines.append(text)
    return "\n".join(lines) + "\n--\n"


def done(*pairs):
    return "".join(entry(e, a) for e, a in pairs)


class History(unittest.TestCase):
    def test_complete_entries_are_read_in_order(self):
        text = done((10, 12), (20, 30))
        self.assertEqual(estimate.history(text), [(10, 12), (20, 30)])

    def test_incomplete_or_zero_entries_are_skipped(self):
        text = done((10, None), (None, 5), (0, 4), (10, 0), (15, 15)) + entry(text="old entry, no estimate")
        self.assertEqual(estimate.history(text), [(15, 15)])

    def test_the_window_is_the_last_thirty_tasks_before_filtering(self):
        text = done(*[(10, 99)] * 5) + done(*[(10, 10)] * 29) + entry(text="newest, incomplete")
        pairs = estimate.history(text)
        self.assertEqual(len(pairs), 29)
        self.assertTrue(all(p == (10, 10) for p in pairs))

    def test_section_lines_and_decision_lists_do_not_confuse_parsing(self):
        text = (entry(10, 20) + "# Features\n" + "[2026-10-12 11:00:00 -0400]\nestimate: 5 min\nactual: 5 min\n"
                "Second.\nDecisions taken without asking:\n- kept the old name\n--\n")
        self.assertEqual(estimate.history(text), [(10, 20), (5, 5)])

    def test_separators_with_trailing_space_and_crlf_still_split(self):
        text = entry(10, 20).replace("--\n", "--  \r\n") + entry(4, 8)
        self.assertEqual(estimate.history(text), [(10, 20), (4, 8)])

    def test_estimate_lines_in_prompt_text_outside_the_header_do_not_count(self):
        text = "[2026-10-12 10:00:00 -0400]\nWrite estimate: 5 min into the docs.\n--\n"
        self.assertEqual(estimate.history(text), [])


class Ratio(unittest.TestCase):
    def test_below_three_entries_there_is_no_adjustment(self):
        r = estimate.adjust([(10, 20), (10, 30)], 20)
        self.assertIsNone(r["adjusted"])
        self.assertEqual(r["used"], 2)

    def test_the_mean_ratio_multiplies_the_estimate(self):
        r = estimate.adjust([(10, 10), (10, 20), (10, 15)], 20)
        self.assertAlmostEqual(r["ratio"], 1.5)
        self.assertEqual(r["adjusted"], 30)
        self.assertEqual(r["discarded"], 0)

    def test_outliers_are_dropped_on_the_log_scale(self):
        pairs = [(10, 10), (10, 11), (10, 12), (10, 9), (10, 10), (10, 300)]
        r = estimate.adjust(pairs, 10)
        self.assertEqual(r["discarded"], 1)
        self.assertEqual(r["used"], 5)
        self.assertAlmostEqual(r["ratio"], (1.0 + 1.1 + 1.2 + 0.9 + 1.0) / 5)

    def test_a_very_fast_task_is_an_outlier_too(self):
        pairs = [(10, 10), (10, 11), (10, 12), (10, 9), (10, 10), (100, 1)]
        self.assertEqual(estimate.adjust(pairs, 10)["discarded"], 1)

    def test_with_three_ratios_nothing_is_discarded(self):
        r = estimate.adjust([(10, 10), (10, 10), (10, 500)], 10)
        self.assertEqual(r["discarded"], 0)
        self.assertEqual(r["used"], 3)

    def test_the_adjusted_estimate_is_whole_minutes_at_least_one(self):
        self.assertEqual(estimate.adjust([(100, 1), (100, 1), (100, 1)], 10)["adjusted"], 1)
        self.assertEqual(estimate.adjust([(3, 4), (3, 4), (3, 4)], 10)["adjusted"], 13)


class Elapsed(unittest.TestCase):
    def test_minutes_between_two_times(self):
        self.assertEqual(estimate.elapsed("2026-10-12 10:00:00 -0400", "2026-10-12 10:24:31 -0400", []), 25)

    def test_pauses_are_subtracted(self):
        pauses = [("2026-10-12 10:05:00 -0400", "2026-10-12 10:15:00 -0400"),
                  ("2026-10-12 10:20:00 -0400", "2026-10-12 10:22:00 -0400")]
        self.assertEqual(estimate.elapsed("2026-10-12 10:00:00 -0400", "2026-10-12 10:30:00 -0400", pauses), 18)

    def test_at_least_one_minute(self):
        self.assertEqual(estimate.elapsed("2026-10-12 10:00:00 -0400", "2026-10-12 10:00:10 -0400", []), 1)

    def test_time_zones_and_midnight(self):
        self.assertEqual(estimate.elapsed("2026-10-12 23:50:00 -0400", "2026-10-13 04:10:00 +0000", []), 20)

    def test_a_pause_that_ends_before_it_starts_is_an_error(self):
        with self.assertRaises(ValueError):
            estimate.elapsed("2026-10-12 10:00:00 -0400", "2026-10-12 10:30:00 -0400",
                             [("2026-10-12 10:20:00 -0400", "2026-10-12 10:10:00 -0400")])


class CommandLine(unittest.TestCase):
    def run_script(self, *args):
        proc = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    def write_done(self, text):
        fd, path = tempfile.mkstemp(suffix=".md")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.addCleanup(os.remove, path)
        return path

    def test_ratio_reports_raw_and_adjusted(self):
        path = self.write_done(done((10, 10), (10, 20), (10, 15)))
        code, out = self.run_script("ratio", path, "20")
        self.assertEqual(code, 0, out)
        self.assertIn("Estimate: 20 min. Adjusted from history: 30 min (ratio 1.50 from 3 tasks, 0 outliers discarded).", out)

    def test_ratio_says_when_history_is_too_short(self):
        path = self.write_done(done((10, 20)))
        code, out = self.run_script("ratio", path, "20")
        self.assertEqual(code, 0, out)
        self.assertIn("Estimate: 20 min. Not enough history to adjust yet (1 of 3 tasks needed).", out)

    def test_a_missing_done_file_is_no_history(self):
        code, out = self.run_script("ratio", "/nonexistent/DONE.md", "20")
        self.assertEqual(code, 0, out)
        self.assertIn("Not enough history to adjust yet (0 of 3 tasks needed)", out)

    def test_json_output(self):
        path = self.write_done(done((10, 10), (10, 20), (10, 15)))
        code, out = self.run_script("ratio", path, "20", "--json")
        data = json.loads(out)
        self.assertEqual((data["estimate"], data["adjusted"], data["used"]), (20, 30, 3))

    def test_elapsed_prints_minutes(self):
        code, out = self.run_script("elapsed", "2026-10-12 10:00:00 -0400", "2026-10-12 10:30:00 -0400",
                                    "2026-10-12 10:05:00 -0400", "2026-10-12 10:15:00 -0400")
        self.assertEqual((code, out.strip()), (0, "20"))

    def test_elapsed_needs_pauses_in_pairs(self):
        code, out = self.run_script("elapsed", "2026-10-12 10:00:00 -0400", "2026-10-12 10:30:00 -0400",
                                    "2026-10-12 10:05:00 -0400")
        self.assertNotEqual(code, 0)
        self.assertIn("pauses come in start and end pairs", out)

    def test_a_bad_estimate_is_refused(self):
        path = self.write_done("")
        for bad in ("0", "-5", "ten"):
            code, out = self.run_script("ratio", path, bad)
            self.assertNotEqual(code, 0, bad)


if __name__ == "__main__":
    unittest.main()

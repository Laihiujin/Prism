import importlib.util
import random
import unittest
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location("interval_schedule", Path(__file__).parents[1] / "fastapi_app/api/v1/publish/interval_schedule.py")
schedule = importlib.util.module_from_spec(spec)
spec.loader.exec_module(schedule)


class IntervalScheduleTest(unittest.TestCase):
    def test_global_accounts(self):
        tasks = [SimpleNamespace(file_index=f, account_index=a) for a in range(3) for f in range(2)]
        offsets = schedule.build_interval_offsets(tasks, "account_first", 60)
        self.assertEqual([offsets[(f, a)] for f in range(2) for a in range(3)], [0, 60, 120, 180, 240, 300])
        offsets = schedule.build_interval_offsets(tasks, "video_first", 60)
        self.assertEqual([offsets[(f, a)] for f in range(2) for a in range(3)], [0, 0, 0, 60, 60, 60])

    def test_sparse_assignments_and_jitter(self):
        tasks = [SimpleNamespace(file_index=f, account_index=a) for f, a in [(0, 0), (3, 1), (7, 2)]]
        self.assertEqual(list(schedule.build_interval_offsets(tasks, "account_first", 30).values()), [0, 30, 60])
        for seed in range(50):
            offsets = list(schedule.build_interval_offsets(tasks, "account_first", 30, 100, random.Random(seed)).values())
            self.assertEqual(offsets[0], 0)
            self.assertTrue(all(a < b for a, b in zip(offsets, offsets[1:])))

    def test_invalid_configuration(self):
        for mode, interval in [("unknown", 60), ("video_first", 0)]:
            with self.assertRaises(ValueError):
                schedule.build_interval_offsets([], mode, interval)


if __name__ == "__main__":
    unittest.main()

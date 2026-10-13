import unittest

from app.simulators import (bankers, cpu_compare, cpu_scheduling, deadlock_detection, dining_philosophers, disk_scheduling,
                            page_compare, page_replacement, paging, producer_consumer, segmentation, thread_lifecycle)

TEXTBOOK = [{"pid": "P1", "arrival": 0, "burst": 24}, {"pid": "P2", "arrival": 0, "burst": 3}, {"pid": "P3", "arrival": 0, "burst": 3}]
REFS = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]
QUEUE = [98, 183, 37, 122, 14, 124, 65, 67]


class CPU(unittest.TestCase):
    def test_fcfs_textbook(self):
        r = cpu_scheduling("FCFS", TEXTBOOK)
        self.assertEqual([m["waiting"] for m in r["metrics"]], [0, 24, 27])
        self.assertEqual(r["avg_waiting"], 17)

    def test_sjf_textbook(self):
        self.assertEqual(cpu_scheduling("SJF", TEXTBOOK)["avg_waiting"], 3)

    def test_round_robin_textbook(self):
        r = cpu_scheduling("Round Robin", TEXTBOOK, 4)
        self.assertEqual([m["waiting"] for m in r["metrics"]], [6, 4, 7])
        self.assertAlmostEqual(r["avg_waiting"], 17 / 3)
        self.assertEqual(r["makespan"], 30)

    def test_srtf_beats_sjf_on_arrivals(self):
        ps = [{"pid": "A", "arrival": 0, "burst": 8}, {"pid": "B", "arrival": 1, "burst": 4},
              {"pid": "C", "arrival": 2, "burst": 9}, {"pid": "D", "arrival": 3, "burst": 5}]
        self.assertAlmostEqual(cpu_scheduling("SRTF", ps)["avg_waiting"], 6.5)  # classic example
        self.assertAlmostEqual(cpu_scheduling("SJF", ps)["avg_waiting"], 7.75)

    def test_idle_gap_and_utilisation(self):
        r = cpu_scheduling("FCFS", [{"pid": "A", "arrival": 0, "burst": 2}, {"pid": "B", "arrival": 5, "burst": 2}])
        self.assertEqual([s["pid"] for s in r["timeline"]], ["A", "IDLE", "B"])
        self.assertAlmostEqual(r["cpu_utilization"], 4 / 7 * 100, places=1)

    def test_rr_arrival_enqueued_before_preempted(self):
        ps = [{"pid": "A", "arrival": 0, "burst": 4}, {"pid": "B", "arrival": 1, "burst": 2}]
        self.assertEqual([s["pid"] for s in cpu_scheduling("Round Robin", ps, 2)["timeline"]], ["A", "B", "A"])

    def test_priority_preemptive(self):
        ps = [{"pid": "A", "arrival": 0, "burst": 4, "priority": 3}, {"pid": "B", "arrival": 1, "burst": 2, "priority": 1}]
        self.assertEqual([s["pid"] for s in cpu_scheduling("Priority-P", ps)["timeline"]], ["A", "B", "A"])
        self.assertEqual([s["pid"] for s in cpu_scheduling("Priority", ps)["timeline"]], ["A", "B"])

    def test_validation(self):
        for bad in ([], [{"pid": "A", "burst": 0}], [{"pid": "A", "burst": 1}, {"pid": "A", "burst": 1}]):
            with self.assertRaises(ValueError):
                cpu_scheduling("FCFS", bad)
        with self.assertRaises(ValueError):
            cpu_scheduling("Nope", TEXTBOOK)

    def test_compare_lists_all(self):
        self.assertEqual(len(cpu_compare(TEXTBOOK, 4)["rows"]), 6)


class Paging(unittest.TestCase):
    def test_textbook_three_frames(self):
        self.assertEqual(page_replacement("FIFO", REFS, 3)["faults"], 15)
        self.assertEqual(page_replacement("LRU", REFS, 3)["faults"], 12)
        self.assertEqual(page_replacement("Optimal", REFS, 3)["faults"], 9)

    def test_belady(self):
        r = page_compare([1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5], 3)
        self.assertTrue(r["belady_anomaly"])
        by = {b["frames"]: b["faults"] for b in r["belady"]}
        self.assertEqual((by[3], by[4]), (9, 10))

    def test_clock_and_lfu_run(self):
        for alg in ("Clock", "LFU"):
            r = page_replacement(alg, REFS, 3)
            self.assertEqual(r["faults"] + r["hits"], len(REFS))
            self.assertGreaterEqual(r["faults"], 9)

    def test_slots_are_stable(self):
        steps = page_replacement("FIFO", [1, 2, 3, 4], 3)["steps"]
        self.assertEqual(steps[3]["frames"], [4, 2, 3])
        self.assertEqual(steps[3]["victim"], 1)

    def test_lru_old_test(self):
        self.assertEqual(page_replacement("LRU", [1, 2, 1, 3], 2)["faults"], 3)
        self.assertEqual(page_replacement("Optimal", [1, 2, 3, 1, 2, 4], 3)["faults"], 4)


class Banker(unittest.TestCase):
    ALLOC = [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]]
    MAX = [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]]

    def test_textbook_safe_sequence(self):
        r = bankers(self.ALLOC, self.MAX, [3, 3, 2])
        self.assertTrue(r["safe"])
        self.assertEqual(r["sequence"], [1, 3, 4, 0, 2])
        self.assertEqual(r["need"][0], [7, 4, 3])

    def test_request_granted_and_denied(self):
        ok = bankers(self.ALLOC, self.MAX, [3, 3, 2], {"process": 1, "vector": [1, 0, 2]})["request"]
        self.assertTrue(ok["granted"])
        self.assertEqual(ok["sequence_after"][0], 1)
        # Textbook follow-up: after P1's grant the state is Allocation P1=(3,0,2), Available=(2,3,0).
        alloc = [r[:] for r in self.ALLOC]
        alloc[1] = [3, 0, 2]
        unsafe = bankers(alloc, self.MAX, [2, 3, 0], {"process": 0, "vector": [0, 2, 0]})["request"]
        self.assertFalse(unsafe["granted"])
        self.assertIn("unsafe", unsafe["reason"])
        wait = bankers(alloc, self.MAX, [2, 3, 0], {"process": 4, "vector": [3, 3, 0]})["request"]
        self.assertIn("not available", wait["reason"])
        over = bankers(self.ALLOC, self.MAX, [3, 3, 2], {"process": 1, "vector": [5, 0, 0]})["request"]
        self.assertIn("exceeds", over["reason"])

    def test_unsafe_state(self):
        self.assertFalse(bankers([[0, 1, 0], [2, 0, 0], [3, 0, 2]], [[7, 5, 3], [3, 2, 2], [9, 0, 2]], [3, 3, 2])["safe"])

    def test_detection(self):
        r = deadlock_detection([[1, 0], [0, 1]], [[0, 1], [1, 0]], [0, 0])
        self.assertEqual(r["deadlocked"], [0, 1])
        with self.assertRaises(ValueError):
            bankers([[1, 2]], [[0, 0]], [1, 1])


class Disk(unittest.TestCase):
    def test_textbook_totals(self):
        t = {a: disk_scheduling(a, QUEUE, 53, 200, "up")["movement"] for a in ("FCFS", "SSTF", "SCAN", "C-SCAN", "LOOK", "C-LOOK")}
        self.assertEqual(t, {"FCFS": 640, "SSTF": 236, "SCAN": 331, "C-SCAN": 382, "LOOK": 299, "C-LOOK": 322})

    def test_scan_down_is_236(self):
        r = disk_scheduling("SCAN", QUEUE, 53, 200, "down")
        self.assertEqual(r["order"], [37, 14, 0, 65, 67, 98, 122, 124, 183])
        self.assertEqual(r["movement"], 236)

    def test_validation(self):
        with self.assertRaises(ValueError):
            disk_scheduling("FCFS", [500], 0, 200)


class Sync(unittest.TestCase):
    def test_producer_blocks_when_buffer_full(self):
        r = producer_consumer(3, 10, 1, 3)
        self.assertGreater(r["producer_blocked"], 0)
        self.assertLessEqual(r["peak_occupancy"], 3)
        self.assertEqual(sum(1 for e in r["events"] if e["action"] == "consume"), 10)

    def test_consumer_blocks_when_empty(self):
        self.assertGreater(producer_consumer(3, 5, 3, 1)["consumer_blocked"], 0)

    def test_naive_philosophers_deadlock(self):
        r = dining_philosophers(5, "naive")
        self.assertTrue(r["deadlock"])
        self.assertEqual(r["events"][-1]["action"], "deadlock")

    def test_safe_strategies_finish(self):
        for s in ("ordered", "asymmetric", "waiter"):
            r = dining_philosophers(5, s, 3)
            self.assertFalse(r["deadlock"], s)
            self.assertEqual(r["meals"], [3] * 5, s)

    def test_forks_never_shared(self):
        for e in dining_philosophers(5, "ordered")["events"]:
            holders = [f for f in e["forks"] if f is not None]
            self.assertEqual(len(holders), sum(1 for st in e["states"] if st == "eating") * 2 + sum(1 for st in e["states"] if st == "holding_first"))


class Memory(unittest.TestCase):
    def test_paging_translation_and_tlb(self):
        r = paging([10, 11, 22, 10], 4, 4, 2)
        self.assertEqual(r["rows"][0]["page"], 2)
        self.assertEqual(r["rows"][0]["offset"], 2)
        self.assertTrue(r["rows"][0]["fault"])
        self.assertEqual(r["rows"][1]["tlb"], "hit")
        self.assertEqual(r["offset_bits"], 2)
        for row in r["rows"]:
            self.assertEqual(row["physical"], row["frame"] * 4 + row["offset"])

    def test_paging_eviction(self):
        r = paging([0, 4, 8, 12], 4, 2, 0)
        self.assertEqual(r["faults"], 4)
        self.assertEqual(r["rows"][2]["victim_page"], 0)

    def test_segmentation(self):
        r = segmentation([{"base": 100, "limit": 50}, {"base": 1000, "limit": 30}],
                         [{"segment": 0, "offset": 20}, {"segment": 1, "offset": 30}, {"segment": 7, "offset": 0}])
        self.assertEqual([x["valid"] for x in r["rows"]], [True, False, False])
        self.assertEqual(r["rows"][0]["physical"], 120)
        self.assertIn("Segment fault", r["rows"][2]["reason"])

    def test_thread_lifecycle_ends_terminated(self):
        r = thread_lifecycle()
        self.assertEqual(set(r["trace"][-1]["states"].values()), {"TERMINATED"})
        for step in r["trace"]:
            self.assertLessEqual(sum(1 for s in step["states"].values() if s == "RUNNING"), 1)
        self.assertTrue(any("BLOCKED" in s["states"].values() for s in r["trace"]))


if __name__ == "__main__":
    unittest.main()

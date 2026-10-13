"""Deterministic Operating Systems simulators. Pure Python, no dependencies.

Every function validates its input (raising ValueError with a readable message) and returns a trace that
the UI can step through, plus summary metrics that match textbook results.
"""
from __future__ import annotations

from collections import deque

MAX_PROCESSES = 50
MAX_REFS = 500


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


# ----------------------------------------------------------------------------- CPU scheduling
CPU_ALGORITHMS = ["FCFS", "SJF", "SRTF", "Priority", "Priority-P", "Round Robin"]


def _processes(processes: list[dict]) -> list[dict]:
    _check(1 <= len(processes) <= MAX_PROCESSES, f"Provide between 1 and {MAX_PROCESSES} processes")
    out, seen = [], set()
    for p in processes:
        try:
            item = {"pid": str(p["pid"]), "arrival": int(p.get("arrival", 0)), "burst": int(p["burst"]),
                    "priority": int(p.get("priority", 0))}
        except (KeyError, TypeError, ValueError):
            raise ValueError("Each process needs pid, arrival, burst and priority as numbers") from None
        _check(item["burst"] > 0 and item["arrival"] >= 0, "Burst must be positive and arrival cannot be negative")
        _check(item["burst"] <= 1000 and item["arrival"] <= 1000, "Burst and arrival are limited to 1000")
        _check(item["pid"] not in seen, f"Duplicate process id {item['pid']}")
        seen.add(item["pid"])
        out.append(item)
    return out


def cpu_scheduling(algorithm: str, processes: list[dict], quantum: int = 2) -> dict:
    _check(algorithm in CPU_ALGORITHMS, f"Unsupported CPU algorithm. Choose one of: {', '.join(CPU_ALGORITHMS)}")
    _check(quantum >= 1, "Quantum must be at least 1")
    ps = _processes(processes)
    info = {p["pid"]: p for p in ps}
    rem = {p["pid"]: p["burst"] for p in ps}
    pending = sorted(ps, key=lambda p: (p["arrival"], p["pid"]))
    queue: list[str] = []
    first: dict[str, int] = {}
    finish: dict[str, int] = {}
    ticks: list[tuple[str, int]] = []  # (pid or IDLE, remaining after tick)
    current: str | None = None
    slice_left = 0
    t = 0

    def key(pid: str):
        p = info[pid]
        if algorithm == "SJF":
            return (p["burst"], p["arrival"], pid)
        if algorithm == "SRTF":
            return (rem[pid], p["arrival"], pid)
        if algorithm in ("Priority", "Priority-P"):
            return (p["priority"], p["arrival"], pid)
        return (p["arrival"], pid)

    def admit() -> None:
        while pending and pending[0]["arrival"] <= t:
            queue.append(pending.pop(0)["pid"])

    while len(finish) < len(ps):
        admit()
        if algorithm == "Round Robin":
            if current is None and queue:
                current, slice_left = queue.pop(0), quantum
        elif algorithm in ("SRTF", "Priority-P"):
            pool = queue + ([current] if current else [])
            if pool:
                best = min(pool, key=key)
                if best != current:
                    if current:
                        queue.append(current)
                    queue.remove(best)
                    current = best
        elif current is None and queue:
            current = min(queue, key=key)
            queue.remove(current)
        if current is None:
            ticks.append(("IDLE", 0))
            t += 1
            continue
        first.setdefault(current, t)
        rem[current] -= 1
        slice_left -= 1
        ticks.append((current, rem[current]))
        t += 1
        admit()  # arrivals during the slice queue before the preempted process (textbook convention)
        if rem[current] == 0:
            finish[current] = t
            current = None
        elif algorithm == "Round Robin" and slice_left == 0:
            queue.append(current)
            current = None

    timeline: list[dict] = []
    for i, (pid, left) in enumerate(ticks):
        if timeline and timeline[-1]["pid"] == pid:
            timeline[-1]["end"], timeline[-1]["remaining"] = i + 1, left
        else:
            timeline.append({"pid": pid, "start": i, "end": i + 1, "remaining": left})
    switches = sum(1 for a, b in zip(timeline, timeline[1:]) if a["pid"] != "IDLE" and b["pid"] != "IDLE")

    metrics = []
    for p in ps:
        tat = finish[p["pid"]] - p["arrival"]
        metrics.append({"pid": p["pid"], "arrival": p["arrival"], "burst": p["burst"], "completion": finish[p["pid"]],
                        "waiting": tat - p["burst"], "turnaround": tat, "response": first[p["pid"]] - p["arrival"]})
    n = len(metrics)
    busy = sum(1 for pid, _ in ticks if pid != "IDLE")
    return {
        "algorithm": algorithm, "timeline": timeline, "metrics": metrics,
        "avg_waiting": sum(m["waiting"] for m in metrics) / n,
        "avg_turnaround": sum(m["turnaround"] for m in metrics) / n,
        "avg_response": sum(m["response"] for m in metrics) / n,
        "cpu_utilization": round(100 * busy / len(ticks), 2), "throughput": round(n / len(ticks), 4),
        "context_switches": switches, "makespan": len(ticks),
        "complexity": "O(T * n) tick simulation, T = total time",
    }


def cpu_compare(processes: list[dict], quantum: int = 2) -> dict:
    rows = []
    for alg in CPU_ALGORITHMS:
        r = cpu_scheduling(alg, processes, quantum)
        rows.append({"algorithm": alg, "avg_waiting": round(r["avg_waiting"], 3),
                     "avg_turnaround": round(r["avg_turnaround"], 3), "avg_response": round(r["avg_response"], 3),
                     "context_switches": r["context_switches"]})
    return {"rows": rows, "best_waiting": min(rows, key=lambda r: r["avg_waiting"])["algorithm"]}


# ----------------------------------------------------------------------------- page replacement
PAGE_ALGORITHMS = ["FIFO", "LRU", "Optimal", "Clock", "LFU"]


def page_replacement(algorithm: str, refs: list[int], frames_n: int) -> dict:
    _check(algorithm in PAGE_ALGORITHMS, f"Unsupported page algorithm. Choose one of: {', '.join(PAGE_ALGORITHMS)}")
    _check(1 <= frames_n <= 20, "Frames must be between 1 and 20")
    _check(1 <= len(refs) <= MAX_REFS, f"Reference string must have 1 to {MAX_REFS} entries")
    _check(all(isinstance(r, int) and r >= 0 for r in refs), "Page numbers must be non-negative integers")
    frames: list[int | None] = [None] * frames_n
    loaded_at = [0] * frames_n
    last_used = [0] * frames_n
    counts = [0] * frames_n
    ref_bit = [0] * frames_n
    fifo_ptr = hand = faults = 0
    steps = []
    for i, page in enumerate(refs):
        victim = None
        slot = frames.index(page) if page in frames else -1
        hit = slot >= 0
        if hit:
            last_used[slot] = i
            counts[slot] += 1
            ref_bit[slot] = 1
        else:
            faults += 1
            free = frames.index(None) if None in frames else -1
            if free >= 0:
                slot = free
            elif algorithm == "FIFO":
                slot = fifo_ptr
                fifo_ptr = (fifo_ptr + 1) % frames_n
            elif algorithm == "LRU":
                slot = min(range(frames_n), key=lambda s: (last_used[s], s))
            elif algorithm == "LFU":
                slot = min(range(frames_n), key=lambda s: (counts[s], loaded_at[s], s))
            elif algorithm == "Optimal":
                future = refs[i + 1:]
                slot = max(range(frames_n), key=lambda s: (future.index(frames[s]) if frames[s] in future else 10 ** 9, -s))
            else:  # Clock / second chance
                while ref_bit[hand] == 1:
                    ref_bit[hand] = 0
                    hand = (hand + 1) % frames_n
                slot = hand
                hand = (hand + 1) % frames_n
            victim = frames[slot]
            frames[slot] = page
            loaded_at[slot] = last_used[slot] = i
            counts[slot] = 1
            ref_bit[slot] = 1
        steps.append({"index": i, "reference": page, "frames": frames.copy(), "hit": hit, "fault": not hit,
                      "victim": victim, "slot": slot, "ref_bits": ref_bit.copy() if algorithm == "Clock" else None})
    return {"algorithm": algorithm, "frames": frames_n, "faults": faults, "hits": len(refs) - faults,
            "fault_rate": faults / len(refs), "hit_ratio": (len(refs) - faults) / len(refs), "steps": steps,
            "complexity": "O(m * n) for m references and n frames"}


def page_compare(refs: list[int], frames_n: int) -> dict:
    rows = [{"algorithm": a, "faults": page_replacement(a, refs, frames_n)["faults"]} for a in PAGE_ALGORITHMS]
    belady = [{"frames": f, "faults": page_replacement("FIFO", refs, f)["faults"]} for f in range(1, 8)]
    anomaly = any(b["faults"] > a["faults"] for a, b in zip(belady, belady[1:]))
    return {"rows": rows, "belady": belady, "belady_anomaly": anomaly}


# ----------------------------------------------------------------------------- Banker's / deadlock
def _matrix(name: str, m: list[list[int]], cols: int | None = None) -> None:
    _check(len(m) > 0 and all(isinstance(r, list) and len(r) > 0 for r in m), f"{name} must be a non-empty matrix")
    _check(len({len(r) for r in m}) == 1, f"{name} rows must all have the same length")
    _check(cols is None or len(m[0]) == cols, f"{name} must have {cols} columns")
    _check(all(isinstance(x, int) and x >= 0 for r in m for x in r), f"{name} must contain non-negative integers")


def _safety(allocation, need, available):
    n, m = len(allocation), len(available)
    work, finish, seq, steps = available[:], [False] * n, [], []
    progress = True
    while progress:
        progress = False
        for i in range(n):
            if not finish[i] and all(need[i][j] <= work[j] for j in range(m)):
                before = work[:]
                work = [work[j] + allocation[i][j] for j in range(m)]
                finish[i] = True
                seq.append(i)
                steps.append({"process": i, "need": need[i][:], "work_before": before, "work_after": work[:]})
                progress = True
    return all(finish), seq, steps, work


def bankers(allocation, maximum, available, request: dict | None = None) -> dict:
    _matrix("Allocation", allocation)
    m = len(allocation[0])
    _matrix("Maximum", maximum, m)
    _check(len(maximum) == len(allocation), "Allocation and Maximum need the same number of processes")
    _check(len(available) == m and all(isinstance(x, int) and x >= 0 for x in available), "Available must match resource count")
    n = len(allocation)
    _check(all(maximum[i][j] >= allocation[i][j] for i in range(n) for j in range(m)), "Maximum cannot be below Allocation")
    need = [[maximum[i][j] - allocation[i][j] for j in range(m)] for i in range(n)]
    safe, seq, steps, work = _safety(allocation, need, available)
    result = {"safe": safe, "sequence": seq, "need": need, "work": work, "steps": steps, "complexity": "O(n^2 * m)"}
    if request:
        i, vec = int(request.get("process", -1)), list(request.get("vector", []))
        _check(0 <= i < n and len(vec) == m and all(isinstance(x, int) and x >= 0 for x in vec), "Invalid resource request")
        verdict = {"process": i, "vector": vec, "granted": False, "reason": "", "sequence_after": []}
        if any(vec[j] > need[i][j] for j in range(m)):
            verdict["reason"] = "Request exceeds the process's declared maximum need"
        elif any(vec[j] > available[j] for j in range(m)):
            verdict["reason"] = "Resources are not available yet, so the process must wait"
        else:
            a2 = [row[:] for row in allocation]
            n2 = [row[:] for row in need]
            av2 = [available[j] - vec[j] for j in range(m)]
            for j in range(m):
                a2[i][j] += vec[j]
                n2[i][j] -= vec[j]
            ok, s2, _, _ = _safety(a2, n2, av2)
            verdict["granted"] = ok
            verdict["sequence_after"] = s2 if ok else []
            verdict["reason"] = "Granting leaves the system in a safe state" if ok else "Granting would leave an unsafe state"
        result["request"] = verdict
    return result


def deadlock_detection(allocation, request, available) -> dict:
    _matrix("Allocation", allocation)
    m = len(allocation[0])
    _matrix("Request", request, m)
    _check(len(request) == len(allocation) and len(available) == m, "Matrix dimensions mismatch")
    ok, seq, steps, _ = _safety(allocation, request, available)
    finished = set(seq)
    return {"deadlocked": [i for i in range(len(allocation)) if i not in finished], "safe": ok,
            "sequence": seq, "steps": steps}


# ----------------------------------------------------------------------------- disk scheduling
DISK_ALGORITHMS = ["FCFS", "SSTF", "SCAN", "C-SCAN", "LOOK", "C-LOOK"]


def disk_scheduling(algorithm: str, requests: list[int], head: int, disk_size: int = 200, direction: str = "up") -> dict:
    _check(algorithm in DISK_ALGORITHMS, f"Unsupported disk algorithm. Choose one of: {', '.join(DISK_ALGORITHMS)}")
    _check(direction in ("up", "down"), "Direction must be 'up' or 'down'")
    _check(disk_size >= 2 and 0 <= head < disk_size, "Head must lie inside the disk")
    _check(1 <= len(requests) <= MAX_REFS and all(0 <= x < disk_size for x in requests), "Disk request outside range")
    flip = direction == "down" and algorithm not in ("FCFS", "SSTF")
    mirror = (lambda x: disk_size - 1 - x) if flip else (lambda x: x)
    reqs, h = [mirror(x) for x in requests], mirror(head)
    left, right = sorted(x for x in reqs if x < h), sorted(x for x in reqs if x >= h)
    if algorithm == "FCFS":
        order = list(reqs)
    elif algorithm == "SSTF":
        rem, cur, order = list(reqs), h, []
        while rem:
            x = min(rem, key=lambda v: (abs(v - cur), v))
            order.append(x)
            rem.remove(x)
            cur = x
    elif algorithm == "SCAN":
        order = right + [disk_size - 1] + left[::-1]
    elif algorithm == "C-SCAN":
        order = right + [disk_size - 1, 0] + left
    elif algorithm == "LOOK":
        order = right + left[::-1]
    else:  # C-LOOK
        order = right + left
    order = [mirror(x) for x in order]
    cur, movement, segments, path = head, 0, [], [head]
    for x in order:
        segments.append({"from": cur, "to": x, "distance": abs(x - cur)})
        movement += abs(x - cur)
        cur = x
        path.append(x)
    return {"algorithm": algorithm, "direction": direction, "order": order, "movement": movement, "segments": segments,
            "path": path, "average_seek": round(movement / len(requests), 3), "disk_size": disk_size,
            "complexity": "O(n)" if algorithm == "FCFS" else "O(n log n)"}


# ----------------------------------------------------------------------------- synchronisation
def producer_consumer(size: int, items: int, producer_period: int = 1, consumer_period: int = 2) -> dict:
    _check(1 <= size <= 20 and 1 <= items <= 100, "Buffer size 1-20 and items 1-100")
    _check(1 <= producer_period <= 10 and 1 <= consumer_period <= 10, "Periods must be between 1 and 10")
    buf: list[int] = []
    empty, full = size, 0
    produced = consumed = tick = blocked_p = blocked_c = peak = 0
    events = []

    def log(actor, action, item, note):
        events.append({"tick": tick, "actor": actor, "action": action, "item": item, "buffer": buf.copy(),
                       "empty": empty, "full": full, "note": note})

    while consumed < items and tick < 5000:
        tick += 1
        if produced < items and tick % producer_period == 0:
            if empty == 0:
                blocked_p += 1
                log("producer", "blocked", None, "wait(empty) blocks: the buffer is full")
            else:
                empty -= 1
                produced += 1
                buf.append(produced)
                full += 1
                peak = max(peak, len(buf))
                log("producer", "produce", produced, "wait(empty); wait(mutex); insert; signal(mutex); signal(full)")
        if consumed < items and tick % consumer_period == 0:
            if full == 0:
                blocked_c += 1
                log("consumer", "blocked", None, "wait(full) blocks: the buffer is empty")
            else:
                full -= 1
                item = buf.pop(0)
                consumed += 1
                empty += 1
                log("consumer", "consume", item, "wait(full); wait(mutex); remove; signal(mutex); signal(empty)")
    return {"events": events, "buffer_size": size, "items": items, "ticks": tick, "peak_occupancy": peak,
            "producer_blocked": blocked_p, "consumer_blocked": blocked_c,
            "model": "bounded-buffer with counting semaphores empty/full and a mutex"}


PHILOSOPHER_STRATEGIES = ["naive", "ordered", "asymmetric", "waiter"]


def dining_philosophers(n: int = 5, strategy: str = "naive", meals: int = 2) -> dict:
    _check(2 <= n <= 8 and 1 <= meals <= 5, "Philosophers 2-8 and meals 1-5")
    _check(strategy in PHILOSOPHER_STRATEGIES, f"Strategy must be one of: {', '.join(PHILOSOPHER_STRATEGIES)}")
    forks: list[int | None] = [None] * n
    state = ["thinking"] * n
    eaten = [0] * n
    eat_left = [0] * n
    seated = [False] * n
    seats_used = 0
    events: list[dict] = []
    step = 0

    def order(i: int) -> tuple[int, int]:
        left, right = i, (i + 1) % n
        if strategy == "ordered":
            return (min(left, right), max(left, right))
        if strategy == "asymmetric" and i % 2 == 1:
            return (right, left)
        return (left, right)

    def log(i: int, action: str, note: str) -> None:
        events.append({"step": step, "philosopher": i, "action": action, "note": note, "forks": forks.copy(),
                       "states": state.copy(), "meals": eaten.copy()})

    deadlock_at = None
    for rnd in range(1, 400):
        progressed = False
        for i in range(n):
            first, second = order(i)
            s = state[i]
            if s == "done":
                continue
            if s == "thinking":
                step += 1
                state[i] = "hungry"
                log(i, "hungry", f"P{i} gets hungry")
                progressed = True
            elif s == "hungry":
                if strategy == "waiter" and not seated[i]:
                    if seats_used < n - 1:
                        seats_used += 1
                        seated[i] = True
                        step += 1
                        log(i, "sit", f"The waiter seats P{i} ({seats_used}/{n - 1} seats used)")
                        progressed = True
                    continue
                if forks[first] is None:
                    forks[first] = i
                    state[i] = "holding_first"
                    step += 1
                    log(i, "pick_first", f"P{i} picks up fork {first}")
                    progressed = True
            elif s == "holding_first":
                if forks[second] is None:
                    forks[second] = i
                    state[i], eat_left[i] = "eating", 2
                    step += 1
                    log(i, "pick_second", f"P{i} picks up fork {second} and starts eating")
                    progressed = True
            elif s == "eating":
                progressed = True  # time passes while eating, so this is not a stall
                eat_left[i] -= 1
                if eat_left[i] == 0:
                    forks[first] = forks[second] = None
                    eaten[i] += 1
                    state[i] = "done" if eaten[i] >= meals else "thinking"
                    if strategy == "waiter":
                        seated[i], seats_used = False, seats_used - 1
                    step += 1
                    log(i, "release", f"P{i} puts both forks down (meal {eaten[i]})")
                    progressed = True
        if all(x == "done" for x in state):
            break
        if not progressed:
            deadlock_at = step
            events.append({"step": step + 1, "philosopher": -1, "action": "deadlock",
                           "note": "Every philosopher holds one fork and waits for another: circular wait",
                           "forks": forks.copy(), "states": state.copy(), "meals": eaten.copy()})
            break
    notes = {
        "naive": "Everyone picks the left fork first, so all five can hold one fork each and wait forever.",
        "ordered": "Forks are numbered and always taken lowest first, which breaks circular wait.",
        "asymmetric": "Odd philosophers reach right first, so the chain of waiting cannot close into a circle.",
        "waiter": "At most n-1 philosophers may sit, so at least one can always get both forks.",
    }
    return {"strategy": strategy, "n": n, "events": events[:800], "deadlock": deadlock_at is not None,
            "deadlock_at": deadlock_at, "meals": eaten, "explanation": notes[strategy], "deadlock_free_ordered": strategy != "naive"}


# ----------------------------------------------------------------------------- address translation
def paging(addresses: list[int], page_size: int = 4, num_frames: int = 4, tlb_size: int = 2) -> dict:
    _check(page_size >= 1 and 1 <= num_frames <= 64 and 0 <= tlb_size <= 16, "Invalid page size, frames or TLB size")
    _check(1 <= len(addresses) <= 200 and all(isinstance(a, int) and a >= 0 for a in addresses), "Provide 1-200 non-negative addresses")
    table: dict[int, int] = {}
    frames: list[int | None] = [None] * num_frames
    fifo: deque[int] = deque()
    tlb: deque[int] = deque()
    rows, faults, tlb_hits = [], 0, 0
    for a in addresses:
        page, offset = divmod(a, page_size)
        victim, fault = None, False
        in_tlb = page in tlb
        if in_tlb:
            tlb_hits += 1
        if page not in table:
            fault = True
            faults += 1
            if None in frames:
                frame = frames.index(None)
            else:
                victim = fifo.popleft()
                frame = table.pop(victim)
                if victim in tlb:
                    tlb.remove(victim)
            frames[frame] = page
            table[page] = frame
            fifo.append(page)
        frame = table[page]
        if not in_tlb and tlb_size:
            if len(tlb) >= tlb_size:
                tlb.popleft()
            tlb.append(page)
        rows.append({"logical": a, "page": page, "offset": offset, "tlb": "hit" if in_tlb else "miss", "fault": fault,
                     "frame": frame, "physical": frame * page_size + offset, "victim_page": victim,
                     "page_table": {str(k): v for k, v in sorted(table.items())}, "tlb_state": list(tlb)})
    bits = page_size.bit_length() - 1 if page_size & (page_size - 1) == 0 else None
    return {"rows": rows, "faults": faults, "tlb_hits": tlb_hits, "tlb_hit_ratio": round(tlb_hits / len(addresses), 3),
            "offset_bits": bits, "formula": "page = address div page_size, offset = address mod page_size, physical = frame * page_size + offset"}


def segmentation(segments: list[dict], logical: list[dict]) -> dict:
    _check(1 <= len(segments) <= 16 and len(logical) >= 1, "Provide segments and at least one logical address")
    rows = []
    for x in logical:
        seg, off = int(x.get("segment", 0)), int(x.get("offset", 0))
        if not 0 <= seg < len(segments):
            rows.append({"segment": seg, "offset": off, "base": None, "limit": None, "valid": False,
                         "physical": None, "reason": "Segment fault: no such segment"})
            continue
        s = segments[seg]
        base, limit = int(s["base"]), int(s["limit"])
        valid = 0 <= off < limit
        rows.append({"segment": seg, "offset": off, "base": base, "limit": limit, "valid": valid,
                     "physical": base + off if valid else None,
                     "reason": "Valid: offset is below the limit" if valid else "Trap: offset is not below the limit"})
    return {"rows": rows, "rule": "physical = base + offset when 0 <= offset < limit, otherwise the hardware traps"}


# ----------------------------------------------------------------------------- threads
THREAD_STATES = ["NEW", "READY", "RUNNING", "BLOCKED", "TERMINATED"]
THREAD_TRANSITIONS = [("NEW", "READY"), ("READY", "RUNNING"), ("RUNNING", "READY"), ("RUNNING", "BLOCKED"),
                      ("BLOCKED", "READY"), ("RUNNING", "TERMINATED")]
DEFAULT_THREADS = {"A": [("cpu", 3), ("io", 2), ("cpu", 2)], "B": [("cpu", 2), ("io", 1), ("cpu", 3)], "C": [("cpu", 4)]}


def thread_lifecycle(scenario: dict | None = None, quantum: int = 2) -> dict:
    scen = scenario or DEFAULT_THREADS
    _check(1 <= len(scen) <= 6 and quantum >= 1, "Provide 1-6 threads and a positive quantum")
    bursts = {k: [(str(kind), int(n)) for kind, n in v] for k, v in scen.items()}
    _check(all(b and all(kind in ("cpu", "io") and n > 0 for kind, n in b) for b in bursts.values()), "Bursts must be cpu/io with positive length")
    st = {k: "NEW" for k in bursts}
    trace = [{"t": 0, "states": dict(st)}]
    ready: list[str] = []
    cur, left_slice, t = None, 0, 0
    io_left: dict[str, int] = {}
    for k in bursts:
        st[k] = "READY"
        ready.append(k)
    while any(s != "TERMINATED" for s in st.values()) and t < 500:
        if cur is None and ready:
            cur, left_slice = ready.pop(0), quantum
            st[cur] = "RUNNING"
        t += 1
        trace.append({"t": t, "states": dict(st)})
        woke = []
        for k in list(io_left):
            io_left[k] -= 1
            if io_left[k] == 0:
                del io_left[k]
                bursts[k].pop(0)
                if bursts[k]:
                    st[k] = "READY"
                    woke.append(k)
                else:
                    st[k] = "TERMINATED"
        if cur:
            kind, n = bursts[cur][0]
            bursts[cur][0] = (kind, n - 1)
            left_slice -= 1
            if n - 1 == 0:
                bursts[cur].pop(0)
                if not bursts[cur]:
                    st[cur], cur = "TERMINATED", None
                elif bursts[cur][0][0] == "io":
                    st[cur], io_left[cur], cur = "BLOCKED", bursts[cur][0][1], None
                elif left_slice == 0:
                    st[cur] = "READY"
                    woke.append(cur)
                    cur = None
            elif left_slice == 0:
                st[cur] = "READY"
                woke.append(cur)
                cur = None
        ready.extend(woke)
    trace.append({"t": t + 1, "states": dict(st)})
    return {"states": THREAD_STATES, "transitions": [list(x) for x in THREAD_TRANSITIONS], "threads": list(bursts),
            "trace": trace, "quantum": quantum}

# Page Replacement

## Demand paging and page faults
In demand paging a page is brought into memory only when it is first referenced. A page fault occurs when a referenced page is marked invalid in the page table. The handler finds the page on disk, finds a free frame (or chooses a victim page), reads the page into the frame, updates the page table and restarts the instruction. With page fault rate p, memory access time m and page fault service time s, the effective access time is EAT = (1 - p) * m + p * s. Because s is millions of times larger than m, p must be extremely small.

## FIFO page replacement
FIFO evicts the page that has been in memory the longest. It is easy to implement with a queue but it ignores how often a page is used. FIFO can suffer from Belady's anomaly: for some reference strings, giving the process more frames increases the number of page faults. Stack algorithms such as LRU and Optimal never show this anomaly.

## Optimal page replacement
Optimal (OPT or MIN) evicts the page that will not be used for the longest time in the future. It gives the lowest possible fault rate for a fixed number of frames but cannot be implemented because the future is unknown, so it is used as a benchmark for other algorithms.

## LRU page replacement
Least Recently Used evicts the page that has not been used for the longest time, approximating OPT by looking backwards instead of forwards. It can be implemented with a counter or timestamp stored per page, or with a stack of page numbers moved to the top on every reference. Both need hardware help on every memory access, so real systems use approximations.

## Clock and second chance
The clock (second chance) algorithm approximates LRU using a reference bit and a circular list of frames. The hand moves around: if the reference bit is 1 it is cleared and the page gets a second chance, and if it is 0 the page is replaced. The enhanced version also considers the modify (dirty) bit and prefers pages that are both unreferenced and clean because evicting them needs no disk write.

## Counting algorithms
LFU replaces the page with the smallest reference count and MFU replaces the page with the largest count on the argument that the page with the smallest count was probably just brought in. Neither is common in practice.

## Worked example with three frames
For the reference string 7,0,1,2,0,3,0,4,2,3,0,3,2,1,2,0,1,7,0,1 with 3 frames, FIFO causes 15 page faults, LRU causes 12 and Optimal causes 9.

## Frame allocation and thrashing
Frames can be allocated equally, proportionally to process size or by priority, and replacement can be global (any frame) or local (only the process's own frames). Thrashing happens when a process does not have enough frames for its working set, so it spends more time paging than executing and CPU utilisation collapses. The working-set model keeps the pages used in the last delta references resident, and the page-fault-frequency scheme adds or removes frames to keep the fault rate between an upper and a lower bound.

# Disk Scheduling

## Disk access time
The time to read from a hard disk is seek time (moving the head to the right cylinder) plus rotational latency (waiting for the sector to rotate under the head) plus transfer time. Seek time dominates, so disk scheduling algorithms reorder pending requests to reduce total head movement. The examples below use the request queue 98, 183, 37, 122, 14, 124, 65, 67 on a disk with cylinders 0 to 199 and the head at 53.

## FCFS and SSTF
FCFS serves requests in arrival order. It is fair but can cause wild swings; for the example queue the total head movement is 640 cylinders. Shortest Seek Time First (SSTF) always serves the pending request closest to the current head position. It greatly reduces movement, 236 cylinders for the example, but it can starve requests far from the head, much like SJF.

## SCAN (elevator)
SCAN moves the head in one direction serving requests until it reaches the end of the disk and then reverses. If the head first moves toward cylinder 0 the order is 37, 14, 0, 65, 67, 98, 122, 124, 183 and the total movement is 236. If it first moves toward the high end, it goes up to 199 and back down to 14 for a total of 331. Requests just behind the head wait for a full sweep, but starvation is avoided.

## C-SCAN
Circular SCAN moves in one direction only. After reaching the last cylinder it returns directly to cylinder 0 without serving requests on the way back, and then sweeps upward again. This gives more uniform waiting times than SCAN. For the example, moving up, the head goes 53 to 199, jumps to 0 and then serves 14 and 37, giving a total of 382 cylinders when the return jump is counted.

## LOOK and C-LOOK
LOOK and C-LOOK are practical variants of SCAN and C-SCAN: the head only travels as far as the last request in each direction instead of the physical end of the disk. For the example LOOK moving up covers 299 cylinders, and C-LOOK moving up covers 322 cylinders when the jump from 183 back to 14 is counted.

## Choosing an algorithm
SSTF or LOOK work well under light to moderate load, while SCAN-style algorithms perform better under heavy load because they cannot starve requests. Solid-state drives have no moving head, so seek-based scheduling gives little benefit and simple policies such as noop or deadline queues are used instead.

# Process Synchronization

## Race conditions and the critical section
A race condition occurs when the result of a computation depends on the order in which concurrent processes access shared data. The part of the code that accesses shared data is the critical section. A correct solution must provide three properties: mutual exclusion (only one process in its critical section), progress (if no process is inside, one of the waiting processes must be allowed in without indefinite postponement) and bounded waiting (a limit on how many times others may enter before a waiting process gets in).

## Peterson's solution and hardware support
Peterson's algorithm solves the two-process critical-section problem in software using a shared turn variable and a flag array. On modern CPUs with instruction reordering it needs memory barriers, so real systems use atomic hardware instructions such as test-and-set and compare-and-swap. These read and modify a memory word in one indivisible step and are the building blocks for locks.

## Mutex locks and spinlocks
A mutex has acquire and release operations that protect a critical section. A spinlock busy-waits in a loop until the lock is free; it wastes CPU but avoids a context switch, so it suits very short critical sections on multiprocessors. A sleeping mutex puts the waiting thread to sleep and is better when the lock may be held for longer.

## Semaphores
A semaphore is an integer with two atomic operations. wait (P) decrements the value and blocks if the result would be negative; signal (V) increments it and wakes a waiting process. A binary semaphore (0 or 1) works like a mutex, while a counting semaphore controls access to a pool of identical resources. Misuse causes problems: swapping the order of wait calls can cause deadlock, and forgetting a signal can block processes forever.

## Producer-consumer (bounded buffer)
A producer adds items to a buffer of size N and a consumer removes them. The classic solution uses three semaphores: empty initialised to N counts free slots, full initialised to 0 counts filled slots, and mutex initialised to 1 protects the buffer. The producer does wait(empty), wait(mutex), adds the item, signal(mutex), signal(full). The consumer does wait(full), wait(mutex), removes the item, signal(mutex), signal(empty). The order of waiting on empty or full before the mutex matters: taking the mutex first can deadlock.

## Readers-writers problem
Many readers may read shared data at the same time, but a writer needs exclusive access. In the first readers-writers variant readers have priority, which can starve writers; the second gives writers priority, which can starve readers. Solutions use a mutex-protected reader count and a semaphore that writers hold.

## Dining philosophers
Five philosophers sit around a table with one fork between each pair and need two forks to eat. If every philosopher picks up the left fork at the same time, nobody can get the right fork and the system deadlocks. Remedies include allowing at most four philosophers to sit, picking up both forks atomically, using an asymmetric rule where odd philosophers take the left fork first and even philosophers take the right first, or numbering the forks and always acquiring the lower-numbered one first (resource ordering).

## Monitors and condition variables
A monitor is a language-level construct in which only one thread can be active inside at a time. Condition variables inside a monitor provide wait and signal so a thread can sleep until a condition becomes true. Java synchronized methods and POSIX mutex plus condition variable follow this pattern.

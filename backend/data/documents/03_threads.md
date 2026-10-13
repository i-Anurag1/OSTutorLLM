# Threads and Concurrency

## Thread versus process
A thread is a unit of CPU execution inside a process. Threads of one process share the code, data, heap, open files and address space, but each thread has its own program counter, registers and stack. Creating a thread and switching between threads is cheaper than for processes because no address-space switch is needed. Threads communicate through shared memory, which is fast but requires synchronisation to avoid race conditions.

## Benefits of multithreading
Multithreading improves responsiveness (a UI thread stays alive while a worker blocks), allows resource sharing without explicit IPC, reduces creation and switching cost compared with processes, and lets a program exploit multiple cores. The main costs are the complexity of synchronisation and the fact that one faulty thread can corrupt memory shared by the whole process.

## User threads and kernel threads
User-level threads are managed by a library in user space; the kernel is unaware of them, so switching is very fast but a blocking system call from one thread blocks the whole process and they cannot run on several cores. Kernel threads are managed by the OS, so they can run in parallel on different cores and one can block without blocking the others, at the price of a system call for every operation.

## Multithreading models
The many-to-one model maps many user threads onto one kernel thread, so there is no parallelism. The one-to-one model maps each user thread to a kernel thread, which is used by Linux and Windows and gives full parallelism but limits the number of threads. The many-to-many model multiplexes many user threads onto a smaller or equal number of kernel threads and gives flexibility with more complex scheduling.

## Creating processes and threads on Linux
The fork system call creates a child process that is a copy of the parent. It returns 0 in the child and the child's process ID in the parent. The exec family replaces the child's program image with a new program. wait lets the parent collect the child's exit status; a child that exits but has not been waited for is a zombie, and a child whose parent exits first is adopted by init. In POSIX threads, pthread_create starts a thread running a function and pthread_join waits for it to finish.

## Thread safety
Code is thread-safe if it behaves correctly when called by several threads at once. Techniques include mutual exclusion with mutexes, atomic operations, thread-local storage and immutable data. Thread pools reuse a fixed set of worker threads to avoid the cost of creating a thread for each task and to bound resource use.

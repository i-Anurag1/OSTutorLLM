# Process Management and CPU Scheduling

## Processes and the PCB
A process is a program in execution: code, data, heap, stack and the CPU state. Its states are new, ready, running, waiting (blocked) and terminated. The kernel keeps a process control block (PCB) for each process holding the process ID, state, program counter, saved registers, scheduling information, memory-management information and open files. A context switch saves the running process's state into its PCB and loads the next process's state. It is pure overhead because no useful work is done while it happens.

## Scheduling criteria
Schedulers are judged by CPU utilisation, throughput (processes finished per unit time), turnaround time (completion time minus arrival time), waiting time (time spent in the ready queue, equal to turnaround minus burst time), and response time (first run minus arrival time). A good scheduler maximises utilisation and throughput and minimises turnaround, waiting and response time.

## First-Come First-Served (FCFS)
FCFS runs processes in arrival order and is non-preemptive. It is simple but suffers from the convoy effect: short processes wait behind one long CPU-bound process, which inflates average waiting time. With bursts P1=24, P2=3, P3=3 arriving together in that order, waiting times are 0, 24 and 27, so the average is 17. If the order were P2, P3, P1 the average would drop to 3.

## Shortest Job First (SJF) and SRTF
SJF picks the ready process with the smallest next CPU burst and gives the minimum possible average waiting time for a set of processes. Its preemptive version is Shortest Remaining Time First (SRTF): when a new process arrives with a burst shorter than the remaining time of the running one, it preempts. The weakness is starvation of long processes and the fact that burst lengths are unknown, so they are predicted by exponential averaging: tau(n+1) = alpha * t(n) + (1 - alpha) * tau(n), where t(n) is the last measured burst and tau(n) the previous prediction.

## Priority scheduling and aging
Each process has a priority and the CPU goes to the highest priority ready process (a smaller number often means higher priority). It can be preemptive or non-preemptive. Low-priority processes may starve. Aging solves this by gradually raising the priority of processes that wait for a long time.

## Round Robin (RR)
RR gives each ready process a fixed time quantum and then moves it to the back of the ready queue. It is preemptive and designed for time-sharing, giving good response time. If the quantum is very large RR behaves like FCFS; if it is very small the context-switch overhead dominates. A common rule of thumb is that about 80 percent of CPU bursts should be shorter than the quantum. For P1=24, P2=3, P3=3 with quantum 4 the schedule is P1 0-4, P2 4-7, P3 7-10, then P1 until 30, giving waiting times 6, 4 and 7 and an average of 5.67.

## Multilevel queue and multilevel feedback queue
A multilevel queue splits ready processes into separate queues, for example interactive foreground and batch background, each with its own algorithm. A multilevel feedback queue (MLFQ) lets processes move between queues: a process that uses its whole quantum is demoted, while one that blocks for I/O stays high. This favours short and interactive jobs without knowing burst lengths in advance, and aging prevents starvation of demoted processes.

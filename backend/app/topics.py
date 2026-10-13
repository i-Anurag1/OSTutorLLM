"""Single source of truth for course topics (used by seed, API, retrieval hints and the UI)."""

TOPICS = [
    ("Foundations", "easy", "What an OS does, kernel and user mode, interrupts, kernel designs.", "operating system kernel mode interrupt"),
    ("Process Scheduling", "medium", "Processes, the PCB and CPU scheduling: FCFS, SJF, Priority, Round Robin, MLFQ.", "process scheduling cpu burst"),
    ("Threads", "easy", "Threads versus processes, thread models, fork, exec and wait.", "thread process fork"),
    ("Synchronization", "medium", "Race conditions, critical sections, mutexes, semaphores, monitors.", "critical section semaphore mutex"),
    ("Producer-Consumer", "medium", "The bounded buffer problem solved with semaphores.", "producer consumer bounded buffer semaphore"),
    ("Dining Philosophers", "medium", "Deadlock and starvation in the classic five-philosopher problem.", "dining philosophers forks deadlock"),
    ("Deadlocks", "medium", "Coffman conditions, resource graphs, prevention, avoidance, detection.", "deadlock coffman resource"),
    ("Banker's Algorithm", "hard", "Safe states, the safety algorithm and resource-request checks.", "banker safe state need allocation"),
    ("Memory Management", "medium", "Address binding, contiguous allocation, paging, the TLB and page tables.", "memory paging page table tlb fragmentation"),
    ("Paging", "medium", "Pages, frames, address splitting and effective access time.", "paging page frame offset"),
    ("Page Replacement", "hard", "Demand paging, FIFO, LRU, Optimal, Clock, Belady's anomaly, thrashing.", "page replacement fifo lru optimal"),
    ("Virtual Memory", "medium", "Demand paging, copy-on-write, memory-mapped files, working sets.", "virtual memory demand paging"),
    ("Segmentation", "medium", "Segment tables, base and limit, and comparison with paging.", "segmentation segment base limit"),
    ("File Systems", "medium", "Files, directories, allocation methods, inodes, links, journaling.", "file system inode directory allocation"),
    ("Disk Scheduling", "medium", "FCFS, SSTF, SCAN, C-SCAN, LOOK and C-LOOK with worked totals.", "disk scheduling seek head cylinder"),
    ("I/O and Storage", "medium", "Polling, interrupts, DMA, buffering, RAID and SSDs.", "io dma raid storage"),
    ("System Calls", "easy", "How user programs enter the kernel; fork, exec, wait and file descriptors.", "system call kernel fork exec"),
    ("Protection and Security", "medium", "Protection domains, access matrix, authentication and common attacks.", "protection security access matrix"),
    ("Linux Commands", "easy", "Files, searching, pipes, permissions and process control commands.", "linux command chmod grep pipe"),
    ("Shell Programming", "easy", "Variables, conditions, loops, functions and exit status in bash.", "shell script bash variable loop"),
]
TOPIC_NAMES = [t[0] for t in TOPICS]
TOPIC_HINTS = {t[0]: t[3] for t in TOPICS}

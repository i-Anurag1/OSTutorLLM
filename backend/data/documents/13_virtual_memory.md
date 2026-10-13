# Virtual Memory

## The idea
Virtual memory separates the logical address space seen by a process from the physical memory actually installed. A process can be larger than physical memory, because only the pages currently needed are kept in RAM and the rest stay on disk. It allows more processes to run at once, simplifies programming, and provides isolation since each process has its own address space.

## Demand paging
Pages are loaded lazily when first referenced. The page table's valid bit says whether a page is in memory. A reference to an invalid page raises a page fault, which the OS services by loading the page from the backing store. A pure demand-paging system starts a process with no pages in memory. Locality of reference, the tendency of programs to reuse nearby addresses and recently used addresses, is the reason demand paging performs well.

## Copy-on-write
When fork creates a child, copy-on-write lets parent and child share the same physical pages marked read-only. Only when one of them writes to a page does the kernel copy it and give the writer a private copy. This makes fork cheap, especially when the child calls exec immediately afterwards.

## Memory-mapped files
A memory-mapped file maps a file's contents into the process's address space so reading and writing memory reads and writes the file through the page cache, with no explicit read or write calls. Several processes can map the same file to share memory. On Linux this is done with mmap.

## Swap space and the page cache
Swap space is disk area used to hold pages evicted from RAM. The kernel also uses free memory as a page cache for file data, which is dropped first when memory runs short because clean cache pages can simply be discarded.

## Thrashing and the working set
When the combined working sets of processes exceed physical memory, page faults dominate and throughput collapses. This is thrashing. The remedies are to reduce the degree of multiprogramming, to use working-set or page-fault-frequency control, and to add memory. The OOM killer on Linux terminates processes when memory is exhausted.

## Address space layout
A typical process address space contains text (code), data, heap growing upward, memory-mapped regions and a stack growing downward, with the kernel mapped in the upper part. Address space layout randomisation (ASLR) randomises these locations on each run to make exploits harder.

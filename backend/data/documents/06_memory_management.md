# Memory Management

## Logical and physical addresses
The CPU generates logical (virtual) addresses, while memory hardware sees physical addresses. The memory management unit (MMU) translates between them at run time. This lets each process have its own address space, enables relocation and provides protection by checking every access.

## Contiguous allocation and fragmentation
With contiguous allocation each process occupies one block of memory. Placement strategies are first fit (first hole large enough), best fit (smallest hole that fits) and worst fit (largest hole). External fragmentation is free memory split into holes too small to use and can be reduced by compaction. Internal fragmentation is wasted space inside an allocated block. The 50-percent rule says that for first fit about one third of memory may be unusable due to external fragmentation.

## Paging
Paging divides logical memory into fixed-size pages and physical memory into frames of the same size, which removes external fragmentation. A logical address is split into a page number p and an offset d. The page table maps page p to frame f and the physical address is f * page size + d. If the page size is 2 to the power n, the low n bits are the offset and the remaining high bits are the page number. Paging still has internal fragmentation, averaging half a page per process.

## Page table and TLB
Page tables live in main memory, so each access would need two memory accesses. The translation lookaside buffer (TLB) is a small, fast associative cache of recent page-to-frame mappings. On a TLB hit the frame is known immediately; on a miss the page table is read and the TLB is updated. With hit ratio h, TLB lookup time t and memory access time m, the effective access time is EAT = h * (t + m) + (1 - h) * (t + 2m). For example with h = 0.8, t = 20 ns and m = 100 ns, EAT = 0.8 * 120 + 0.2 * 220 = 140 ns.

## Page table size and multilevel paging
The page table size equals the number of pages times the entry size. A 32-bit address space with 4 KB pages has 2 to the power 20 pages, so with 4-byte entries one flat page table takes 4 MB per process. Multilevel paging pages the page table itself so only the parts in use are kept in memory. Hashed and inverted page tables store one entry per physical frame, which saves memory but makes lookups slower without extra hashing.

## Swapping
Swapping moves an entire process between main memory and a backing store so more processes can exist than fit in memory. Modern systems prefer paging individual pages out, which is far cheaper than swapping whole processes.

## Protection and sharing
Page table entries carry valid and invalid bits and read, write and execute permission bits. Accessing an invalid page raises a trap. Pages of shared code, such as a library, can be mapped into several processes at the same frames when the code is read-only and reentrant.

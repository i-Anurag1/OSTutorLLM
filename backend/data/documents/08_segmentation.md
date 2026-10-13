# Segmentation

## Segments and the user's view of memory
Segmentation divides a program's logical address space into variable-sized segments that match how programmers think: code, data, heap, stack, and libraries. A logical address is a pair (segment number s, offset d).

## Segment table and translation
Each process has a segment table with one entry per segment holding a base (starting physical address) and a limit (length). To translate (s, d) the hardware checks that s is a valid segment number and that d is less than the limit. If the check fails the hardware traps with a segmentation fault; otherwise the physical address is base + d. For example, if segment 2 has base 4300 and limit 400, address (2, 53) maps to 4353, while (2, 500) is invalid because 500 is not less than 400.

## Fragmentation and protection
Because segments have different sizes, segmentation suffers from external fragmentation, just like variable-size contiguous allocation, and may need compaction. It has no internal fragmentation. Each segment can have its own protection bits, so code can be read-only and executable while data is read-write, and segments can be shared between processes by pointing their tables at the same physical segment.

## Segmentation versus paging
Paging uses fixed-size units and is invisible to the programmer; it removes external fragmentation but has internal fragmentation. Segmentation uses variable-size logical units that match program structure; it makes sharing and protection natural but causes external fragmentation. Many designs combine them: each segment is itself divided into pages, so the segment table points to a page table for that segment and the address has the form (segment, page, offset).

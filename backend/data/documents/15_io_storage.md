# I/O and Storage Systems

## I/O hardware and device controllers
Devices connect through ports and buses and are operated by a device controller with registers for commands and status. The CPU communicates with controllers either through special I/O instructions or by memory-mapped I/O, where device registers appear at ordinary memory addresses.

## Polling, interrupts and DMA
In polling (programmed I/O) the CPU repeatedly checks the controller's status register, which wastes cycles. With interrupt-driven I/O the device raises an interrupt when it is ready, so the CPU can do other work. For large transfers, direct memory access (DMA) lets the controller move data between the device and memory without involving the CPU for each byte, interrupting only when the whole transfer is complete.

## The I/O software stack
Layers from top to bottom are user programs, system call interface, device-independent kernel I/O subsystem, device drivers and interrupt handlers. A device driver hides device-specific details behind a uniform interface. Block devices such as disks transfer fixed-size blocks and support random access, while character devices such as keyboards stream bytes.

## Buffering, caching and spooling
Buffering holds data in memory while it is being transferred, to cope with speed mismatches, different transfer sizes and copy semantics. Double buffering lets one buffer fill while another drains. A cache keeps a copy of frequently used data in faster storage. Spooling holds output for a device that cannot accept interleaved data, such as a printer, in a queue on disk.

## Blocking and non-blocking I/O
A blocking call suspends the calling thread until the I/O completes. Non-blocking calls return immediately with whatever data is available, and asynchronous I/O starts the operation and notifies the program later. Event-driven servers use select, poll or epoll to wait on many descriptors at once.

## RAID levels
RAID combines several disks for performance and reliability. RAID 0 stripes data across disks for speed with no redundancy. RAID 1 mirrors data on two disks, so it survives one disk failure at 50 percent usable capacity. RAID 5 stripes data with distributed parity, tolerates one disk failure and has capacity of n-1 disks. RAID 6 uses double parity to survive two failures. RAID 10 stripes across mirrored pairs, combining speed and redundancy. RAID is not a substitute for backups.

## Solid-state drives
Flash storage has no moving parts, so random access is fast, but pages cannot be overwritten in place and are erased in large blocks. A flash translation layer remaps logical blocks, performs garbage collection and spreads writes across cells for wear levelling, and the TRIM command tells the drive which blocks are no longer in use.

# Operating System Foundations

## What an operating system does
An operating system (OS) is system software that manages hardware and provides services to programs. It has two jobs. As a resource manager it allocates CPU time, memory, storage and I/O devices fairly and efficiently. As an abstraction layer it gives programs simple interfaces such as files, processes and sockets instead of raw hardware.

## Kernel mode and user mode
The CPU runs in at least two privilege modes. In kernel mode (supervisor mode) code may execute privileged instructions such as changing page tables, disabling interrupts and talking to devices. In user mode those instructions are forbidden, and a user program that attempts one causes a trap. A mode bit in the CPU status register records the current mode. User programs enter the kernel only through controlled entry points: system calls, interrupts and exceptions.

## Interrupts, traps and exceptions
An interrupt is an asynchronous signal from hardware, such as a timer tick, a disk finishing a transfer or a key press. A trap (exception) is synchronous and is caused by the running instruction, for example a divide by zero, a page fault or a system call instruction. On either event the CPU saves the program counter and flags, switches to kernel mode and jumps to a handler found through the interrupt vector table. The timer interrupt lets the OS take the CPU back from a program that never yields, which is what makes preemptive multitasking possible.

## Kernel designs
A monolithic kernel (Linux, classic UNIX) runs the scheduler, memory manager, file systems and drivers together in kernel mode. Components call each other directly, so it is fast, but a faulty driver can crash the whole system. A microkernel (Minix, QNX) keeps only address spaces, basic scheduling and inter-process communication in the kernel and runs file systems and drivers as user-space servers. This improves isolation and reliability at the cost of extra message passing. Hybrid kernels such as Windows NT and macOS XNU combine both ideas.

## Types of operating systems
Batch systems run jobs one after another with no interaction. Time-sharing (multitasking) systems switch rapidly between programs so every user sees a responsive machine. Real-time systems guarantee deadlines: in a hard real-time system a missed deadline is a failure, while a soft real-time system tolerates occasional misses. Distributed and embedded operating systems target networks of machines and dedicated devices.

## Bootstrapping
At power-on, firmware (BIOS or UEFI) runs, locates a bootloader on disk, and the bootloader loads the kernel into memory. The kernel initialises devices and memory management, then starts the first user process (init or systemd on Linux), which launches every other service.

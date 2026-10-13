# System Calls

## Purpose
A system call is the interface through which a user program requests a service from the kernel, such as creating a process, opening a file or sending network data. Because user mode cannot touch hardware directly, system calls provide a safe and controlled transition into kernel mode.

## How a system call works
A program normally calls a library wrapper such as read or fork in the C library. The wrapper places the system call number and arguments in registers and executes a special instruction (syscall or int 0x80 on x86, svc on ARM). This traps into the kernel, which switches to kernel mode, uses the number to index the system call table, runs the handler, places the return value in a register and returns to user mode. Large arguments are passed by putting their address in a register or a block in memory, or by pushing them on the stack.

## Categories
Process control covers fork, exec, exit, wait and kill. File management covers open, read, write, close, lseek, stat and unlink. Device management covers ioctl, read and write on device files. Information maintenance covers getpid, time and sysinfo. Communication covers pipe, socket, send, recv and shared memory. Protection covers chmod, chown and umask.

## The fork, exec and wait pattern
The shell runs a command by calling fork to create a child. The child calls exec to load the program and the parent calls wait to block until the child exits and returns its status. After fork both processes continue from the same point; the return value distinguishes them: 0 in the child and the child's process ID in the parent, with -1 signalling failure.

## File descriptors
open returns a small non-negative integer called a file descriptor that indexes the process's table of open files. Descriptors 0, 1 and 2 are standard input, output and error. read and write take a descriptor, a buffer and a count, and return the number of bytes transferred or -1 on error, in which case the error code is stored in errno. dup2 duplicates a descriptor and is how shells implement redirection and pipes.

## API versus system call, and tracing
An API such as POSIX defines functions programs call, while the system call is the kernel entry underneath it. A library function like printf may buffer output and finally call write. On Linux the strace tool prints every system call a program makes along with arguments and results, which is very useful for understanding what a program does.

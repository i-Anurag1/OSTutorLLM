# Protection and Security

## Protection versus security
Protection is the set of mechanisms that control access of programs, processes and users to resources defined by the system. Security defends the system against internal and external attacks such as malware, intrusion and denial of service. The principle of least privilege says that every program and user should have only the privileges needed to do its job.

## Domains and the access matrix
A protection domain defines the set of objects and operations a process may use. The access matrix has domains as rows, objects as columns and the allowed operations in each cell. Storing it by column gives an access control list (ACL) attached to each object, while storing it by row gives capability lists held by each domain. Unix permission bits are a compact form of ACL.

## Authentication
Authentication proves identity using something you know (a password), something you have (a token or phone) or something you are (a biometric trait); multi-factor authentication combines several. Passwords should be stored as salted slow hashes such as bcrypt, scrypt or PBKDF2, never as plain text, so that stolen password files are hard to crack.

## Common attacks
A buffer overflow writes past the end of a buffer and can overwrite a return address to hijack control flow. Defences include stack canaries (a guard value checked before returning), a non-executable stack or data pages (NX bit) and ASLR. Other threats are privilege escalation, Trojan horses, viruses, worms, ransomware, SQL injection, race conditions such as time-of-check to time-of-use (TOCTOU) and denial of service.

## Isolation techniques
Separate address spaces and user and kernel modes protect processes from each other. Sandboxing restricts a program's system calls, for example with seccomp. Containers use Linux namespaces to isolate what a process can see and cgroups to limit what it can use. Virtual machines isolate whole operating systems through a hypervisor, which gives stronger isolation than containers at higher cost.

## Linux access control
Linux checks the user ID, group ID and permission bits when opening files. The root user bypasses these checks, so administration should use sudo for single commands. Capabilities split root's power into smaller pieces, and mandatory access control systems such as SELinux and AppArmor enforce system-wide policies even against the owner of a file.

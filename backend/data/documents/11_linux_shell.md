# Linux Commands and Shell Programming

## Navigating and managing files
pwd prints the current directory, ls lists files (ls -l gives permissions, owner, size and time, ls -a includes hidden files), and cd changes directory. mkdir creates directories, cp copies, mv moves or renames, rm deletes (rm -r removes directories recursively and should be used with care), touch creates an empty file, and cat prints file contents. head and tail show the first and last lines, and tail -f follows a growing log.

## Searching and filtering
grep searches text for a pattern (grep -i ignores case, grep -r searches recursively, grep -n shows line numbers). find locates files by name, type, size or time, for example find . -name "*.c". wc counts lines, words and bytes, sort orders lines, uniq removes adjacent duplicates and cut extracts columns.

## Pipes and redirection
Every process starts with standard input (file descriptor 0), standard output (1) and standard error (2). The pipe operator connects one command's output to the next command's input, as in ls | wc -l. Redirection sends output to a file: > overwrites, >> appends, < reads input from a file, and 2> redirects errors. Writing 2>&1 sends errors to the same place as normal output.

## File permissions
Each file has read (r), write (w) and execute (x) permissions for the owner, the group and others, shown as nine characters such as rwxr-xr--. Permissions are also written in octal where r=4, w=2 and x=1, so rwxr-xr-- is 754. chmod changes permissions (chmod 755 script.sh or chmod u+x script.sh), chown changes ownership, and umask sets default permissions for new files. The setuid bit makes a program run with its owner's privileges.

## Process control commands
ps shows processes (ps aux lists all), top shows live resource usage, and kill sends a signal to a process (kill -9 sends SIGKILL, which cannot be caught). Appending & runs a command in the background, jobs lists background jobs, and fg and bg move jobs to the foreground or background. Ctrl+C sends SIGINT and Ctrl+Z suspends a job. nice and renice change scheduling priority.

## Shell scripting basics
A script starts with a shebang line such as #!/bin/bash and must be executable. Variables are assigned without spaces (name=value) and read with $name. Command-line arguments are $1, $2 and so on, with $# as their count and $@ as all of them. The exit status of the last command is $?, where 0 means success. Conditions use if [ condition ]; then ... fi, for example if [ -f file ] tests that a file exists and -eq, -lt and -gt compare integers. Loops include for i in 1 2 3; do ... done and while [ condition ]; do ... done. Command substitution $(command) captures output, and functions are defined as name() { ... }.

## A small script example
The script below sums the numbers from 1 to 5: total=0; for i in 1 2 3 4 5; do total=$((total + i)); done; echo $total prints 15. Quoting variables as "$var" prevents word splitting when values contain spaces.

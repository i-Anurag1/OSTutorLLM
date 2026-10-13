# File Systems

## Files and directories
A file is a named collection of related information on secondary storage. Attributes include name, type, location, size, protection and timestamps. Common operations are create, open, read, write, seek, truncate, delete and close. A directory maps file names to file metadata. Directory structures include single-level, two-level, tree-structured (the usual hierarchy) and acyclic-graph directories that allow shared files through links.

## Access methods
Sequential access reads records in order and is the model for tapes and many streams. Direct (random) access reads any block by number and suits databases. Indexed access builds an index over blocks or records so that a search can jump near the desired data.

## Allocation methods
Contiguous allocation stores a file in consecutive blocks; it is fast and simple but suffers from external fragmentation and needs the final file size up front. Linked allocation chains blocks through pointers, so there is no external fragmentation, but random access is slow and one lost pointer breaks the file. The File Allocation Table (FAT) keeps those pointers in a table in memory to speed up access. Indexed allocation stores all block pointers of a file in an index block, which gives efficient direct access at the cost of index overhead.

## Unix inodes
A Unix inode stores a file's metadata (owner, permissions, size, timestamps, link count) and block pointers but not its name. It holds direct pointers to data blocks, a single indirect pointer to a block of pointers, a double indirect pointer and a triple indirect pointer. With 4 KB blocks and 4-byte pointers, one indirect block holds 1024 pointers, so the single indirect level adds 4 MB. Directory entries pair a file name with an inode number.

## Hard links and symbolic links
A hard link is another directory entry pointing to the same inode; the file's data is removed only when the link count reaches zero, and hard links cannot cross file systems. A symbolic (soft) link is a small file containing a path; it can cross file systems and point to directories but becomes dangling if the target is removed.

## Free-space management
Free blocks can be tracked with a bit vector (one bit per block), a linked list of free blocks, grouping, or counting runs of contiguous free blocks. A bit vector makes it easy to find contiguous space but the vector itself uses memory.

## Journaling and consistency
A crash in the middle of a multi-step update can leave the file system inconsistent. A journaling file system such as ext4 or NTFS first writes a description of intended changes to a log, then applies them, so after a crash it replays or discards the log instead of scanning the entire disk with fsck. Mounting attaches a file system to a point in the directory tree.

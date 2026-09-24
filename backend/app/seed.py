from pathlib import Path
from .db import SessionLocal
from .models import User,Topic,Question,Source
from .auth import hash_password
from .rag import ingest_all,DOCS
TOPICS=['Linux Commands','Shell Programming','Process Scheduling','Deadlocks','Memory Management','Paging','Segmentation','File Systems','Disk Scheduling','Synchronization','Threads','Producer-Consumer',"Banker's Algorithm",'Dining Philosophers','System Calls','I/O and Storage','Protection and Security']
QUESTIONS=[
('Paging','medium','mcq','What causes a page fault?',['A referenced page is absent from the required physical frames','The CPU clock stops','A file is deleted','A process terminates'],'A','A page fault occurs when a referenced page is not resident.'),
('Paging','medium','mcq','Which page replacement policy removes the least recently used page?',['FIFO','LRU','Optimal','FCFS'],'B','LRU removes the page not used for the longest time.'),
('Process Scheduling','easy','mcq','Which algorithm uses a time quantum?',['FCFS','SJF','Round Robin','Priority'],'C','Round Robin assigns each ready process a fixed time quantum.'),
('Deadlocks','easy','mcq','Which is not a Coffman condition?',['Mutual exclusion','Hold and wait','Preemption','Circular wait'],'C','No preemption, not preemption, is a Coffman condition.'),
('Segmentation','easy','mcq','When is a segmented logical address valid?',['Offset equals the limit','Offset is less than the segment limit','Base is zero','Segment number is odd'],'B','The offset must be below the segment limit.'),
('Disk Scheduling','medium','mcq','Which disk algorithm chooses the closest pending request?',['FCFS','SSTF','SCAN','C-SCAN'],'B','SSTF selects the pending request with the smallest head distance.'),
('Synchronization','easy','mcq','Producer-consumer commonly uses what kind of shared structure?',['Bounded buffer','Page table','Inode only','TLB'],'A','Producer-consumer coordinates access to a bounded buffer.'),
('System Calls','easy','mcq','System calls provide what interface?',['User-to-kernel interface','GPU-to-display interface','Compiler-to-linker interface','Disk-to-network interface'],'A','System calls provide the user-to-kernel interface.'),
('Threads','easy','mcq','Threads in one process commonly share which resource?',['Address space','Separate executable image','Independent process ID namespace','Independent heap only'],'A','Threads in one process share an address space and many resources.'),
('Virtual Memory','medium','mcq','What does a TLB cache?',['Recent address translations','Disk requests','Shell commands','File contents'],'A','The TLB caches recent virtual-to-physical translations.'),
]
def run():
    db=SessionLocal()
    for email,pw,name,role in [('student@ostutor.local','Student123!','Student','student'),('faculty@ostutor.local','Faculty123!','Faculty','faculty'),('admin@ostutor.local','Admin123!','Administrator','admin')]:
        u=db.query(User).filter_by(email=email).first()
        if not u: db.add(User(email=email,password_hash=hash_password(pw),name=name,role=role))
    db.commit(); users={u.email:u for u in db.query(User).all()}
    for n in TOPICS:
        if not db.query(Topic).filter_by(name=n).first(): db.add(Topic(name=n,description=f'Interactive course module: {n}.',difficulty='medium'))
    db.commit()
    admin=users['admin@ostutor.local']
    for row in QUESTIONS:
        if not db.query(Question).filter_by(prompt=row[3]).first(): db.add(Question(topic=row[0],difficulty=row[1],kind=row[2],prompt=row[3],options=row[4],answer=row[5],explanation=row[6],created_by=admin.id))
    db.commit()
    result=ingest_all()
    import hashlib
    from .rag import metadata
    for p in sorted(DOCS.glob('*')):
        if not p.is_file(): continue
        checksum=hashlib.sha256(p.read_bytes()).hexdigest(); file_chunks=sum(1 for h in metadata if h['path']==p.name)
        existing=db.query(Source).filter_by(path=str(p)).first()
        if not existing: db.add(Source(name=p.name,path=str(p),status='ready',version=1,chunks=file_chunks,checksum=checksum,uploaded_by=admin.id))
        else: existing.status='ready'; existing.checksum=checksum; existing.chunks=file_chunks
    db.commit(); db.close(); print('seed complete',result)
if __name__=='__main__': run()

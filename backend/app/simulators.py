from collections import deque

def cpu_scheduling(algorithm, processes, quantum=2):
    ps=[{'pid':str(p['pid']),'arrival':int(p.get('arrival',0)),'burst':int(p['burst']),'priority':int(p.get('priority',0))} for p in processes]
    if not ps or any(p['burst']<=0 or p['arrival']<0 for p in ps): raise ValueError('Invalid process values')
    rem={p['pid']:p['burst'] for p in ps}; t=0; timeline=[]; done=set(); first={}; finish={}; queue=[]; rr=deque(); added=set()
    while len(done)<len(ps):
        arrivals=sorted([p for p in ps if p['arrival']<=t and p['pid'] not in added],key=lambda p:(p['arrival'],p['pid']))
        for p in arrivals: rr.append(p); added.add(p['pid'])
        if algorithm=='Round Robin':
            if not rr:
                t=min(p['arrival'] for p in ps if p['pid'] not in added); continue
            p=rr.popleft(); run=min(quantum,rem[p['pid']]); start=t; t+=run; rem[p['pid']]-=run; first.setdefault(p['pid'],start)
        else:
            ready=[p for p in ps if p['arrival']<=t and p['pid'] not in done and rem[p['pid']]>0]
            if not ready: t=min(p['arrival'] for p in ps if p['pid'] not in added); continue
            if algorithm=='FCFS': p=min(ready,key=lambda x:(x['arrival'],x['pid']))
            elif algorithm=='SJF': p=min(ready,key=lambda x:(x['burst'],x['arrival'],x['pid']))
            elif algorithm=='SRTF':
                p=min(ready,key=lambda x:(rem[x['pid']],x['arrival'],x['pid'])); run=1; start=t; t+=run; rem[p['pid']]-=run; first.setdefault(p['pid'],start)
            elif algorithm=='Priority': p=min(ready,key=lambda x:(x['priority'],x['arrival'],x['pid']))
            else: raise ValueError('Unsupported CPU algorithm')
            if algorithm!='SRTF':
                run=rem[p['pid']]; start=t; t+=run; rem[p['pid']]=0; first.setdefault(p['pid'],start)
        timeline.append({'pid':p['pid'],'start':start,'end':t,'remaining':rem[p['pid']]})
        if rem[p['pid']]==0: done.add(p['pid']); finish[p['pid']]=t
        elif algorithm=='Round Robin': rr.append(p)
    metrics=[]
    for p in ps:
        tat=finish[p['pid']]-p['arrival']; wt=tat-p['burst']; metrics.append({'pid':p['pid'],'waiting':wt,'turnaround':tat,'response':first[p['pid']]-p['arrival']})
    return {'algorithm':algorithm,'timeline':timeline,'metrics':metrics,'avg_waiting':sum(x['waiting'] for x in metrics)/len(metrics),'avg_turnaround':sum(x['turnaround'] for x in metrics)/len(metrics),'complexity':'O(n²) for preemptive simulation, O(n log n) for sorted non-preemptive variants'}

def page_replacement(algorithm, refs, frames_n):
    frames=[]; faults=0; steps=[]; last={}; q=deque()
    for i,page in enumerate(refs):
        hit=page in frames; victim=None
        if not hit:
            faults+=1
            if len(frames)<frames_n: frames.append(page); q.append(page)
            elif algorithm=='FIFO': victim=q.popleft(); frames[frames.index(victim)]=page; q.append(page)
            elif algorithm=='LRU': victim=min(frames,key=lambda x:last.get(x,-1)); frames[frames.index(victim)]=page
            elif algorithm=='Optimal':
                future=refs[i+1:]; victim=max(frames,key=lambda x:future.index(x) if x in future else 10**9); frames[frames.index(victim)]=page
            else: raise ValueError('Unsupported page algorithm')
        last[page]=i; steps.append({'index':i,'reference':page,'frames':frames.copy(),'hit':hit,'fault':not hit,'victim':victim})
    return {'algorithm':algorithm,'faults':faults,'hits':len(refs)-faults,'fault_rate':faults/len(refs) if refs else 0,'steps':steps,'complexity':'O(m*n)'}

def bankers(allocation,maximum,available):
    n=len(allocation); m=len(available)
    if any(len(r)!=m for r in allocation+maximum) or len(maximum)!=n: raise ValueError('Matrix dimensions mismatch')
    if any(maximum[i][j]<allocation[i][j] for i in range(n) for j in range(m)): raise ValueError('Maximum is below allocation')
    need=[[maximum[i][j]-allocation[i][j] for j in range(m)] for i in range(n)]; work=available[:]; finish=[False]*n; seq=[]; steps=[]
    while True:
        found=False
        for i in range(n):
            if not finish[i] and all(need[i][j]<=work[j] for j in range(m)):
                before=work[:]
                work=[work[j]+allocation[i][j] for j in range(m)]; finish[i]=True; seq.append(i); found=True; steps.append({'process':i,'need':need[i],'work_before':before,'work_after':work[:]})
        if not found: break
    return {'safe':all(finish),'sequence':seq,'need':need,'work':work,'steps':steps,'complexity':'O(n^2*m)'}

def deadlock_detection(allocation,request,available):
    n=len(allocation); m=len(available); work=available[:]; finish=[False]*n; seq=[]; steps=[]
    while True:
        found=False
        for i in range(n):
            if not finish[i] and all(request[i][j]<=work[j] for j in range(m)):
                before=work[:]; work=[work[j]+allocation[i][j] for j in range(m)]; finish[i]=True; seq.append(i); found=True; steps.append({'process':i,'work_before':before,'work_after':work[:]})
        if not found: break
    return {'deadlocked':[i for i,f in enumerate(finish) if not f],'safe':all(finish),'sequence':seq,'steps':steps}

def disk_scheduling(algorithm,requests,head,disk_size=200):
    if not 0<=head<disk_size or any(not 0<=x<disk_size for x in requests): raise ValueError('Disk request outside range')
    left=sorted(x for x in requests if x<head); right=sorted(x for x in requests if x>=head); order=[]
    if algorithm=='FCFS': order=list(requests)
    elif algorithm=='SSTF':
        rem=list(requests); cur=head
        while rem: x=min(rem,key=lambda v:(abs(v-cur),v)); order.append(x); rem.remove(x); cur=x
    elif algorithm=='SCAN': order=right+[disk_size-1]+left[::-1]
    elif algorithm=='C-SCAN': order=right+[disk_size-1,0]+left
    elif algorithm=='LOOK': order=right+left[::-1]
    elif algorithm=='C-LOOK': order=right+left
    else: raise ValueError('Unsupported disk algorithm')
    cur=head; movement=0; segments=[]
    for x in order: movement+=abs(x-cur); segments.append({'from':cur,'to':x,'distance':abs(x-cur)}); cur=x
    return {'algorithm':algorithm,'order':order,'movement':movement,'segments':segments,'complexity':'O(n log n)' if algorithm!='FCFS' else 'O(n)'}

def producer_consumer(size,items):
    q=deque(); events=[]
    for item in range(1,items+1):
        if len(q)>=size: events.append({'event':'producer_wait','buffer':list(q)})
        q.append(item); events.append({'event':'produce','item':item,'buffer':list(q)})
        consumed=q.popleft(); events.append({'event':'consume','item':consumed,'buffer':list(q)})
    return {'events':events,'model':'bounded-buffer semaphore sequence'}

def dining_philosophers(n=5):
    states=['thinking']*n; events=[]
    for i in range(n):
        left=i; right=(i+1)%n; states[i]='hungry'; events.append({'philosopher':i,'action':'hungry','states':states[:]})
        if states[left]!='eating' and states[right]!='eating': states[i]='eating'; events.append({'philosopher':i,'action':'eat','states':states[:]})
        states[i]='thinking'; events.append({'philosopher':i,'action':'release','states':states[:]})
    return {'events':events,'deadlock_free_ordered':True}

def paging(addresses,page_size,num_frames):
    rows=[]
    for a in addresses:
        page=a//page_size; offset=a%page_size; frame=page%num_frames; physical=frame*page_size+offset
        rows.append({'logical':a,'page':page,'offset':offset,'frame':frame,'physical':physical})
    return {'rows':rows,'formula':'page=floor(address/page_size), offset=address mod page_size'}

def segmentation(segments,logical):
    rows=[]
    for x in logical:
        seg=x.get('segment',0); off=x.get('offset',0); s=segments[seg]
        valid=0<=off<s['limit']; rows.append({'segment':seg,'offset':off,'base':s['base'],'limit':s['limit'],'valid':valid,'physical':s['base']+off if valid else None})
    return {'rows':rows,'rule':'physical = base + offset when offset < limit'}

def thread_lifecycle():
    return {'states':['NEW','READY','RUNNING','BLOCKED','TERMINATED'],'transitions':[('NEW','READY'),('READY','RUNNING'),('RUNNING','BLOCKED'),('BLOCKED','READY'),('RUNNING','TERMINATED')]}

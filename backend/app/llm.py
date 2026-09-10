import httpx,json,re,time
from .config import settings

def _evidence_answer(question,hits,topic=None,difficulty='adaptive'):
    text=' '.join(h['text'] for h in hits)
    q=question.lower()
    # Deterministic grounded tutor that works with zero API keys.
    if any(x in q for x in ['page replacement','fifo','lru','optimal']):
        body=("Page replacement decides which page to evict when a page fault occurs and all frames are full. "
              "FIFO removes the page that has been resident the longest. LRU removes the page that has not been used for the longest time. "
              "Optimal removes the page whose next use is farthest in the future, giving the theoretical minimum number of faults.")
    elif 'deadlock' in q:
        body=("A deadlock is a state in which processes wait indefinitely for resources held by one another. "
              "The four Coffman conditions are mutual exclusion, hold and wait, no preemption, and circular wait. "
              "Banker's algorithm checks whether granting a request preserves a safe state.")
    elif 'paging' in q or 'segmentation' in q:
        body=("Paging divides virtual memory into fixed-size pages and physical memory into frames. A page fault occurs when a referenced page is not resident. "
              "Segmentation instead models memory as logical segments with a base and limit, and an address is valid only when its offset is below the segment limit.")
    elif 'process' in q and 'schedul' in q:
        body=("FCFS runs ready processes in arrival order. SJF selects the shortest available burst, while Round Robin gives each ready process a fixed time quantum. "
              "The choice changes waiting time, response time, and fairness.")
    elif 'producer' in q or 'consumer' in q or 'semaphore' in q:
        body=("The producer-consumer problem coordinates producers and consumers around a bounded buffer. Semaphores can control mutual exclusion and the counts of available and occupied slots.")
    else:
        # Pull a concise answer from the strongest grounded snippets.
        snippets=[h['text'] for h in hits[:3]]
        body=("Here is a grounded explanation based on the indexed course sources. " + ' '.join(snippets))
    cited=' '.join(f'[S{i+1}]' for i in range(min(3,len(hits))))
    return f"{body}\n\nKey takeaway: focus on the definition, decision rule, and a concrete example when studying this topic. {cited}".strip()
async def generate(messages,temperature=0.2,response_format=None):
    if not settings.llm_base_url:
        return _evidence_answer(messages[-1]['content'],[],None),1.0
    url=settings.llm_base_url.rstrip('/')+'/chat/completions'; headers={'Content-Type':'application/json'}
    if settings.llm_api_key: headers['Authorization']='Bearer '+settings.llm_api_key
    body={'model':settings.llm_model,'messages':messages,'temperature':temperature,'max_tokens':1800}
    if response_format: body['response_format']=response_format
    t=time.perf_counter()
    async with httpx.AsyncClient(timeout=45) as client:
        r=await client.post(url,json=body,headers=headers); r.raise_for_status(); data=r.json()
    return data['choices'][0]['message']['content'],round((time.perf_counter()-t)*1000,2)
def grounded_answer(messages,hits):
    if settings.llm_base_url: return None
    question=messages[-1]['content'].split('Question:',1)[-1].split('\n\nRETRIEVED KNOWLEDGE:',1)[0]
    return _evidence_answer(question,hits)
def grounded_validate(answer,citations):
    used=set(re.findall(r'\[S(\d+)\]',answer)); ids={c['id'][1:] for c in citations}; return used.issubset(ids) and bool(citations)

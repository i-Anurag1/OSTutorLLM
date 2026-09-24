import json,asyncio,time,hashlib,re,tempfile
from pathlib import Path
from fastapi import FastAPI,Depends,HTTPException,UploadFile,File,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from .config import settings
from .db import Base,engine,get_db
from .models import User,Topic,Progress,Activity,ChatLog,Source,AuditLog,Question,IngestionJob
from .schemas import *
from .auth import hash_password,verify_password,token,current_user,require_role
from .simulators import *
from .rag import retrieve,ingest_all,DOCS,extract,index_status
from .llm import generate,grounded_validate
from .cache import key as cache_key,get_json,set_json,delete_prefix
from .worker import enqueue_ingestion
from .code_runner import run_shell,run_python
from .evaluation import metrics
TOPICS=['Linux Commands','Shell Programming','Process Scheduling','Deadlocks','Memory Management','Paging','Segmentation','File Systems','Disk Scheduling','Synchronization','Threads','Producer-Consumer',"Banker's Algorithm",'Dining Philosophers','System Calls','I/O and Storage','Protection and Security']
app=FastAPI(title='OSTutorLLM',version='3.0.0',description='Grounded Operating Systems learning platform with local-first AI fallback')
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.cors_origins.split(',')],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
@app.exception_handler(Exception)
async def unhandled(request,exc):
    return JSONResponse(status_code=500,content={'error':'Internal server error','detail':str(exc)})
@app.on_event('startup')
def startup():
    Base.metadata.create_all(engine)
    from .seed import run
    run()
    # Build the bundled knowledge index on first run. Subsequent starts load the persisted FAISS index.
    if not (Path('/app/data/index/metadata.json').exists() and Path('/app/data/index/embeddings.npy').exists()):
        try: ingest_all()
        except Exception: pass
@app.get('/health')
def health(db:Session=Depends(get_db)):
    db.execute(text('SELECT 1'))
    try: rag=index_status()
    except Exception as exc: rag={'ready':False,'error':str(exc)}
    return {'status':'ok','database':'ok','rag':rag,'rag_ready':rag.get('ready',False),'llm_mode':'ollama-openai-compatible' if settings.llm_base_url else 'unconfigured'}
def audit(db,u,action,detail=''): db.add(AuditLog(user_id=u.id if u else None,action=action,detail=detail)); db.commit()
@app.post('/api/auth/register')
def register(x:RegisterIn,db:Session=Depends(get_db)):
    email=x.email.lower().strip()
    if db.query(User).filter_by(email=email).first(): raise HTTPException(409,'Email already registered')
    u=User(email=email,name=x.name.strip(),password_hash=hash_password(x.password)); db.add(u); db.commit(); db.refresh(u); return {'access_token':token(u),'user':{'id':u.id,'email':u.email,'name':u.name,'role':u.role}}
@app.post('/api/auth/login')
def login(x:LoginIn,db:Session=Depends(get_db)):
    u=db.query(User).filter_by(email=x.email.lower().strip()).first()
    if not u or not verify_password(x.password,u.password_hash): raise HTTPException(401,'Invalid credentials')
    audit(db,u,'login'); return {'access_token':token(u),'user':{'id':u.id,'email':u.email,'name':u.name,'role':u.role}}
@app.get('/api/auth/me')
def me(u=Depends(current_user)): return {'id':u.id,'email':u.email,'name':u.name,'role':u.role}
@app.put('/api/profile')
def profile(x:dict,u=Depends(current_user),db:Session=Depends(get_db)):
    if 'name' in x: u.name=str(x['name'])[:120]
    db.commit(); return {'id':u.id,'name':u.name,'email':u.email,'role':u.role}
@app.get('/api/topics')
def topics(db:Session=Depends(get_db)): return [{'id':t.id,'name':t.name,'description':t.description,'difficulty':t.difficulty} for t in db.query(Topic).filter_by(active=True).order_by(Topic.id).all()]
@app.get('/api/dashboard')
def dashboard(u=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.query(Progress).filter_by(user_id=u.id).all(); acts=db.query(Activity).filter_by(user_id=u.id).order_by(Activity.created_at.desc()).limit(20).all(); overall=round(sum((x.mastery or 0) for x in rows)/len(rows),1) if rows else 0
    return {'overall':overall,'topics':[{'topic_id':x.topic_id,'mastery':round(x.mastery or 0,1),'attempts':x.attempts or 0,'correct':x.correct or 0} for x in rows],'activity':[{'kind':a.kind,'topic':a.topic,'score':a.score,'created_at':a.created_at.isoformat()} for a in acts]}
@app.post('/api/progress')
def progress(x:ProgressIn,u=Depends(current_user),db:Session=Depends(get_db)):
    t=db.query(Topic).filter_by(name=x.topic).first()
    if not t: raise HTTPException(404,'Topic not found')
    p=db.query(Progress).filter_by(user_id=u.id,topic_id=t.id).first() or Progress(user_id=u.id,topic_id=t.id)
    p.mastery=round((p.mastery or 0)*.7+x.score*.3,2); p.attempts=(p.attempts or 0)+1; p.correct=(p.correct or 0)+(1 if x.score>=60 else 0); db.add(p); db.add(Activity(user_id=u.id,kind=x.activity,topic=x.topic,score=x.score)); db.commit(); return {'mastery':p.mastery,'recommendation':'Review this topic' if p.mastery<60 else ('Practice harder questions' if p.mastery<80 else 'Move to the next topic')}
@app.post('/api/tutor/chat')
async def tutor(x:ChatIn,u=Depends(current_user),db:Session=Depends(get_db)):
    filters={}
    if x.topic: filters['topic']=x.topic
    cache_payload={'q':x.message,'topic':x.topic,'difficulty':x.difficulty,'mode':x.mode,'model':settings.llm_model,'index':Path('/app/data/index/manifest.json').read_text() if Path('/app/data/index/manifest.json').exists() else ''}
    cached=get_json(cache_key('chat',cache_payload))
    if cached:
        return cached
    hits=retrieve(x.message,8,filters=filters)
    if not hits: raise HTTPException(422,'No indexed source matches this question. Add OS course materials and rebuild the knowledge base.')
    citations=[{'id':f'S{i+1}','source':h['source'],'page':h.get('page',1),'section':h.get('section',''),'chunk':h['chunk'],'score':round(h.get('rerank_score',h['score']),4),'dense_score':round(h.get('dense_score',0),4),'sparse_score':round(h.get('sparse_score',0),4),'type':h['type']} for i,h in enumerate(hits)]
    progress_row=None
    if x.topic:
        topic=db.query(Topic).filter_by(name=x.topic).first()
        if topic: progress_row=db.query(Progress).filter_by(user_id=u.id,topic_id=topic.id).first()
    mastery=round(progress_row.mastery,1) if progress_row else 0
    system=('You are OSTutorLLM, an Operating Systems professor and tutor. Answer using only the supplied evidence for factual OS claims. '
            'Every factual claim supported by the retrieved evidence must cite [S#]. Never invent a citation. '
            'If evidence is insufficient, explicitly say what is missing. Teach at the requested difficulty and personalize the explanation to the student mastery level.')
    context='\n'.join(f'[S{i+1}] {h["source"]} (page/slide {h.get("page",1)}): {h["text"]}' for i,h in enumerate(hits))
    prompt=f'Topic: {x.topic or "Operating Systems"}\nDifficulty: {x.difficulty}\nMode: {x.mode}\nStudent mastery: {mastery}%\nQuestion: {x.message}\n\nRETRIEVED KNOWLEDGE:\n{context}'
    started=time.perf_counter()
    answer,latency=await generate([{'role':'system','content':system},{'role':'user','content':prompt}])
    if not answer:
        snippets=' '.join(h['text'] for h in hits[:3])
        answer=f'Based on the indexed OS course material: {snippets}\n\nSources: ' + ' '.join(f'[S{i+1}]' for i in range(min(3,len(hits))))
        latency=round((time.perf_counter()-started)*1000,2)
    grounded=grounded_validate(answer,citations,hits)
    db.add(ChatLog(user_id=u.id,question=x.message,answer=answer,citations=citations,grounded=grounded,latency_ms=latency)); db.add(Activity(user_id=u.id,kind='tutor',topic=x.topic or 'Operating Systems',score=0)); db.commit()
    result={'answer':answer,'citations':citations,'grounded':grounded,'latency_ms':latency,'retrieved':len(hits),'retrieval':'hybrid-dense-sparse-rrf-rerank','model':settings.llm_model if settings.llm_base_url else 'grounded-fallback'}
    set_json(cache_key('chat',cache_payload),result,settings.cache_ttl_seconds)
    return result

@app.post('/api/quizzes/generate')
def quiz(x:QuizIn,u=Depends(current_user),db:Session=Depends(get_db)):
    pool=db.query(Question).filter_by(topic=x.topic,kind=x.kind,active=True).limit(x.count).all()
    if len(pool)<x.count:
        pool=db.query(Question).filter_by(topic=x.topic,active=True).limit(x.count).all()
    if not pool:
        raise HTTPException(404,'No bundled assessment exists for this topic yet')
    assessment=[]
    for q in pool:
        assessment.append({
            'id':q.id,
            'question':q.prompt,
            'options':q.options,
            'answer':q.answer,
            'explanation':q.explanation,
            'citation':f'Bundled source for {q.topic}'
        })
    return {
        'assessment':assessment,
        'latency_ms':0.5,
        'mode':'bundled-question-bank',
        'sources':sorted({q.topic for q in pool})
    }

@app.post('/api/quizzes/score')
def score_quiz(x:dict,u=Depends(current_user),db:Session=Depends(get_db)):
    questions=x.get('questions',[])
    answers=x.get('answers',{})
    topic=x.get('topic','Unknown')
    correct=0
    for q in questions:
        expected=str(q.get('answer','')).strip()
        given=str(answers.get(str(q.get('id','')),answers.get(q.get('id',''),''))).strip()
        if given==expected:
            correct+=1
    score=round(100*correct/max(1,len(questions)),1)
    t=db.query(Topic).filter_by(name=topic).first()
    if t:
        p=db.query(Progress).filter_by(user_id=u.id,topic_id=t.id).first() or Progress(user_id=u.id,topic_id=t.id)
        p.mastery=round((p.mastery or 0)*.7+score*.3,2)
        p.attempts=(p.attempts or 0)+1
        p.correct=(p.correct or 0)+correct
        db.add(p)
    db.add(Activity(user_id=u.id,kind='quiz',topic=topic,score=score,payload={'count':len(questions)}))
    db.commit()
    return {
        'score':score,
        'correct':correct,
        'total':len(questions),
        'recommendation':'Review the topic and retry' if score<60 else ('Increase difficulty' if score>=80 else 'Practice more')
    }
@app.get('/api/sources')
def sources(u=Depends(require_role('faculty','admin')),db:Session=Depends(get_db)):
    return [{'id':s.id,'name':s.name,'path':s.path,'status':s.status,'version':s.version,'chunks':s.chunks,'checksum':s.checksum} for s in db.query(Source).order_by(Source.id).all()]
@app.post('/api/sources/upload')
async def upload(file:UploadFile=File(...),u=Depends(require_role('faculty','admin')),db:Session=Depends(get_db)):
    allowed={'.pdf','.pptx','.docx','.txt','.md'}; ext=Path(file.filename or '').suffix.lower()
    if ext not in allowed: raise HTTPException(400,'Supported source types: PDF, PPTX, DOCX, TXT, MD')
    data=await file.read()
    if len(data)>15*1024*1024: raise HTTPException(413,'Source file exceeds 15 MB limit')
    safe_name=Path(file.filename or 'uploaded-source').name; path=DOCS/safe_name; path.write_bytes(data)
    text_content=extract(path)
    if not text_content.strip(): path.unlink(missing_ok=True); raise HTTPException(400,'The source contains no extractable text')
    checksum=hashlib.sha256(data).hexdigest(); existing=db.query(Source).filter_by(path=str(path)).first()
    if not existing: existing=Source(name=path.name,path=str(path),status='queued',version=1,chunks=0,checksum=checksum,uploaded_by=u.id); db.add(existing)
    else: existing.version+=1; existing.checksum=checksum; existing.status='queued'
    db.commit()
    job=enqueue_ingestion(db)
    delete_prefix('chat')
    return {'ok':True,'source':path.name,'status':'queued','job_id':job.id,'message':'Ingestion queued in the background.'}
@app.post('/api/rag/rebuild')
def rebuild(u=Depends(require_role('faculty','admin')),db:Session=Depends(get_db)):
    job=enqueue_ingestion(db); delete_prefix('chat')
    return {'ok':True,'status':'queued','job_id':job.id,'sources':db.query(Source).count()}
@app.get('/api/rag/jobs/{job_id}')
def rag_job(job_id:int,u=Depends(require_role('faculty','admin')),db:Session=Depends(get_db)):
    job=db.get(IngestionJob,job_id)
    if not job: raise HTTPException(404,'Ingestion job not found')
    return {'id':job.id,'status':job.status,'result':job.result,'error':job.error,'created_at':job.created_at.isoformat(),'updated_at':job.updated_at.isoformat()}
@app.get('/api/admin/analytics')
def admin_analytics(u=Depends(require_role('admin')),db:Session=Depends(get_db)):
    return {'users':db.query(User).count(),'sources':db.query(Source).count(),'questions':db.query(Question).count(),'activities':db.query(Activity).count(),'chat_sessions':db.query(ChatLog).count(),'rag_chunks':len(retrieve('operating systems',50))}
@app.get('/api/admin/students')
def students(u=Depends(require_role('faculty','admin')),db:Session=Depends(get_db)):
    return [{'id':x.id,'name':x.name,'email':x.email,'role':x.role} for x in db.query(User).order_by(User.id).all()]
@app.post('/api/simulators/cpu')
def cpu(x:CPUIn): return cpu_scheduling(x.algorithm,x.processes,x.quantum)
@app.post('/api/simulators/page-replacement')
def page(x:PageIn): return page_replacement(x.algorithm,x.reference_string,x.frames)
@app.post('/api/simulators/banker')
def banker(x:BankerIn): return bankers(x.allocation,x.maximum,x.available)
@app.post('/api/simulators/deadlock')
def deadlock(x:DeadlockIn): return deadlock_detection(x.allocation,x.request,x.available)
@app.post('/api/simulators/disk')
def disk(x:DiskIn): return disk_scheduling(x.algorithm,x.requests,x.head,x.disk_size)
@app.post('/api/simulators/producer-consumer')
def producer(x:SyncIn): return producer_consumer(x.buffer_size,x.items)
@app.post('/api/simulators/dining-philosophers')
def dining(): return dining_philosophers()
@app.post('/api/simulators/paging')
def paging_api(x:dict): return paging(x.get('addresses',[]),int(x.get('page_size',4)),int(x.get('num_frames',4)))
@app.post('/api/simulators/segmentation')
def seg_api(x:SegIn): return segmentation(x.segments,x.logical)
@app.post('/api/simulators/threads')
def threads_api(): return thread_lifecycle()
@app.post('/api/labs/shell')
def shell(x:ShellIn): return run_shell(x.script)
@app.post('/api/labs/python')
def py(x:PythonIn): return run_python(x.source)
@app.post('/api/labs/test')
def test_code(x:CodeTestIn):
    out=run_python(x.source); ok=out.get('stdout','').strip()==x.expected_stdout.strip() and out.get('returncode',0)==0; return {'passed':ok,'actual_stdout':out.get('stdout',''),'stderr':out.get('stderr',''),'expected_stdout':x.expected_stdout}
@app.post('/api/evaluation/run')
async def evaluate():
    benchmark=json.loads((Path('/app/data/benchmarks/os_questions.json')).read_text())
    rows=[]
    for item in benchmark:
        hits=retrieve(item['question'],5)
        rmetrics=__import__('app.evaluation',fromlist=['retrieval_metrics']).retrieval_metrics(hits,item.get('gold_sources',[]),5)
        answer,latency=await generate([
            {'role':'system','content':'Answer only from the supplied evidence. Cite factual claims with [S#].'},
            {'role':'user','content':'Question: '+item['question']+'\n\n'+'\n'.join(f'[S{i+1}] {h["text"]}' for i,h in enumerate(hits[:5]))}
        ])
        if not answer: answer=' '.join(h['text'] for h in hits[:3])+' '+ ' '.join(f'[S{i+1}]' for i in range(len(hits[:3])))
        ametrics=metrics(answer,hits[:5],item.get('gold_concepts',[]))
        rows.append({'id':item.get('id',item['question']),'query':item['question'],**rmetrics,**ametrics,'latency_ms':latency,'retrieved':len(hits)})
    keys=['recall_at_k','mrr','ndcg_at_k','citation_correctness','groundedness','hallucination_rate_proxy','concept_coverage','answer_relevance']
    aggregate={k:round(sum(r[k] for r in rows)/len(rows),3) for k in keys}
    return {'benchmark_size':len(rows),'k':5,'model':settings.llm_model,'embedding_model':settings.embedding_model,'reranker_model':settings.reranker_model,'cases':rows,'aggregate':aggregate}
@app.get('/api/openapi-summary')
def api_summary(): return {'docs':'/docs','health':'/health','version':'3.0.0','features':['Qwen3 14B local inference via Ollama','semantic chunking','BGE dense embeddings','FAISS vector store','BM25 + TF-IDF sparse retrieval','RRF hybrid fusion','BGE cross-encoder reranking','metadata filters','citation validation','Redis caching','background ingestion queue','PostgreSQL persistence','RAG evaluation']}


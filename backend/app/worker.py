from redis import Redis
from rq import Queue
from .config import settings
from .db import SessionLocal
from .models import IngestionJob, Source
from .rag import ingest_all


def run_ingestion(job_id):
    db=SessionLocal()
    job=db.get(IngestionJob, job_id)
    if not job: db.close(); return
    try:
        job.status='processing'; db.commit()
        result=ingest_all()
        job.status='completed'; job.result=result
        for src in db.query(Source).all():
            src.status='ready'
        db.commit()
    except Exception as exc:
        job.status='failed'; job.error=str(exc)[:2000]; db.commit(); raise
    finally:
        db.close()


def enqueue_ingestion(db):
    job=IngestionJob(status='queued'); db.add(job); db.commit(); db.refresh(job)
    q=Queue('ingestion',connection=Redis.from_url(settings.redis_url))
    q.enqueue(run_ingestion,job.id)
    return job


def worker_main():
    q=Queue('ingestion',connection=Redis.from_url(settings.redis_url))
    from rq import Worker
    Worker([q]).work()

if __name__=='__main__': worker_main()

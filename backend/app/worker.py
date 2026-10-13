from redis import Redis
from rq import Queue, Worker

from . import rag
from .config import settings
from .db import SessionLocal
from .models import IngestionJob
from .seed import sync_sources


def run_ingestion(job_id: int) -> None:
    db = SessionLocal()
    job = db.get(IngestionJob, job_id)
    if not job:
        db.close()
        return
    try:
        job.status = "processing"
        db.commit()
        result = rag.ingest_all()
        sync_sources()
        job.status, job.result = "completed", result
        db.commit()
    except Exception as exc:
        db.rollback()
        job.status, job.error = "failed", str(exc)[:2000]
        db.commit()
        raise
    finally:
        db.close()


def enqueue_ingestion(db) -> IngestionJob:
    job = IngestionJob(status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    Queue("ingestion", connection=Redis.from_url(settings.redis_url)).enqueue(run_ingestion, job.id, job_timeout=3600)
    return job


def worker_main() -> None:
    Worker([Queue("ingestion", connection=Redis.from_url(settings.redis_url))]).work()


if __name__ == "__main__":
    worker_main()

import os
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init
from dotenv import load_dotenv
load_dotenv()

# Get Redis URL from environment variable
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Initialize Celery
celery = Celery(
    "celery_worker",
    backend=redis_url,  # Stores task results
    broker=redis_url,   # Message queue
)

celery.conf.update(
    result_expires=3600,  # Cache results for 1 hour
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    broker_connection_retry_on_startup=True
)

celery.conf.beat_schedule = {
    "retry_failed_tasks": {
        "task": "celery_worker.retry_failed_moderation",
        "schedule": crontab(minute=0, hour="*"),  # Runs every hour
    }
}

# celery.conf.worker_concurrency = 4

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database import DATABASE_URL

@worker_process_init.connect
def init_worker(**kwargs):
    """
    Reinitialize The Async Engine in The Worker Process to Bind it to The Worker's Own Event Loop.
    """
    new_engine = create_async_engine(DATABASE_URL, future=True, echo=True)
    global AsyncSessionLocal
    AsyncSessionLocal = async_sessionmaker(
        bind=new_engine, class_=AsyncSession, expire_on_commit=False
    )
    print("Worker process initialized a new async engine!")
import tasks

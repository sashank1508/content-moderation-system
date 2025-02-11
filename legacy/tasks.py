import asyncio
import json
from typing import Optional
import httpx
import logging
from openai import OpenAI
import redis.asyncio as redis
from dotenv import load_dotenv
from asgiref.sync import async_to_sync
import concurrent.futures
from celery.signals import worker_shutdown
import os
# Database 
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database import get_db
# from database import AsyncSessionLocal
from database import get_sessionmaker
from models import ModerationResult
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Environment Setup
load_dotenv(override=True)
openai_api_key = os.getenv('OPENAI_API_KEY')
if not openai_api_key:
    raise EnvironmentError("OPENAI_API_KEY Is Missing In Environment Variables")
use_mock_server = os.getenv("USE_MOCK_SERVER", "false").strip().lower() == "true"
logging.info(f"USE_MOCK_SERVER is set to: {use_mock_server}")
openai_client = OpenAI(api_key=openai_api_key) if not use_mock_server else None

# Async Redis Connection
async def get_redis():
    return redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        encoding="utf-8",
        decode_responses=True)

# Global ThreadPoolExecutor
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

@worker_shutdown.connect
def shutdown_executor(*args, **kwargs):
    """ Ensures the ThreadPoolExecutor is Shut Down When Celery Stops. """
    logging.info("Shutting Down Celery Worker & ThreadPoolExecutor...")
    executor.shutdown(wait=True)
    logging.info("Shutdown Complete.")

# Import Celery instance from celery.py
from celery_worker import celery
# def run_async_in_executor(async_func, *args):
#     executor.submit(lambda: asyncio.run(async_func(*args)))

def run_async_in_executor(async_func, *args):
    return executor.submit(lambda: asyncio.run(async_func(*args)))

@celery.task(name="celery_worker.moderate_text_task", bind=True, max_retries=3)
def moderate_text_task(self, text_id: str, text: str)-> dict:
    """
    Processes (Celery Task) Text Moderation.
    Calls OpenAI or Mock API.
    """
    try:
        # loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(loop)
        # result = loop.run_until_complete(moderate_text(text_id, text))
        # return result
        # result = asyncio.run(asyncio.to_thread(moderate_text, text_id, text))
        # return result

        # # Force failure for testing (remove this later)
        # if "fail" in text.lower():
        #     raise Exception("Forced Failure for Testing")
        
        result = async_to_sync(moderate_text)(text_id, text)
        # result = asyncio.run(moderate_text(text_id, text))

        return result
    
    except Exception as e:
        logging.error(f"Task Failed: {e}")

        # # Store failed task in Dead Letter Queue (DLQ)
        # async_to_sync(push_to_dlq)(text_id, text, str(e))

        # # Store Failed Task in Dead Letter Queue (DLQ)
        # redis_client = await get_redis()
        # failed_task = {"text_id": text_id, "text": text, "error": str(e)}
        # await redis_client.rpush("dlq:moderation_failed", json.dumps(failed_task))
        # await redis_client.close()

        if "quota" in str(e).lower():
            logging.error("OpenAI Quota Exceeded, Skipping Retries.")
            return {"status": "failed", "reason": "Quota Exceeded"}

        # If max retries exceeded, don't retry again
        if self.request.retries >= 3:
            logging.warning(f"Task {text_id} Moved To DLQ After Max Retries.")

            # Store failed task in Dead Letter Queue (DLQ)
            # async_to_sync(push_to_dlq)(text_id, text, str(e))
            # asyncio.run(push_to_dlq(text_id, text, str(e)))

            # # Use ThreadPoolExecutor for optimized threading
            # with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            #     executor.submit(lambda: asyncio.run(push_to_dlq(text_id, text, str(e))))

            # executor.submit(lambda: asyncio.run(push_to_dlq(text_id, text, str(e))))
            run_async_in_executor(push_to_dlq, text_id, text, str(e))

            return {"status": "failed", "reason": str(e)}

        # Retry task with exponential backoff
        raise self.retry(exc=e, countdown=5 ** self.request.retries)

# async def push_to_dlq(text_id, text, error):
#     """
#     Push failed tasks to Dead Letter Queue (DLQ) in Redis.
#     """
#     redis_client = await get_redis()
#     failed_task = {"text_id": text_id, "text": text, "error": error}
#     await redis_client.rpush("dlq:moderation_failed", json.dumps(failed_task))
#     await redis_client.close()
#     print(f"Task {text_id} added to DLQ: {failed_task}")

async def push_to_dlq(text_id, text, error)-> None:
    """
    Push Failed Tasks to Dead Letter Queue (DLQ) in Redis.
    """
    redis_client = await get_redis()
    try:
        failed_task = {"text_id": text_id, "text": text, "error": error}
        await redis_client.rpush("dlq:moderation_failed", json.dumps(failed_task))
        logging.warning(f"Task {text_id} Added to DLQ: {failed_task}")
    except Exception as e:
        logging.error(f"Failed to push {text_id} to DLQ: {e}")
    finally:
        await redis_client.aclose()

async def moderate_text(text_id: str, text: str)-> dict:
    """Handles Text Moderation by Calling OpenAI or a Mock API, Storing Results in PostgreSQL and Caching in Redis."""
    redis_client = await get_redis()
    try:
        if use_mock_server:
            # Call Mock API
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post("http://127.0.0.1:8080/v1/moderations", json={"input": text})
                moderation_data = response.json()
        else:
            try:
                # Call OpenAI's API
                model = "omni-moderation-latest"
                moderation_response = await asyncio.to_thread(openai_client.moderations.create, model=model, input=text)
                moderation_data = moderation_response.model_dump()
            except Exception as e:
                logging.error(f"OpenAI API Error: {e}. Falling Back To Mock Server.")

                # Fallback: Call the Mock API instead
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post("http://127.0.0.1:8080/v1/moderations", json={"input": text})
                    moderation_data = response.json()
        
        # Store result in PostgreSQL
        await store_moderation_result(
            text_id=text_id,
            text=text,
            status="completed",
            moderation_data=moderation_data)
        
        # Store result in Redis (for caching)
        await redis_client.set(text_id, json.dumps(moderation_data), ex=3600)

        logging.info(f"Moderation Result Stored For {text_id} in PostgreSQL and Redis")
        return moderation_data

    finally:
        await redis_client.aclose()

# @celery.task(name="celery_worker.retry_failed_moderation")
# def retry_failed_moderation():
#     async_to_sync(_async_retry_failed_moderation)()

@celery.task(name="celery_worker.retry_failed_moderation")
def retry_failed_moderation()-> None:
    """
    Celery Task to Retry All Failed Moderation Tasks From DLQ.
    """
    # executor.submit(lambda: asyncio.run(_async_retry_failed_moderation()))
    run_async_in_executor(_async_retry_failed_moderation)

# async def _async_retry_failed_moderation():
#     """
#     The actual async function to retry failed moderation tasks.
#     """
#     redis_client = await get_redis()

#     while True:
#         failed_task = await redis_client.lpop("dlq:moderation_failed")
#         if not failed_task:
#             break  # Stop if no more tasks
        
#         task_data = json.loads(failed_task)
#         text_id = task_data["text_id"]
#         text = task_data["text"]

#         print(f"Retrying failed task {text_id}")
#         moderate_text_task.delay(text_id, text)  # Reschedule task

#     await redis_client.close()

@celery.task(name="celery_worker.moderate_image_task", bind=True, max_retries=3)
def moderate_image_task(self, image_id: str, image_url: str)-> dict:
    """
    Celery Task For Image Moderation.
    Calls OpenAI or Mock API.
    """
    try:        
        result = async_to_sync(moderate_image)(image_id, image_url)
        return result
    
    except Exception as e:
        logging.error(f"Image Moderation Task Failed: {e}")

        if "quota" in str(e).lower():
            logging.error("OpenAI Quota Exceeded, Skipping Retries.")
            return {"status": "failed", "reason": "Quota Exceeded"}

        # If max retries exceeded, don't retry again
        if self.request.retries >= 3:
            logging.warning(f"Image Task {image_id} Moved To DLQ After Max Retries.")
            run_async_in_executor(push_to_dlq, image_id, image_url, str(e))
            return {"status": "failed", "reason": str(e)}

        # Retry task with exponential backoff
        raise self.retry(exc=e, countdown=5 ** self.request.retries)

async def moderate_image(image_id: str, image_url: str)-> dict:
    """Handles Image Moderation by Calling OpenAI or a Mock API, Storing Results in PostgreSQL and Caching in Redis."""
    redis_client = await get_redis()
    try:
        if use_mock_server:
            # Call Mock API
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post("http://127.0.0.1:8080/v1/moderations/image", json={
                    "image_url": image_url
                })
                moderation_data = response.json()
        else:
            try:
                # Call OpenAI's API
                model = "omni-moderation-latest"
                moderation_response = await asyncio.to_thread(openai_client.moderations.create, model=model, input=[
                    {"type": "image_url", "image_url": {"url": image_url}}
                ])
                moderation_data = moderation_response.model_dump()
            except Exception as e:
                logging.error(f"OpenAI API Error: {e}. Falling Back To Mock Server.")

                # Fallback: Call the Mock API instead
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post("http://127.0.0.1:8080/v1/moderations/image", json={
                    "image_url": image_url
                })
                moderation_data = response.json()
        
        # Store result in PostgreSQL
        await store_moderation_result(
            text_id=image_id,
            text=image_url,
            status="completed",
            moderation_data=moderation_data)
        
        # Store result in Redis (for caching)
        await redis_client.set(image_id, json.dumps(moderation_data), ex=3600)

        logging.info(f"Image Moderation Result Stored For {image_id} in PostgreSQL and Redis")
        return moderation_data

    finally:
        await redis_client.aclose()

async def _async_retry_failed_moderation() -> None:
    """
    Async Function to Reprocess Failed Moderation Tasks From DLQ.
    Uses a Redis Lock to Prevent Multiple Instances From Running Simultaneously.
    """
    redis_client = await get_redis()
    
    lock = await redis_client.setnx("dlq:retry_lock", "1")  # Try to acquire lock
    if not lock:
        logging.info("Retry Task Already Running. Skipping...")
        await redis_client.aclose()
        return

    # Set expiration so if a crash happens, the lock is automatically released
    await redis_client.expire("dlq:retry_lock", 60)

    try:
        tasks_to_retry = []
        while True:
            failed_task = await redis_client.lpop("dlq:moderation_failed")
            if not failed_task:
                break  
            tasks_to_retry.append(json.loads(failed_task))

        await redis_client.aclose()  # Close Redis before processing tasks

        # for task_data in tasks_to_retry:
        #     text_id = task_data["text_id"]
        #     text = task_data["text"]
        #     logging.info(f"Retrying failed task {text_id}")
        #     moderate_text_task.delay(text_id, text)  # Reschedule task

        for task_data in tasks_to_retry:
            text_id = task_data["text_id"]

            # Determine if it's text or an image
            if "text" in task_data:
                text = task_data["text"]
                logging.info(f"Retrying Failed Text Moderation Task {text_id}")
                moderate_text_task.delay(text_id, text)  # Reschedule text task
            
            elif "image_url" in task_data:
                image_url = task_data["image_url"]
                logging.info(f"Retrying Failed Image Moderation Task {text_id}")
                moderate_image_task.delay(text_id, image_url)  # Reschedule image task

            else:
                logging.warning(f"Unknown Moderation Type for Task {text_id}, Skipping.")

    finally:
        await redis_client.delete("dlq:retry_lock")  # Release lock
        await redis_client.aclose()

# async def _async_retry_failed_moderation():
#     """
#     Async function to reprocess failed moderation tasks from DLQ.
#     """
#     redis_client = await get_redis()
    
#     # Fetch all failed tasks at once to minimize Redis calls
#     tasks_to_retry = []
    
#     while True:
#         failed_task = await redis_client.lpop("dlq:moderation_failed")
#         if not failed_task:
#             break  # Stop when no more tasks
        
#         tasks_to_retry.append(json.loads(failed_task))

#     await redis_client.close()  # Properly close Redis

#     for task_data in tasks_to_retry:
#         text_id = task_data["text_id"]
#         text = task_data["text"]
#         print(f"Retrying failed task {text_id}")

#         # Reschedule task in Celery
#         moderate_text_task.delay(text_id, text)

async def store_moderation_result(text_id: str, text: str, status: str, moderation_data: dict) -> Optional[ModerationResult]:
    """
    Stores or Updates The Moderation Result in PostgreSQL Inside Celery.
    If text_id Exists, Update The Record. Otherwise, Insert a New One.
    """
    SessionLocal = get_sessionmaker()  # This creates an engine on the current loop.
    async with SessionLocal() as db: 
        try:
            # Check if the text_id already exists
            result = await db.execute(select(ModerationResult).filter(ModerationResult.text_id == text_id))
            existing_entry = result.scalars().first()

            if existing_entry:
                # Update existing record
                existing_entry.text = text
                existing_entry.status = status
                existing_entry.result = moderation_data
                existing_entry.created_at = datetime.now()
                logging.info(f"Updated Existing Moderation Result For text_id: {text_id}")
            else:
                # Insert new record
                new_entry = ModerationResult(
                    text_id=text_id,
                    text=text,
                    status=status,
                    result=moderation_data,
                    created_at=datetime.now()
                )
                db.add(new_entry)
                logging.info(f"Inserted New Moderation Result For text_id: {text_id}")

            await db.commit()
            return existing_entry if existing_entry else new_entry

        except Exception as e:
            logging.error(f"Database error: {e}")
            await db.rollback()
            return None
        
# async def store_moderation_result(text_id: str, text: str, status: str, moderation_data: dict):
#     """
#     Stores the moderation result in PostgreSQL using asyncpg.
#     """
#     async for db in get_db():
#         new_entry = ModerationResult(
#             text_id=text_id,
#             text=text,
#             status=status,
#             result=moderation_data,
#             created_at=datetime.datetime.utcnow()
#         )
#         db.add(new_entry)
#         await db.commit()
#         await db.refresh(new_entry)
#         return new_entry

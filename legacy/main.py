import os
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request, APIRouter
from fastapi import UploadFile, File, Form
from fastapi.responses import PlainTextResponse
import base64
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, HttpUrl, Field
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from starlette.routing import Match
import redis.asyncio as redis
from tasks import celery
from dotenv import load_dotenv
import uuid
import json
from fastapi import Query
from datetime import datetime
from typing import Optional
from structlog import get_logger
from prometheus_client import Counter, Histogram, CollectorRegistry
from prometheus_client import REGISTRY, generate_latest,CONTENT_TYPE_LATEST
import prometheus_client.parser as parser

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import Depends, HTTPException
from database import get_db
from models import ModerationResult
import structlog
import logging

# Import Celery Task
from tasks import moderate_text_task, moderate_image_task
from celery.result import AsyncResult

# # Environment Setup
# load_dotenv()
# openai_api_key = os.getenv('OPENAI_API_KEY')
# if not openai_api_key:
#     raise EnvironmentError("OPENAI_API_KEY Is Missing In Environment Variables")
# use_mock_server = os.getenv("USE_MOCK_SERVER", "false").lower() == "true"
# openai_client = OpenAI(api_key=openai_api_key) if not use_mock_server else None

# Clear any previously registered metrics to avoid duplicates
for collector in list(REGISTRY._collector_to_names.keys()):
    REGISTRY.unregister(collector)

# Prometheus Metrics
REQUEST_COUNT = Counter("api_requests_total",
                        "Total API Requests", 
                        ["method", "endpoint"],
                        registry=REGISTRY)

REQUEST_LATENCY = Histogram("api_request_duration_seconds",
                            "API Request Duration",
                            ["method", "endpoint"],
                            registry=REGISTRY)

ERROR_COUNT = Counter("api_errors_total",
                      "Total API Errors",
                      ["method", "endpoint", "exception"],
                      registry=REGISTRY)

def pretty_json_serializer(event_dict, **kwargs):
    return json.dumps(event_dict, indent=4, sort_keys=True, **kwargs)

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),  # Timestamp in ISO format
        structlog.processors.JSONRenderer(serializer=pretty_json_serializer)
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

# Configure Structured Logging
log = structlog.get_logger()

# Async Redis Connection
load_dotenv()
async def get_redis():
    return redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        encoding="utf-8",
        decode_responses=True
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = None
    try:
        redis_client = await get_redis()
        await FastAPILimiter.init(redis_client)
        log.info("FastAPI Rate Limiter Initialized")
        yield
    except Exception as e:
        log.error("Redis Initialization Failed", error=str(e))
    finally:
        if redis_client:
            await redis_client.aclose()
            log.info("Redis Connection Closed.")

# FastAPI Application Setup
app = FastAPI(
    docs_url="/",
    title="Content Moderation System",
    version="1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)
    
# Pydantic Model For Text Moderation Requests
class TextModerationRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to be Moderated")

# Pydantic Model For Image Moderation Requests
class ImageModerationRequest(BaseModel):
    image_url: HttpUrl

# Pydantic Model For Moderation Results
class ModerationResultResponse(BaseModel):
    message: str
    id: str
    text: str
    status: str
    result: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# # Function to call OpenAI's moderation API
# async def moderate(text: str):
#     model = "omni-moderation-latest"
#     response = openai_client.moderations.create(model=model, input=text)
#     return response

# # Function to call OpenAI's moderation API asynchronously
# async def moderate(text_id: str, text: str):
#     model = "omni-moderation-latest"
#     response = await asyncio.to_thread(openai_client.moderations.create, model=model, input=text)
    
#     # Store result in Redis
#     redis_client = await get_redis()
#     await redis_client.set(text_id, json.dumps(response.model_dump()), ex=3600)  # Expire in 1 hour
#     await redis_client.close()
#     print(f"Moderation Result Stored For {text_id}")

# # Function to call either OpenAI's API or the Mock API
# async def moderate(text_id: str, text: str):
#     try:    
#         if use_mock_server:
#             # Call Mock API
#             async with httpx.AsyncClient() as client:
#                 response = await client.post("http://127.0.0.1:8080/v1/moderations", json={"input": text})
#                 moderation_data = response.json()
#         else:
#             # Call OpenAI's API
#             model = "omni-moderation-latest"
#             moderation_data = await asyncio.to_thread(openai_client.moderations.create, model=model, input=text)

#     except Exception as e:
#         print(f"OpenAI API Error: {e}. Falling Back To Mock Server.")
#         # If OpenAI Fails, Fall Back To Mock API
#         async with httpx.AsyncClient() as client:
#             response = await client.post("http://127.0.0.1:8080/v1/moderations", json={"input": text})
#             moderation_data = response.json()

#     # Store result in Redis
#     redis_client = await get_redis()
#     await redis_client.set(text_id, json.dumps(moderation_data), ex=3600)  # Expire in 1 hour
#     await redis_client.close()
#     print(f"Moderation Result Stored For {text_id}")

async def store_pending_status(text_id: str, text: str, celery_task_id: str) -> None:
    """Stores pending status in Redis for quick retrieval."""
    redis_client = await get_redis()
    try:
        await redis_client.set(
            f"status:{text_id}",
            json.dumps({"status": "Processing",
                        "text": text,
                        "celery_task_id": celery_task_id}),
            ex=600)     # Expires in 10 minutes
        # log.info("Stored Pending Status", text_id=text_id, celery_task_id=celery_task_id)
    finally: 
        await redis_client.aclose()

# # API endpoint for text moderation (With Rate Limiting)
# @app.post("/api/v1/moderate/text", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
# async def moderate_text(request: TextModerationRequest):
#     try:
#         text = request.text
#         moderation = await moderate(text)
#         return {"message": "Text Moderation Is Processing",
#                 "text": text,
#                 "id": moderation}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# # API Endpoint For Text Moderation (With Rate Limiting and Async Processing)
# @app.post("/api/v1/moderate/text", tags=["Steps AI"], dependencies=[Depends(RateLimiter(times=10, seconds=60))])
# async def moderate_text(request: TextModerationRequest, background_tasks: BackgroundTasks):
#     try:
#         text = request.text
#         text_id = str(uuid.uuid4())  # Generate a unique ID
#         background_tasks.add_task(moderate, text_id, text)  # Offload processing
#         return {"message": "Text Moderation Is Processing", "text": text, "id": text_id}
    
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# **Middleware to Track Request Count And Duration**
@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    method = request.method
    endpoint = request.url.path

    # Normalize Dynamic Routes
    for route in request.app.router.routes:
        match, _ = route.matches(request.scope)
        if match == Match.FULL:
            endpoint = route.path  # Replace with normalized path
            break

    REQUEST_COUNT.labels(method=method, endpoint=endpoint).inc()  # Increment request count
    with REQUEST_LATENCY.labels(method=method, endpoint=endpoint).time():  # Track request duration
        response = await call_next(request)

    return response

# API Endpoint For Text Moderation (Now Uses Celery)
@app.post("/api/v1/moderate/text", dependencies=[Depends(RateLimiter(times=10, seconds=60))], tags=["POST"])
async def moderate_text(request: TextModerationRequest, background_tasks: BackgroundTasks) -> dict:
    if not request.text.strip():  # Ensure text is not empty or just spaces
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    """
    ## **Moderate Text**
    
    **Description:**  
    
    Asynchronously processes text moderation using Celery.
    
    ### **Request Body**:
    - **`text`**:  The text content to be moderated.
    
    ### **Response Body**:
    - **`message`**:  Confirmation that the moderation task is queued.

    - **`text`**:  The submitted text content.

    - **`id`**:  Unique ID for tracking the moderation task.
    ---
    """
    try:
        text = request.text
        text_id = str(uuid.uuid4())  # Generate unique ID

        # Send task to Celery
        celery_task = moderate_text_task.delay(text_id, text)

        # BackgroundTasks for quick Redis status update
        background_tasks.add_task(store_pending_status, text_id, text, celery_task.id)

        log.info("Text Moderation Task Queued", text_id=text_id, text=text)
        return {"message": "Text Moderation Task Queued",
                "text": text,
                # "celery_task_id": celery_task.id,
                "id": text_id}
    
    except Exception as e:
        ERROR_COUNT.labels(method="POST", endpoint="/api/v1/moderate/text", exception=str(e)).inc()
        log.error("Error in Text Moderation", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# API Endpoint For Image Moderation (Uses Celery)
@app.post("/api/v1/moderate/image", dependencies=[Depends(RateLimiter(times=10, seconds=60))], tags=["POST"])
async def moderate_image(request: ImageModerationRequest, background_tasks: BackgroundTasks) -> dict:
    """
    ## **Moderate Image**
    
    **Description:**

    Asynchronously processes image moderation using Celery.
    
    ### **Request Body**:
    - **`image_url`**:  The URL of the image to be moderated.
    
    ### **Response Body**:
    - **`message`**:  Confirmation that the moderation task is queued.

    - **`image_url`**:  The submitted image URL.

    - **`id`**:  Unique ID for tracking the moderation task.
    ---
    """
    try:
        image_url = str(request.image_url)
        image_id = str(uuid.uuid4())  # Generate unique ID

        # Send task to Celery
        celery_task = moderate_image_task.delay(image_id, image_url)

        # Store pending status in Redis
        background_tasks.add_task(store_pending_status, image_id, image_url, celery_task.id)
        
        log.info("Image Moderation Task Queued", image_id=image_id, image_url=image_url)
        return {"message": "Image Moderation Task Queued",
                "image_url": image_url,
                "id": image_id}
    
    except Exception as e:
        ERROR_COUNT.labels(method="POST", endpoint="/api/v1/moderate/image", exception=str(e)).inc()
        log.error("Error in Image Moderation", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# # API Endpoint For Text Moderation (Now Uses Both BackgroundTasks & Celery)
# @app.post("/api/v1/moderate/text", dependencies=[Depends(RateLimiter(times=10, seconds=60))], tags=["Steps AI"])
# async def moderate_text(request: TextModerationRequest, background_tasks: BackgroundTasks):
#     try:
#         text = request.text
#         text_id = str(uuid.uuid4())  # Generate unique ID
        
#         # Store Request in Redis using BackgroundTasks
#         redis_client = await get_redis()
#         await redis_client.set(f"pending:{text_id}", json.dumps({"text": text}), ex=600)  # Expire in 10 minutes
#         await redis_client.close()

#         # Schedule Processing in Celery (Runs in Background)
#         background_tasks.add_task(moderate_text_task.delay, text_id, text)
        
#         return {"message": "Text Moderation Task Queued", "text": text, "id": text_id}
    
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# API Endpoint To Retrieve Failed Moderation Tasks
@app.get("/api/v1/moderation/failed", tags=["GET"])
async def get_failed_tasks() -> dict:
    """
    ## **Retrieve Failed Moderation Tasks**
    
    **Description:**  

    Fetches all failed moderation tasks stored in the Dead Letter Queue (DLQ) in Redis.

    ### **Response Body**:
    - **`status`**:  Indicates whether failed tasks were found or not.

    - **`message`**:  A message stating whether there are failed tasks or if the DLQ is empty.
    
    - **`failed_tasks`**:  A list of failed moderation tasks (if any exist).

    ---
    """
    redis_client = await get_redis()

    try:
        failed_tasks = await redis_client.lrange("dlq:moderation_failed", 0, -1)
        
        if not failed_tasks:
            return {"status": "Not Found", "message": "No Failed Tasks in DLQ"}
        
        return {
            "failed_tasks": [json.loads(task) for task in failed_tasks]
        }
    except Exception as e:
        ERROR_COUNT.labels(method="GET", endpoint="/api/v1/moderation/failed", exception=str(e)).inc()
        raise HTTPException(status_code=500, detail=f"Error fetching failed tasks: {str(e)}")
    finally:
        await redis_client.aclose()

# API Endpoint To Clear Failed Moderation Tasks
@app.delete("/api/v1/moderation/failed/clear", tags=["DELETE"])
async def clear_failed_tasks()-> dict:
    """
    ## **Clear All Failed Moderation Tasks**
    
    **Description:**  

    Deletes all failed moderation tasks from the Dead Letter Queue (DLQ) in Redis.

    ### **Response Body**:
    - **`status`**:  Indicates whether the deletion was successful or if no failed tasks were found.

    - **`message`**:  A confirmation message indicating whether all tasks were cleared or if no failed tasks were present.

    ---
    """
    redis_client = await get_redis()

    try:
        # Check if there are any failed tasks
        failed_tasks = await redis_client.lrange("dlq:moderation_failed", 0, -1)

        if not failed_tasks:
            return {"status": "Not Found", "message": "No Failed Tasks in DLQ to Clear"}

        # If tasks exist, delete the DLQ
        await redis_client.delete("dlq:moderation_failed")
        return {"status": "success", "message": "All Failed Moderation Tasks Cleared From DLQ"}

    except Exception as e:
        ERROR_COUNT.labels(method="DELETE", endpoint="/api/v1/moderation/failed/clear", exception=str(e)).inc()
        raise HTTPException(status_code=500, detail=f"Error clearing failed tasks: {str(e)}")
    
    finally:
        await redis_client.aclose()

# API Endpoint To Clear a Specific Failed Moderation Task
@app.delete("/api/v1/moderation/failed/{id}/clear", tags=["DELETE"])
async def clear_failed_task_by_id(id: str)-> dict:
    """
    ## **Clear Failed Moderation Task by ID**
    
    **Description:**

    Removes a specific failed moderation task from the Dead Letter Queue (DLQ) in Redis.

    ### **Path Parameter**:
    - **`id`**:  The unique identifier of the failed moderation task.

    ### **Response Body**:
    - **`status`**:  Indicates if the deletion was successful or if the task was not found.

    - **`message`**:  A confirmation message or an error message if the task was not found.

    ---
    """
    redis_client = await get_redis()

    try:
        # Fetch all failed tasks
        failed_tasks = await redis_client.lrange("dlq:moderation_failed", 0, -1)

        if not failed_tasks:
            return {"status": "Not Found", "message": "No Failed Tasks in DLQ"}

        # Convert tasks to JSON objects
        filtered_tasks = []
        removed_task = None

        for task in failed_tasks:
            task_data = json.loads(task)
            if task_data["text_id"] == id:
                removed_task = task_data  # Mark this for deletion
            else:
                filtered_tasks.append(task)  # Keep other tasks

        if removed_task:
            # Clear DLQ and reinsert only non-matching tasks
            await redis_client.delete("dlq:moderation_failed")
            if filtered_tasks:
                await redis_client.rpush("dlq:moderation_failed", *filtered_tasks)

            return {"status": "success", "message": f"Failed Task with ID {id} Removed from DLQ"}

        return {"status": "Not Found", "message": f"No Failed Task Found with ID {id}"}

    except Exception as e:
        ERROR_COUNT.labels(method="DELETE", endpoint="/api/v1/moderation/failed/{id}/clear", exception=str(e)).inc()
        raise HTTPException(status_code=500, detail=f"Error clearing failed task: {str(e)}")
    
    finally:
        await redis_client.aclose()
    
# @app.get("/api/v1/moderation/{text_id}/result", tags=["Steps AI"])
# async def get_moderation_result(text_id: str, db: AsyncSession = Depends(get_db)):
#     """
#     Retrieves a moderation result from PostgreSQL using asyncpg.
#     """
#     result = await db.execute(select(ModerationResult).filter(ModerationResult.text_id == text_id))
#     moderation = result.scalars().first()

#     if not moderation:
#         raise HTTPException(status_code=404, detail="Moderation Result Not Found")

#     return {
#         "id": moderation.text_id,
#         "text": moderation.text,
#         "status": moderation.status,
#         "result": moderation.result,
#         "created_at": moderation.created_at
#     }

# API Endpoint To Retrieve All Moderation Results
@app.get("/api/v1/moderation/all", tags=["GET"])
async def get_all_moderation_tasks(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
)-> dict:
    """
    ## **Retrieve All Moderation Tasks**
    
    **Description:**  

    Fetches all moderation tasks from the database with pagination.

    ### **Query Parameters**:
    - **`offset`** *(integer, default=0)*:  The starting index for pagination.
    
    - **`limit`** *(integer, default=10, min=1, max=100)*:  The maximum number of records to retrieve.

    ### **Response Body**:
    - **`total_count`**:  The total number of moderation records in the database.

    - **`offset`**:  The starting index for the records returned.

    - **`limit`**:  The number of records returned per request.

    - **`tasks`**:  A list of moderation tasks, each containing:

      - **`id`**:  Unique identifier of the moderation task.

      - **`text`**:  The moderated text content.

      - **`status`**:  The current moderation status.

      - **`result`**:  The moderation analysis result.

      - **`created_at`**:  Timestamp when the moderation task was created.

    ---
    """
    try:
        # Get total count
        total_count = await db.execute(text("SELECT COUNT(*) FROM moderation_results"))
        total_count = total_count.scalar()

        if total_count == 0:
            return {"message": "Database is Empty"}

        # Fetch records
        query = select(ModerationResult).offset(offset).limit(limit)
        result = await db.execute(query)
        tasks = result.scalars().all()

        if not tasks:
            return {"message": f"No Records Found for Limit={limit}, Offset={offset}. Total Records: {total_count}"}

        return {
            "total_count": total_count,
            "offset": offset,
            "limit": limit,
            "tasks": [
                {
                    "id": task.text_id,
                    "text": task.text,
                    "status": task.status,
                    "result": task.result,
                    "created_at": task.created_at
                }
                for task in tasks
            ]
        }

    except Exception as e:
        ERROR_COUNT.labels(method="GET", endpoint="/api/v1/moderation/all", exception=str(e)).inc()
        return {"database_status": "error", "message": str(e)}
    
# API Endpoint To Clear All Moderation Results
@app.delete("/api/v1/moderation/clear_all", tags=["DELETE"])
async def clear_all_moderation_results(db: AsyncSession = Depends(get_db))-> dict:
    """
    ## **Delete All Moderation Results**
    
    **Description:**  

    Deletes all records from the `moderation_results` table, clearing the database of all stored moderation data.

    ### **Response Body**:
    - **`status`**:  Indicates if the deletion was successful or if an error occurred.
    
    - **`message`**:  A confirmation message indicating whether all records were deleted or if an error was encountered.

    ---
    """
    try:
        await db.execute(text("DELETE FROM moderation_results"))
        await db.commit()
        return {"status": "success", "message": "All Moderation Results Have Been Deleted From The Database."}
    
    except Exception as e:
        ERROR_COUNT.labels(method="DELETE", endpoint="/api/v1/moderation/clear_all", exception=str(e)).inc()
        await db.rollback()
        return {"status": "error", "message": str(e)}

# API Endpoint To Clear Moderation Result By ID
@app.delete("/api/v1/moderation/clear/{id}", tags=["DELETE"])
async def clear_moderation_result_by_id(id: str, db: AsyncSession = Depends(get_db))-> dict:
    """
    ## **Delete Moderation Result by ID**
    
    **Description:** 
     
    Deletes a specific moderation result from the database based on the provided `id`.

    ### **Path Parameter**:
    - **`id`**:  The unique identifier of the moderation task to be deleted.

    ### **Response Body**:
    - **`status`**:  Indicates if the deletion was successful or if an error occurred.

    - **`message`**:  A confirmation message or an error message if the record was not found.

    ---
    """
    try:
        result = await db.execute(select(ModerationResult).filter(ModerationResult.text_id == id))
        moderation = result.scalars().first()

        if not moderation:
            raise HTTPException(status_code=404, detail=f"Moderation Result With ID {id} Not Found.")

        await db.delete(moderation)
        await db.commit()
        return {"status": "success", "message": f"Moderation Result With ID {id} Has Been Deleted."}

    except Exception as e:
        ERROR_COUNT.labels(method="DELETE", endpoint="/api/v1/moderation/clear/{id}", exception=str(e)).inc()
        await db.rollback()
        return {"status": "error", "message": str(e)}

# API Endpoint To Retrieve Moderation Results
@app.get("/api/v1/moderation/{id}", response_model=ModerationResultResponse, tags=["GET"])
async def get_moderation_result(id: str, db: AsyncSession = Depends(get_db))-> dict:
    """
    ## **Retrieve Moderation Result**
    
    **Description:**  

    Fetches the moderation result for a given `id`. It first checks Redis for the result, and if not found, queries the database.

    ### **Path Parameter**:
    - **`id`**:  The unique identifier of the moderation task.

    ### **Response Body**:
    - **`message`**:  Status message indicating where the result was found.

    - **`id`**:  The unique identifier of the moderation task.

    - **`status`**:  The current moderation status (`Processing`, `Completed`, or `Not Found`).

    - **`result`**:  The moderation analysis result.
    
    - **`created_at`**:  Timestamp of when the moderation task was created.

    ---
    """
    redis_client = await get_redis()
    try:
        # Check if task is still "Processing"
        status = await redis_client.get(f"status:{id}")
        if status:
            status_data = json.loads(status)
            celery_task_id = status_data.get("celery_task_id")

            if celery_task_id:
                task_status = AsyncResult(celery_task_id)

                if task_status.state in ["PENDING", "STARTED"]:
                    return {
                        "id": id,
                        "status": task_status.state,
                        "message": f"Moderation Task is Currently {task_status.state} in Celery."
                    }

        result = await redis_client.get(id) 
        if result:
            try:
                parsed_result = json.loads(result)
                created_at = parsed_result.get("created_at")
                if created_at:
                    created_at = datetime.fromisoformat(created_at)
                else:
                    created_at = datetime.now()
                return {"message": "Moderation Result Found in Redis", 
                        "id": id,
                        "status": "Completed",
                        "text": parsed_result.get("text", ""),
                        "created_at": created_at,
                        "result": parsed_result}
                        
            except json.JSONDecodeError:
                raise HTTPException(status_code=500, detail="Error Parsing Moderation Result")
        
        # If not in Redis, check PostgreSQL
        db_result = await db.execute(select(ModerationResult).filter(ModerationResult.text_id == id))
        moderation = db_result.scalars().first()

        if not moderation:
            raise HTTPException(status_code=404, detail="Moderation Result Not Found in Redis or Database")
        
        # Return data from PostgreSQL
        return {
            "message": "Moderation Result Found in Database",
            "id": moderation.text_id,
            "text": moderation.text,
            "status": moderation.status,
            "result": moderation.result,
            "created_at": moderation.created_at
        }
        # return {"status": "Not Found", "message": "Moderation Result Not Found"}
            
    finally:
        await redis_client.aclose()

# API Endpoint To Check Database Connection
@app.get("/api/v1/debug/db", tags=["MONITORING"])
async def debug_db(db: AsyncSession = Depends(get_db))-> dict:
    """
    ## **Debug Database Connection**
    
    **Description:**  
    
    Checks the connection to the database and returns the number of records in the `moderation_results` table.

    ### **Response Body**:
    - **`database_status`**:  Indicates whether the database is connected or if there was an error.

    - **`row_count`**:  Number of records in the `moderation_results` table (if successful).

    - **`message`**:  Error message if the connection fails.

    ---
    """
    try:
        result = await db.execute(text("SELECT COUNT(*) FROM moderation_results"))
        count = result.scalar()

        return {"database_status": "connected", "row_count": count}
    
    except Exception as e:
        ERROR_COUNT.labels(method="GET", endpoint="/api/v1/debug/db", exception=str(e)).inc()
        return {"database_status": "error", "message": str(e)}
    
# # Prometheus Metrics Endpoint
@app.get("/stats", response_class=PlainTextResponse, tags=["MONITORING"])
async def metrics()->PlainTextResponse:
    """Returns Prometheus Metrics in Plain Text."""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    # return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)\

@app.get("/metrics/json", tags=["MONITORING"])
async def get_metrics_json()-> dict:
    """
    Returns Prometheus Metrics in JSON Format.
    """
    try:
        # Generate raw Prometheus metrics
        raw_metrics = generate_latest()

        # Parse metrics into JSON format
        parsed_metrics = {}
        for metric in parser.text_string_to_metric_families(raw_metrics.decode("utf-8")):
            parsed_metrics[metric.name] = {
                "type": metric.type,
                "help": metric.documentation,
                "values": [
                    {
                        "labels": sample.labels,
                        "value": sample.value
                    }
                    for sample in metric.samples
                ]
            }

        return parsed_metrics
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
async def check_database(db: AsyncSession)-> dict:
    """ Check if the database connection is working """
    try:
        result = await db.execute(text("SELECT 1"))
        return {"database": "connected"}
    except Exception as e:
        return {"database": "error", "details": str(e)}

async def check_redis()-> dict:
    """ Check if Redis is reachable """
    try:
        redis_client = redis.from_url("redis://redis:6379/0", encoding="utf-8", decode_responses=True)
        pong = await redis_client.ping()
        await redis_client.aclose()
        return {"redis": "connected"} if pong else {"redis": "error"}
    except Exception as e:
        return {"redis": "error", "details": str(e)}

async def check_celery()-> dict:
    """ Check if Celery workers are running (by sending a test task) """
    try:
        test_task = celery.send_task("celery_worker.moderate_text_task", args=["test_id", "test_text"])
        task_status = AsyncResult(test_task.id)

        if task_status.state:
            return {"celery": "running"}
        else:
            return {"celery": "error"}
    except Exception as e:
        return {"celery": "error", "details": str(e)}

# Health Check Endpoint
@app.get("/api/v1/health", tags=["MONITORING"])
async def health_check(db: AsyncSession = Depends(get_db))-> dict:
    """
    ## **Health Check Endpoint**
    
    **Checks API, Database, Redis, and Celery Worker Status.**
    """
    db_status = await check_database(db)
    redis_status = await check_redis()
    celery_status = await check_celery()

    health_status = {
        "api": "running",
        "status": "ok",
        "database": db_status,
        "redis": redis_status,
        "celery": celery_status
    }

    # If any component fails, return HTTP 500
    if "error" in db_status.values() or "error" in redis_status.values() or "error" in celery_status.values():
        raise HTTPException(status_code=500, detail=health_status)

    return health_status

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

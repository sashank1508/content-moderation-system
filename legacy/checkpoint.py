import os
import asyncio
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel
from contextlib import asynccontextmanager
from openai import OpenAI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as redis
from dotenv import load_dotenv
import uuid
import json
import httpx

# Environment Setup
load_dotenv()
openai_api_key = os.getenv('OPENAI_API_KEY')
if not openai_api_key:
    raise EnvironmentError("OPENAI_API_KEY Is Missing In Environment Variables")
use_mock_server = os.getenv("USE_MOCK_SERVER", "false").lower() == "true"
openai_client = OpenAI(api_key=openai_api_key) if not use_mock_server else None

# Async Redis Connection
async def get_redis():
    return redis.from_url("redis://localhost:6379", encoding="utf-8", decode_responses=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = None
    try:
        redis_client = await get_redis()
        await FastAPILimiter.init(redis_client)
        print("FastAPI Rate Limiter Initialized")
        yield
    except Exception as e:
        print(f"Redis Initialization Failed: {e}")
    finally:
        if redis_client:
            await redis_client.close()
            print("Redis Connection Closed.")

# FastAPI Application Setup
app = FastAPI(docs_url="/", title="Content Moderation System", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)
    
# Pydantic model for text moderation requests
class TextModerationRequest(BaseModel):
    text: str

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

# Function to call either OpenAI's API or the Mock API
async def moderate(text_id: str, text: str):
    try:    
        if use_mock_server:
            # Call Mock API
            async with httpx.AsyncClient() as client:
                response = await client.post("http://127.0.0.1:8080/v1/moderations", json={"input": text})
                moderation_data = response.json()
        else:
            # Call OpenAI's API
            model = "omni-moderation-latest"
            moderation_data = await asyncio.to_thread(openai_client.moderations.create, model=model, input=text)

    except Exception as e:
        print(f"OpenAI API Error: {e}. Falling Back To Mock Server.")
        # If OpenAI Fails, Fall Back To Mock API
        async with httpx.AsyncClient() as client:
            response = await client.post("http://127.0.0.1:8080/v1/moderations", json={"input": text})
            moderation_data = response.json()

    # Store result in Redis
    redis_client = await get_redis()
    await redis_client.set(text_id, json.dumps(moderation_data), ex=3600)  # Expire in 1 hour
    await redis_client.close()
    print(f"Moderation Result Stored For {text_id}")

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

# API Endpoint For Text Moderation (With Rate Limiting and Async Processing)
@app.post("/api/v1/moderate/text", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
async def moderate_text(request: TextModerationRequest, background_tasks: BackgroundTasks):
    try:
        text = request.text
        text_id = str(uuid.uuid4())  # Generate a unique ID
        background_tasks.add_task(moderate, text_id, text)  # Offload processing
        return {"message": "Text Moderation Is Processing", "text": text, "id": text_id}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# API Endpoint To Retrieve Moderation Results
@app.get("/api/v1/moderation/{id}")
async def get_moderation_result(id: str):
    redis_client = await get_redis()
    result = await redis_client.get(id)
    await redis_client.close()

    if result:
        try:
            parsed_result = json.loads(result)
            return {"message": "Moderation Result Found", "id": id, "result": parsed_result}
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Error Parsing Moderation Result")
    else:
        raise HTTPException(status_code=404, detail="Moderation Result Not Found Or Still Processing")

# Health check endpoint
@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
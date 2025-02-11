from fastapi import FastAPI
from pydantic import BaseModel
import random
import uuid

# Mock OpenAI API
mock_app = FastAPI()

# Request Model for Text Moderation
class MockModerationRequest(BaseModel):
    input: str

# Request Model for Image Moderation
class MockImageModerationRequest(BaseModel):
    image_url: str

@mock_app.post("/v1/moderations")
async def mock_moderate_text(request: MockModerationRequest)-> dict:
    """Simulates OpenAI's Moderation API Response For Text"""
    fake_response = {
        "id": "modr-" + str(uuid.uuid4()),
        "model": "omni-moderation-mock",
        "results": [
            {
                "flagged": random.choice([True, False]),
                "categories": {
                    "sexual": random.choice([True, False]),
                    "sexual/minors": random.choice([True, False]),
                    "harassment": random.choice([True, False]),
                    "harassment/threatening": random.choice([True, False]),
                    "hate": random.choice([True, False]),
                    "hate/threatening": random.choice([True, False]),
                    "illicit": random.choice([True, False]),
                    "illicit/violent": random.choice([True, False]),
                    "self-harm": random.choice([True, False]),
                    "self-harm/intent": random.choice([True, False]),
                    "self-harm/instructions": random.choice([True, False]),
                    "violence": random.choice([True, False]),
                    "violence/graphic": random.choice([True, False])
                },
                "category_scores": {
                    "sexual": round(random.uniform(0.0, 1.0), 7),
                    "sexual/minors": round(random.uniform(0.0, 1.0), 7),
                    "harassment": round(random.uniform(0.0, 1.0), 7),
                    "harassment/threatening": round(random.uniform(0.0, 1.0), 7),
                    "hate": round(random.uniform(0.0, 1.0), 7),
                    "hate/threatening": round(random.uniform(0.0, 1.0), 7),
                    "illicit": round(random.uniform(0.0, 1.0), 7),
                    "illicit/violent": round(random.uniform(0.0, 1.0), 7),
                    "self-harm": round(random.uniform(0.0, 1.0), 7),
                    "self-harm/intent": round(random.uniform(0.0, 1.0), 7),
                    "self-harm/instructions": round(random.uniform(0.0, 1.0), 7),
                    "violence": round(random.uniform(0.0, 1.0), 7),
                    "violence/graphic": round(random.uniform(0.0, 1.0), 7)
                },
                "category_applied_input_types": {
                    "sexual": ["text"],
                    "sexual/minors": [],
                    "harassment": ["text"],
                    "harassment/threatening": [],
                    "hate": [],
                    "hate/threatening": [],
                    "illicit": ["text"],
                    "illicit/violent": [],
                    "self-harm": ["text"],
                    "self-harm/intent": [],
                    "self-harm/instructions": [],
                    "violence": ["text"],
                    "violence/graphic": []
                }
            }
        ]
    }
    return fake_response

@mock_app.post("/v1/moderations/image")
async def mock_moderate_image(request: MockImageModerationRequest)-> dict:
    """Simulates OpenAI's Moderation API Response For Images."""
    fake_response = {
        "id": "modr-" + str(uuid.uuid4()),
        "model": "omni-moderation-mock",
        "results": [
            {
                "flagged": random.choice([True, False]),
                "image_url": request.image_url,
                "categories": {
                    "violence": random.choice([True, False]),
                    "harassment": random.choice([True, False]),
                    "sexual": random.choice([True, False]),
                    "self-harm": random.choice([True, False])
                },
                "category_scores": {
                    "violence": round(random.uniform(0.0, 1.0), 7),
                    "harassment": round(random.uniform(0.0, 1.0), 7),
                    "sexual": round(random.uniform(0.0, 1.0), 7),
                    "self-harm": round(random.uniform(0.0, 1.0), 7)
                }
            }
        ]
    }
    return fake_response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("mock:mock_app", host="127.0.0.1", port=8080, reload=True)

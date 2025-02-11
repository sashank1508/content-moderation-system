import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

import pytest
from unittest.mock import AsyncMock, patch
from tasks import moderate_text_task, moderate_image_task, retry_failed_moderation, push_to_dlq
from celery_worker import celery

# --- Test Celery Task: Text Moderation ---
def test_moderate_text_task()-> None:
    """Test Celery text moderation task."""
    result = moderate_text_task("test-id", "This is a test.")

    assert isinstance(result, dict)
    assert "id" in result
    assert "model" in result
    assert "results" in result


# --- Test Celery Task: Image Moderation ---
def test_moderate_image_task()-> None:
    """Test Celery image moderation task."""
    result = moderate_image_task("image-id", "https://example.com/image.jpg")

    assert isinstance(result, dict)
    assert "id" in result
    assert "model" in result
    assert "results" in result


# --- Test Celery Task: Retry Failed Moderation ---
def test_retry_failed_moderation()-> None:
    """Test Celery retry task for failed moderation tasks."""
    with patch("tasks._async_retry_failed_moderation", new_callable=AsyncMock) as mock_retry:
        retry_failed_moderation()
        mock_retry.assert_called_once()


# --- Test: Push Failed Task to DLQ ---
@pytest.mark.asyncio
async def test_push_to_dlq()-> None:
    """Test pushing a failed task to Dead Letter Queue (DLQ)."""
    with patch("tasks.get_redis", new_callable=AsyncMock) as mock_redis:
        mock_redis.return_value.rpush = AsyncMock()
        await push_to_dlq("test-id", "This is a failed text", "Some error message")
        
        mock_redis.return_value.rpush.assert_called_once()

# Test retry_failed_moderation when no failed tasks exist
@pytest.mark.asyncio
async def test_retry_failed_moderation_empty()-> None:
    """Ensure retry failed moderation handles empty DLQ properly."""
    with patch("tasks.get_redis", new_callable=AsyncMock) as mock_redis:
        mock_redis_instance = mock_redis.return_value
        mock_redis_instance.lpop = AsyncMock(return_value=None)
        retry_failed_moderation.apply(args=())
        mock_redis_instance.lpop.assert_called_once()


# Test if push_to_dlq handles errors properly
@pytest.mark.asyncio
async def test_push_to_dlq_handles_redis_error()-> None:
    """Ensure push_to_dlq handles Redis errors gracefully."""
    with patch("tasks.get_redis", new_callable=AsyncMock) as mock_redis:
        mock_redis.return_value.rpush.side_effect = Exception("Redis is down!")
        await push_to_dlq("fail-id", "This should fail", "Redis error")

def test_moderate_text_task_invalid_input()-> None:
    """Test Celery text moderation task with invalid input."""
    result = moderate_text_task("test-id", "")  # Empty text
    
    assert isinstance(result, dict)
    assert "id" in result
    assert "model" in result
    assert "results" in result

def test_moderate_image_task_invalid_url()-> None:
    """Test Celery image moderation task with an invalid URL."""
    result = moderate_image_task("image-id", "not-a-url")
    
    assert isinstance(result, dict)  # Should return a dictionary
    assert "id" in result
    assert "model" in result
    assert "results" in result

@pytest.mark.asyncio
async def test_push_to_dlq_handles_none()-> None:
    """Ensure push_to_dlq handles None values properly."""
    with patch("tasks.get_redis", new_callable=AsyncMock) as mock_redis:
        mock_redis.return_value.rpush = AsyncMock()
        await push_to_dlq(None, None, None)  # Passing None values
        
        mock_redis.return_value.rpush.assert_called_once()

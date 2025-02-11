import pytest
import redis.asyncio as redis

@pytest.fixture
async def mock_redis():
    """Mock Redis connection."""
    class FakeRedis:
        async def set(self, *args, **kwargs): return True
        async def get(self, *args, **kwargs): return None
        async def delete(self, *args, **kwargs): return True

    return FakeRedis()

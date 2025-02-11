from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/moderation_db")
Base = declarative_base()

def get_engine():
    return create_async_engine(DATABASE_URL, future=True, echo=True)

def get_sessionmaker():
    engine = get_engine()
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    SessionLocal = get_sessionmaker()
    async with SessionLocal() as session:
        yield session

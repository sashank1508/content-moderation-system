# from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker
# import os
# from dotenv import load_dotenv

# # Load environment variables
# load_dotenv()

# # PostgreSQL connection URL
# DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/moderation_db")

# # Create Async Engine for PostgreSQL
# engine = create_async_engine(DATABASE_URL, future=True, echo=True)

# # Create session factory
# AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# # # Session Factory
# # async_session = sessionmaker(
# #     bind=engine, class_=AsyncSession, expire_on_commit=False
# # )

# # Base ORM Model
# Base = declarative_base()

# async def get_db():
#     async with AsyncSessionLocal() as session:
#         yield session

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/moderation_db")
Base = declarative_base()

def get_engine():
    return create_async_engine(DATABASE_URL, future=True, echo=True)

# def get_engine():
#     return create_async_engine(DATABASE_URL, future=True, echo=True, 
#                                pool_size=20, max_overflow=10, 
#                                pool_recycle=1800, pool_timeout=30)

def get_sessionmaker():
    engine = get_engine()
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    SessionLocal = get_sessionmaker()
    async with SessionLocal() as session:
        yield session

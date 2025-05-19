import uuid
import os
from typing import List

from sqlalchemy import Column, String, Float, Boolean, Text, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from geoalchemy2 import Geography, WKTElement
from geoalchemy2.functions import ST_DWithin, ST_Distance
from dotenv import load_dotenv

from app.db.models import Service  # your Pydantic model or dataclass for input


load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")

if not all([DB_USER, DB_PASS, DB_NAME]):
    raise ValueError("Missing required DB credentials in .env")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


Base = declarative_base()

class ServiceDB(Base):
    __tablename__ = "services"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String)
    type = Column(String)
    location = Column(String)
    address = Column(Text)
    mobile_no = Column(String)
    timings = Column(String)
    cost = Column(String)
    available = Column(Boolean)
    contact = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    geom = Column(Geography(geometry_type='POINT', srid=4326))


# Initialize DB engine and session
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def insert_services(services: List[Service]):
    async with AsyncSessionLocal() as session:
        db_services = [
            ServiceDB(
                name=s.name,
                type=s.type,
                location=s.location,
                address=s.address,
                mobile_no=s.mobile_no,
                timings=s.timings,
                cost=s.cost,
                available=s.available,
                contact=s.contact,
                latitude=s.latitude,
                longitude=s.longitude,
                geom=WKTElement(f'POINT({s.longitude} {s.latitude})', srid=4326)
            )
            for s in services
        ]
        session.add_all(db_services)
        await session.commit()


async def search_nearby(lat: float, lon: float, top_k: int = 100, radius_km: int = 20):
    async with AsyncSessionLocal() as session:
        point = WKTElement(f'POINT({lon} {lat})', srid=4326)

        stmt = (
            select(ServiceDB)
            .where(ST_DWithin(ServiceDB.geom, point, radius_km * 1000))  # radius in meters
            .order_by(ST_Distance(ServiceDB.geom, point))
            .limit(top_k)
        )

        results = (await session.execute(stmt)).scalars().all()

        services = [
            {
                "name": r.name,
                "type": r.type,
                "location": r.location,
                "address": r.address,
                "mobile_no": r.mobile_no,
                "timings": r.timings,
                "cost": r.cost,
                "available": r.available,
                "contact": r.contact,
                "latitude": r.latitude,
                "longitude": r.longitude,
            }
            for r in results
        ]

        return services


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

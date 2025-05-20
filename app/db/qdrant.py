from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from app.db.models import Service
from typing import List
import uuid
import os

client = QdrantClient(host=os.getenv("QDRANT_HOST", "localhost"), port=int(os.getenv("QDRANT_PORT", 6333)))
COLLECTION_NAME = "services"

model = SentenceTransformer("all-MiniLM-L6-v2")  

async def init_qdrant():
    try:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
    except Exception as e:
        if "already exists" not in str(e).lower():
            raise e

async def insert_services(services: List[Service]):
    points = []
    for s in services:
        text = f"{s.name} {s.type} {s.location or ''} {s.address or ''}"
        vector = model.encode(text)

        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "name": s.name,
                "type": s.type,
                "location": s.location,
                "address": s.address,
                "mobile_no": s.mobile_no,
                "timings": s.timings,
                "cost": s.cost,
                "available": s.available,
                "contact": s.contact,
                "latitude": s.latitude,
                "longitude": s.longitude
            }
        )
        points.append(point)

    client.upsert(collection_name=COLLECTION_NAME, points=points)

async def search_nearby(lat: float, lon: float, top_k: int = 100, radius_km: int = 20):
    from geopy.distance import geodesic

    print(f"[Qdrant Search] Looking for services near ({lat}, {lon}) within {radius_km} km")

    results, _ = client.scroll(collection_name=COLLECTION_NAME, limit=1000)

    filtered = []
    for r in results:
        data = r.payload
        lat2 = data.get("latitude")
        lon2 = data.get("longitude")

        if lat2 is not None and lon2 is not None:
            dist_km = geodesic((lat, lon), (lat2, lon2)).km

            if dist_km <= radius_km:
                data["distance_km"] = round(dist_km, 2)
                filtered.append(data)

    print(f"[Qdrant Search] Found {len(filtered)} services within {radius_km} km")
    return sorted(filtered, key=lambda x: x["distance_km"])

async def get_all_service_types():
    results = client.scroll(collection_name=COLLECTION_NAME, limit=1000)[0]
    return sorted(set(r.payload.get("type", "") for r in results if "type" in r.payload))

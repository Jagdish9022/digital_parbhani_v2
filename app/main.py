from fastapi import FastAPI, UploadFile, File, Query, Request, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.db.qdrant import insert_services, search_nearby, init_qdrant, get_all_service_types
from app.utils.common import parse_csv, extract_location_and_service
from app.db.models import Service, UserQuery
import requests
from geopy.distance import geodesic

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    await init_qdrant()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload_services/")
async def upload(file: UploadFile = File(...)):
    services = parse_csv(file)
    await insert_services(services)
    return {"message": f"{len(services)} services uploaded successfully."}

@app.post("/get_help/")
async def get_help(user_query: UserQuery = Body(...)):
    query = user_query.query
    user_lat = user_query.latitude
    user_lon = user_query.longitude

    if not query:
        raise HTTPException(status_code=400, detail="Query text is required")

    if user_lat is None or user_lon is None:
        raise HTTPException(status_code=400, detail="Location coordinates are required")

    analysis = {
        'service_type': user_query.service_type or 'unknown',
        'location_mentioned': user_query.location_mentioned,
        'urgency': user_query.urgency or 'Medium'
    }

    print(analysis)
    service_type = analysis.get("service_type", "unknown")
    mentioned_location = analysis.get("location_mentioned")
    urgency = analysis.get("urgency", "Medium")

    target_lat, target_lon = user_lat, user_lon
    location_name = "your current location"

    if mentioned_location:
        try:
            geo_resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": mentioned_location, "format": "json", "limit": 1},
                headers={"User-Agent": "EmergencyLocator/1.0"}
            )
            geo_data = geo_resp.json()

            if geo_data:
                target_lat = float(geo_data[0]['lat'])
                target_lon = float(geo_data[0]['lon'])
                location_name = geo_data[0].get('display_name', mentioned_location)
        except Exception as e:
            print(f"Geocoding error: {e}")

    results = await search_nearby(target_lat, target_lon, top_k=100)

    if service_type and service_type != "unknown":
        service_keywords = {
            "hospital": ["hospital", "medical", "healthcare", "clinic", "emergency"],
            "doctor": ["doctor", "physician", "medical", "clinic", "healthcare"],
            "ambulance": ["ambulance", "emergency", "medical transport"],
            "automobile": ["automobile", "car", "mechanic", "garage", "vehicle", "repair", "auto"],
            "pharmacy": ["pharmacy", "medicine", "medical", "chemist", "drug store"],
            "food": ["food", "restaurant", "cafe", "catering", "meal", "hotel"],
            "police": ["police", "security", "law enforcement", "thief"],
            "fire": ["fire", "firefighter", "emergency", "fire extinguisher"],
        }

        matching_keywords = []
        for category, keywords in service_keywords.items():
            if any(keyword.lower() in service_type.lower() for keyword in [category] + keywords):
                matching_keywords.extend(keywords)
                matching_keywords.append(category)

        if matching_keywords:
            type_filtered = [
                r for r in results
                if any(keyword.lower() in r.get('type', '').lower() for keyword in matching_keywords)
            ]
        else:
            type_filtered = [
                r for r in results
                if service_type.lower() in r.get('type', '').lower()
            ]

        if not type_filtered and service_type != "unknown":
            type_filtered = [
                r for r in results
                if service_type.lower() in r.get('type', '').lower()
            ]
    else:
        type_filtered = results

    radius_km = 20  # Default
    if urgency == "High":
        radius_km = 50
    elif urgency == "Low":
        radius_km = 30


    filtered_by_radius = [
        r for r in type_filtered
        if geodesic((target_lat, target_lon), (r['latitude'], r['longitude'])).km <= radius_km
    ]

    filtered = filtered_by_radius

    if len(filtered) == 0:
        return {
            "original_query": query,
            "understood_service": service_type,
            "target_location": location_name,
            "target_coordinates": [target_lat, target_lon],
            "user_coordinates": [user_lat, user_lon],
            "urgency": urgency,
            "radius_km": radius_km,
            "nearby_services": [],
            "message": f"No {service_type} services found within {radius_km}km of the target location. Try increasing the search radius or selecting a different service type."
        }

    for result in filtered:
        result['distance_km'] = round(
            geodesic((target_lat, target_lon), (result['latitude'], result['longitude']))
            .km, 2
        )

    filtered.sort(key=lambda x: x['distance_km'])

    return {
        "original_query": query,
        "understood_service": service_type,
        "target_location": location_name,
        "target_coordinates": [target_lat, target_lon],
        "user_coordinates": [user_lat, user_lon],
        "urgency": urgency,
        "radius_km": radius_km,
        "nearby_services": filtered
    }

@app.get('/get_services')
async def get_all_service():
    return await get_all_service_types()

@app.get("/get_all_services")
async def get_all_services():
    from app.db.qdrant import client, COLLECTION_NAME
    results, _ = client.scroll(collection_name=COLLECTION_NAME, limit=1000)
    return [r.payload for r in results]

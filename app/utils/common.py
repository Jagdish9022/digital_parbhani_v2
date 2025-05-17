import pandas as pd
from app.db.models import Service
from fastapi import UploadFile

def parse_csv(file: UploadFile) -> list[Service]:
    df = pd.read_csv(file.file)

    expected_columns = {
        "name", "type", "location", "address", "mobile_no",
        "timings", "cost", "available", "latitude", "longitude", "contact"
    }

    if not expected_columns.issubset(df.columns):
        raise ValueError(f"Missing columns. Expected: {expected_columns}")

    services = []
    for _, row in df.iterrows():
        service = Service(
            name=row["name"],
            type=row["type"],
            location=row["location"],
            address=row["address"],
            mobile_no=str(row["mobile_no"]),
            timings=row["timings"],
            cost=str(row["cost"]),
            available=bool(row["available"]),
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            contact=str(row["contact"])
        )
        services.append(service)

    return services


def extract_location_and_service(text: str):
    known_services = ["ambulance", "doctor", "hospital", "medical", "clinic", "nurse"]
    words = text.lower().split()

    found_service = None
    for service in known_services:
        if service in words:
            found_service = service
            break

    if found_service:
        words = [w for w in words if w != found_service]

    possible_location = " ".join(words).replace("need", "").replace("help", "").strip()

    return possible_location, found_service
    
from pydantic import BaseModel
from typing import Optional

class Service(BaseModel):
    name: str
    type: str
    latitude: float
    longitude: float
    location: Optional[str] = None
    address: Optional[str] = None
    mobile_no: Optional[str] = None
    timings: Optional[str] = None
    cost: Optional[str] = None
    available: Optional[bool] = True
    contact: Optional[str] = None

class UserQuery(BaseModel):
    query: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    service_type: Optional[str] = None
    location_mentioned: Optional[str] = None
    urgency: Optional[str] = "Medium"

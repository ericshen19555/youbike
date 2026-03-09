from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import time

class StationInfo(BaseModel):
    sno: str = Field(..., description="Station ID")
    sna: str = Field(..., description="Station Name (TW)")
    tot: int = Field(0, description="Total spaces")
    sbi: int = Field(0, description="Available bikes")
    sbi_20: int = Field(0, description="YouBike 2.0 bikes")
    sbi_20e: int = Field(0, description="YouBike 2.0 electric bikes")
    lat: float = 0.0
    lng: float = 0.0
    ar: Optional[str] = Field(None, description="Station Address")
    sarea: Optional[str] = Field(None, description="District")
    sareaen: Optional[str] = Field(None, description="District (EN)")
    bemp: int = Field(0, description="Available spaces")

    updatetime: str = Field("", description="Update time")
    act: str = Field("1", description="Status (1: active)")
    isRealtime: bool = False



class UserSubscription(BaseModel):
    id: Optional[int] = None
    user_id: str
    station_id: str
    rrule: str # RFC 5545 string
    threshold: int = 3
    bike_type: str = "any" # "any", "normal", "electric"
    is_active: bool = True

class ActiveTask(BaseModel):
    id: Optional[int] = None
    sub_id: int # Link to UserSubscription
    next_run: str # ISO format datetime
    current_interval: int = 60 # Seconds (15, 30, 60)
    status: str = "pending" # "pending", "running", "completed"


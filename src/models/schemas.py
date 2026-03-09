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
    bemp: int = Field(0, description="Available spaces")
    updatetime: str = Field("", description="Update time")
    act: str = Field("1", description="Status (1: active)")
    isRealtime: bool = False



class UserTrigger(BaseModel):
    user_id: str
    station_id: str
    threshold: int = 3
    start_time: str  # Format: "HH:MM"
    end_time: str    # Format: "HH:MM"
    days_of_week: str = "1,2,3,4,5"  # Format: "1,2,3,4,5" (1=Mon, 7=Sun)
    bike_type: str = "any" # "any", "normal", "electric"
    is_active: bool = True

import httpx
import time
from typing import List, Dict, Optional
from src.models.schemas import StationInfo

class YouBikeClient:
    LIST_URL = "https://apis.youbike.com.tw/json/station-min-yb2.json"
    PARKING_URL = "https://apis.youbike.com.tw/tw2/parkingInfo"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    async def fetch_station_list(self) -> List[StationInfo]:
        """Fetch basic station metadata."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.LIST_URL}?_t={int(time.time()*1000)}")
            response.raise_for_status()
            data = response.json()
            
            stations = []
            for item in data:
                if not item.get("station_no"):
                    continue
                stations.append(StationInfo(
                    sno=item.get("station_no"),
                    sna=item.get("name_tw"),
                    tot=int(item.get("parking_spaces") or item.get("total_spaces") or 0),
                    lat=float(item.get("lat") or 0),
                    lng=float(item.get("lng") or 0),
                    ar=item.get("address_tw"),
                    sarea=item.get("district_tw"),
                    updatetime=item.get("updated_at") or "",
                    act=item.get("act") or "1"
                ))
            return stations

    async def fetch_parking_info(self, station_ids: List[str]) -> Dict[str, dict]:
        """Fetch real-time availability for given station IDs (max 20 per batch recommended in JS)."""
        if not station_ids:
            return {}
            
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.PARKING_URL,
                    json={"station_no": station_ids},
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                result = response.json()
                
                parking_data = {}
                # retCode 1 means success
                if result.get("retCode") == 1 and result.get("retVal"):
                    data_list = result["retVal"]
                    if isinstance(data_list, dict) and "data" in data_list:
                        data_list = data_list["data"]
                    
                    if not isinstance(data_list, list):
                        data_list = [data_list] # Sometimes it might be a single object

                    for b in data_list:
                        sno = b.get("station_no")
                        if not sno: continue
                        
                        detail = b.get("available_spaces_detail") or {}
                        d = int(detail.get("yb2") or 0)
                        e = int(detail.get("eyb") or 0)
                        
                        parking_data[sno] = {
                            "tot": int(b.get("parking_spaces") or b.get("total_spaces") or 0),
                            "sbi": d + e,
                            "sbi_20": d,
                            "sbi_20e": e,
                            "bemp": int(b.get("empty_spaces") or 0),
                            "updatetime": b.get("updated_at") or "",
                            "isRealtime": True
                        }
                return parking_data
            except Exception as e:
                import logging
                logging.warning(f"Failed to fetch parking info: {e}")
                return {}
        return {}



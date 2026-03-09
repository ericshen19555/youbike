import httpx
import time
from typing import List, Dict, Optional
from src.models.schemas import StationInfo
from src.config.constants import YB2_STATION_LIST_URL, YB2_PARKING_INFO_URL

class YouBikeClient:

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.station_list_url = YB2_STATION_LIST_URL
        self.parking_info_url = YB2_PARKING_INFO_URL

    async def fetch_station_list(self) -> List[StationInfo]:
        """Fetch basic station metadata."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.station_list_url}?_t={int(time.time()*1000)}")
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
                    self.parking_info_url,
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



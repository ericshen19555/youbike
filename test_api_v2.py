import asyncio
import sys
import os
from datetime import time as dt_time

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from api.client import YouBikeClient

async def test_api_integration():
    client = YouBikeClient()
    
    print("Step 1: Fetching Station List...")
    stations = await client.fetch_station_list()
    if not stations:
        print("Failed to fetch station list.")
        return
        
    print(f"Successfully fetched {len(stations)} stations.")
    
    # Pick top 5 stations for real-time testing
    target_ids = [s.sno for s in stations[:5]]
    print(f"Step 2: Fetching Real-time Info for: {target_ids}")
    
    realtime_data = await client.fetch_parking_info(target_ids)
    
    if not realtime_data:
        print("Failed to fetch real-time info.")
        return
        
    print(f"Successfully fetched real-time info for {len(realtime_data)} stations.")
    for sno, data in realtime_data.items():
        print(f"Station {sno}:")
        print(f"  Available Bikes (Total): {data['sbi']}")
        print(f"  - YouBike 2.0: {data['sbi_20']}")
        print(f"  - Electric: {data['sbi_20e']}")
        print(f"  Empty Spaces: {data['bemp']}")
        print(f"  Update Time: {data['updatetime']}")

if __name__ == "__main__":
    asyncio.run(test_api_integration())

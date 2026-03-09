import httpx
import json

async def check_realtime_api():
    # Taipei YouBike 2.0 Realtime API
    url = "https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json"
    print(f"Checking URL: {url}")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            data = response.json()
            if data and len(data) > 0:
                print(f"Number of stations: {len(data)}")
                print(f"Keys in first item: {list(data[0].keys())}")
                sample = data[0]
                # Check for sbi, bemp
                print(f"sbi: {sample.get('sbi')}")
                print(f"bemp: {sample.get('bemp')}")
                print(f"Sample data: {sample}")
            else:
                print("No data found")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_realtime_api())

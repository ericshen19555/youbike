import httpx
import json

async def inspect_realtime():
    url = "https://apis.youbike.com.tw/json/station-min-yb2.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()
        if data:
            print("--- First Station Sample ---")
            print(json.dumps(data[0], indent=2, ensure_ascii=False))
            print("--- Fields Mapping ---")
            print(f"sno: {data[0].get('sno')}")
            print(f"sna: {data[0].get('sna')}")
            print(f"bikes: {data[0].get('available_rent_bikes')}")
            print(f"spaces: {data[0].get('available_return_bikes')}")
            print(f"time: {data[0].get('mday')}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(inspect_realtime())

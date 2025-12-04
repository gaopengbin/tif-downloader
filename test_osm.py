import asyncio
import aiohttp

async def test():
    url = 'https://overpass-api.de/api/interpreter'
    query = '[out:json];(way["building"](32.95,118.49,33.02,118.59););out body;>;out skel qt;'
    
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            print(f"Querying: {url}")
            async with session.post(url, data={'data': query}) as response:
                print(f'Status: {response.status}')
                if response.status == 200:
                    data = await response.json()
                    print(f'Elements: {len(data.get("elements", []))}')
                else:
                    text = await response.text()
                    print(f'Error response: {text[:500]}')
    except Exception as e:
        print(f'Error: {type(e).__name__}: {e}')

asyncio.run(test())

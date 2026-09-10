import asyncio

import httpx
from app.models import MonitoredSite
from app.services.checker import check_many

sites = [
    MonitoredSite(id=1, name="Google", url="https://google.com"),
    MonitoredSite(id=2, name="GitHub", url="https://github.com"),
    MonitoredSite(id=3, name="404", url="https://github.com/esto-no-existe-xyz"),
    MonitoredSite(id=4, name="DNS roto", url="https://dominio-que-no-existe-abc123.com"),
    MonitoredSite(id=5, name="Lento", url="https://httpbin.org/delay/20"),
]


async def main():
    async with httpx.AsyncClient() as client:
        results = await check_many(client, sites)
    for r in results:
        print(r)


asyncio.run(main())
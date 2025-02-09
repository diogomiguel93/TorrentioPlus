from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os

app = FastAPI()

# Config CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TORRENTIO_ADDON_URL = os.getenv('TORRENTIO_ADDON_URL')

@app.get('/manifest.json')
async def get_manifest():
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{TORRENTIO_ADDON_URL}/manifest.json")
        manifest = response.json()

    manifest['name'] = 'Torrentio+ RD'
    return manifest


@app.get('/stream/{type}/{id}.json')
async def get_stream(type: str, id: str):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{TORRENTIO_ADDON_URL}/stream/{type}/{id}.json")
        full_streams = response.json()

        # Filter streams
        streams = []
        for stream in full_streams.get('streams', {}):
            if 'ilCorSaRoNeRo' in stream['title'] or '🇮🇹' in stream['title']:
                if 'download' in stream['name']:
                    if await is_cached(stream):
                        stream['name'] = stream['name'].replace('RD download', 'RD+ (checked)')
                        streams.append(stream)
                else:
                    streams.append(stream)

    full_streams['streams'] = streams
    return full_streams


async def is_cached(stream: dict) -> bool:
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
        response = await client.head(stream['url'])
        print(response.headers)
        if response.headers['Server'] == 'Lity 2.0':
            return True
        else:
            return False




if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=9000)
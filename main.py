from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import httpx
import base64
import asyncio
import rd

app = FastAPI()
templates = Jinja2Templates(directory="templates")
#app.mount("/static", StaticFiles(directory="static"), name="static")

# Config CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config page
@app.get('/', response_class=HTMLResponse)
@app.get('/configure', response_class=HTMLResponse)
async def configure(request: Request):
    response = templates.TemplateResponse("configure.html", {"request": request})
    return response


# Manifest endpoint
@app.get('/{addon_url}/manifest.json')
async def get_manifest(addon_url: str):
    addon_url = decode_base64_url(addon_url)
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{addon_url}/manifest.json")
        manifest = response.json()

    manifest['name'] = 'Torrentio+ RD'
    return manifest


# Stream filter
@app.get('/{addon_url}/stream/{type}/{id}.json')
async def get_stream(addon_url: str, type: str, id: str):
    addon_url = decode_base64_url(addon_url)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{addon_url}/stream/{type}/{id}.json")
        full_streams = response.json()

        # Filter streams
        filtered_streams = []
        cache_check_list = []
        for stream in full_streams.get('streams', {}):
            if 'ilCorSaRoNeRo' in stream.get('description', stream.get('title')) or '🇮🇹' in stream.get('description', stream.get('title')):
                if '⏳' in stream['name'] or 'download' in stream['name']:
                    cache_check_list.append(stream)
                else:
                    filtered_streams.append(stream)

        # Run delayed cache checking
        tasks = [is_cached(stream, (i+1) * rd.REQUEST_DELAY) for i, stream in enumerate(cache_check_list)]
        cached_results = [r for r in await asyncio.gather(*tasks) if r]
        streams = filtered_streams + cached_results

    if len(streams) > 0:
        full_streams['streams'] = streams
    return full_streams


# Filter cached torrents
async def filter_cached_torrent(stream: dict) -> list:
    if '⏳' in stream['name'] or 'download' in stream['name']:
        file_id, hash = get_hash_from_url(stream['url'])
        if await is_cached(hash, file_id):
            stream['name'] = stream['name'].replace('⏳', '⚡⏳')
            stream['name'] = stream['name'].replace('RD download', 'RD++')
            return stream
    else:
        return stream


# Debrid checker
async def is_cached(stream, delay) -> bool:
    file_id, hash = get_hash_from_url(stream['url'])
    async with httpx.AsyncClient(timeout=30) as client:
        if await rd.instant_availability(client, hash, file_id, delay):
            stream['name'] = stream['name'].replace('⏳', '⚡⏳')
            stream['name'] = stream['name'].replace('RD download', 'RD++')
            return stream
        else:
            return {}
    """
        response = await client.head(stream['url'])
        print(response.headers)
        if 'real-debrid' in response.headers['location']:
            return True
        else:
            return False
    """

# Torrent get hash
def get_hash_from_url(url: str) -> tuple:
    # Torrentio
    url_parts = url.split('/')
    if 'torrentio' in url:
        return 'all', url_parts[5]
    # Mediafusion
    elif 'mediafusion' in url:
        return 'all', url_parts[-1]


# Url decoder
def decode_base64_url(encoded_url):
    padding = '=' * (-len(encoded_url) % 4)
    encoded_url += padding
    decoded_bytes = base64.b64decode(encoded_url)
    return decoded_bytes.decode('utf-8')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=9000)
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from urllib.parse import unquote
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
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(f"{addon_url}/stream/{type}/{id}.json")
        full_streams = response.json()
        print(len(full_streams))
        # Filter streams
        streams = []
        check_list = []
        for stream in full_streams.get('streams', {}):
            if 'ilCorSaRoNeRo' in stream.get('description', stream.get('title')) or '🇮🇹' in stream.get('description', stream.get('title')):
                if '⏳' in stream['name'] or 'download' in stream['name']:
                    check_list.append(stream)
                    if await is_cached(stream):
                        stream['name'] = stream['name'].replace('⏳', '⚡⏳').replace('RD download', 'RD++ 🇮🇹')
                        streams.append(stream)
                else:
                    stream['name'] = stream['name'].replace('RD+', 'RD+ 🇮🇹')
                    streams.append(stream)

        if streams:
            full_streams['streams'] = streams

        if check_list:
            rd_key = get_realdebrid_key_from_url(addon_url)
            asyncio.create_task(delete_downloads(check_list, rd_key))
            asyncio.create_task(delete_torrents(check_list, rd_key))

    return full_streams


# Debrid checker
async def is_cached(stream: dict) -> bool:
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        response = await client.head(stream['url'])
        print(response.headers)
        if 'real-debrid' in response.headers['location']:
            return True
        else:
            return False
        
# Debrid delete torrents
async def delete_torrents(delete_list: list, rd_key: str):
    async with httpx.AsyncClient(timeout=120, headers={'Authorization': f"Bearer {rd_key}"}) as client:
        for stream in delete_list:
            hash = get_hash_from_url(stream['url'])
            torrents = await rd.get_torrents(client, 0)
            for torrent in torrents:
                if torrent['hash'] == hash:
                    await rd.delete_torrent(client, torrent['id'], 0)

async def delete_downloads(delete_list: list, rd_key: str):
    async with httpx.AsyncClient(timeout=120, headers={'Authorization': f"Bearer {rd_key}"}) as client:
        for stream in delete_list:
            if 'torrentio' in stream['url']:
                filename = get_filename_from_url(stream['url'])
            else:
                filename = stream['behaviorHints']['filename']
            downlods = await rd.get_downloads(client, 0)
            for download in downlods:
                if download['filename'] == filename:
                    await rd.delete_download(client, download['id'], 0)
        

# Torrent get hash
def get_hash_from_url(url: str) -> str:
    # Torrentio
    url_parts = url.split('/')
    if 'torrentio' in url:
        return url_parts[5]
    # Mediafusion
    elif 'mediafusion' in url:
        return url_parts[-1]
    
def get_filename_from_url(url: str) -> str:
    # Torrentio
    url_parts = url.split('/')
    if 'torrentio' in url:
        print(unquote(url_parts[-1]))
        return unquote(url_parts[-1])

def get_realdebrid_key_from_url(url: str) -> str:
    # Torrentio
    url_parts = url.split('realdebrid=')
    if 'torrentio' in url:
        return url_parts[-1]

# Url decoder
def decode_base64_url(encoded_url):
    padding = '=' * (-len(encoded_url) % 4)
    encoded_url += padding
    decoded_bytes = base64.b64decode(encoded_url)
    return decoded_bytes.decode('utf-8')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=9000)
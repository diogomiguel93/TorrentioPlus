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
import re

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


resolution_relevance = [
    '2160p',
    '4k',
    '1440p',
    '2k',
    '1080p',
    '720p',
    '480p'
]

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
@app.get('/{user_settings}/{addon_url}/manifest.json')
async def get_manifest(user_settings:str, addon_url: str):
    addon_url = decode_base64_url(addon_url)
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{addon_url}/manifest.json")
        manifest = response.json()

    if 'realdebrid' in addon_url:
        manifest['name'] = 'Torrentio 🇮🇹 - RD'
    else:
        manifest['name'] = 'Torrentio 🇮🇹'
    return manifest


# Stream filter
@app.get('/{user_settings}/{addon_url}/stream/{type}/{id}.json')
async def get_stream(user_settings: str, addon_url: str, type: str, id: str):
    addon_url = decode_base64_url(addon_url)
    user_settings = parse_user_settings(user_settings)
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(f"{addon_url}/stream/{type}/{id}.json")
        full_streams = response.json()
        
        # Filter streams
        streams = []
        check_list = []
        for stream in full_streams.get('streams', {}):
            if 'ilCorSaRoNeRo' in stream['title'] or '🇮🇹' in stream['title']:
                if 'download' in stream['name']:
                    check_list.append(stream)
                    if await is_cached(stream):
                        stream['name'] = stream['name'].replace('RD download', 'RD+')
                        stream['name'], stream['title'], stream['video_size'], stream['resolution'], stream['peers'] = format_stream(stream)
                        streams.append(stream)
                else:
                    stream['name'], stream['title'], stream['video_size'], stream['resolution'], stream['peers'] = format_stream(stream)
                    streams.append(stream)


        if len(streams) > 0:
            sort_type = get_sort_type_from_url(addon_url)
            # Sort quality then size
            if sort_type == 'qualitysize':
                streams.sort(
                    key=lambda x: (
                        next((i for i, res in enumerate(resolution_relevance) if res.lower() in x['resolution'].lower()), float('inf')),
                        -x['video_size']
                    )
                )

            # Sort quality the seeders
            elif sort_type == 'qualityseeders':
                streams.sort(
                    key=lambda x: (
                        next((i for i, res in enumerate(resolution_relevance) if res.lower() in x['resolution'].lower()), float('inf')),
                        -x['peers']
                    )
                )

            # Sort by size
            elif sort_type == 'size':
                streams.sort(key=lambda x: x['video_size'], reverse=True)

            # Sort by seeders (default)
            elif sort_type == 'seeders':
                streams.sort(key=lambda x: x['peers'], reverse=True)

        elif user_settings['original_results']:
            for stream in full_streams.get('streams', {}):
                stream['name'] = stream['name'].replace('RD download', 'RD⏳')
                stream['name'], stream['title'], stream['video_size'], stream['resolution'], stream['peers'] = format_stream(stream)
                streams.append(stream)

        full_streams['streams'] = streams

        if check_list:
            rd_key = get_realdebrid_key_from_url(addon_url)
            asyncio.create_task(delete_downloads(check_list, rd_key))
            asyncio.create_task(delete_torrents(check_list, rd_key))

    return full_streams


# Extract Stream infomations
def extract_stream_infos(stream: dict) -> tuple:

    # Name
    try:
        name_parts = stream['name'].split('\n')
        name = name_parts[0]
        resolution = name_parts[1]
    except:
        resolution = 'UNK'

    # Title (description)
    pattern = re.compile(r"""
        ^(.+?)\s*\n👤\s*            # Filename
        (\d+)\s+                    # Peers
        💾\s*([\d\.]+\s*[GM]B)\s+   # Size
        ⚙️\s*(.+?)\s*               # Source
        (?:\n(.*))?$                # Language
    """, re.VERBOSE | re.MULTILINE)
    match = pattern.search(stream['title'])

    if match:
        filename = match.group(1).strip()
        peers = int(match.group(2))
        size = match.group(3)
        source = match.group(4).strip()
        languages = match.group(5).strip() if match.group(5) else "Unknown"    
        return name, resolution, filename, peers, size, source, languages


# Rename stream
def format_stream(stream: dict) -> tuple:

    name, resolution, filename, peers, size, source, languages = extract_stream_infos(stream)

    if 'GB' in size:
        raw_size = gb_to_bytes(float(size.replace(' GB', '')))
    elif 'MB' in size:
        raw_size = mb_to_bytes(float(size.replace(' MB', '')))
    
    if 'RD+' in name:
        name = f"[RD⚡] Torrentio {resolution}"
        title = f"📄 {filename}\n📦 {size}\n🔍 {source}\n🔊 {languages}"
    elif 'RD⏳' in name:
        name = f"[RD⏳] Torrentio {resolution}"
        title = f"📄 {filename}\n📦 {size} 👤 {peers}\n🔍 {source}\n🔊 {languages}"
    else:
        name = f"Torrentio {resolution}"
        title = f"📄 {filename}\n📦 {size} 👤 {peers}\n🔍 {source}\n🔊 {languages}"

    return name, title, raw_size, resolution, peers


# Debrid checker
async def is_cached(stream: dict) -> bool:
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
        response = await client.head(stream['url'])
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

# Debrid delete downloads
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
        

# Addon URL parts extration
def get_hash_from_url(url: str) -> str:
    url_parts = url.split('/')
    if 'torrentio' in url:
        return url_parts[5]

def get_filename_from_url(url: str) -> str:
    url_parts = url.split('/')
    if 'torrentio' in url:
        return unquote(url_parts[-1])

def get_realdebrid_key_from_url(url: str) -> str:
    url_parts = url.split('realdebrid=')
    if 'torrentio' in url:
        return url_parts[-1]
    
def get_sort_type_from_url(url: str) -> str:
    match = re.search(r'sort=([^|%]+)', url)
    if match:
        return match.group(1)
    else:
        return 'qualityseeders'


# Url decoder
def decode_base64_url(encoded_url):
    padding = '=' * (-len(encoded_url) % 4)
    encoded_url += padding
    decoded_bytes = base64.b64decode(encoded_url)
    return decoded_bytes.decode('utf-8')


# Byte convetions
def gb_to_bytes(gb: float) -> int:
    return int(gb * 1024**3)

def mb_to_bytes(mb: float) -> int:
    return int(mb * 1024**2)


# User settings
def parse_user_settings(user_settings: str) -> dict:
    settings = user_settings.split('|')
    _user_settings = {
        'original_results': False
    }
    for setting in settings:
        if 'oResult' in setting:
            setting = setting.split('=')[1]
            if setting == 'true':
                _user_settings['original_results'] = True

    return _user_settings



if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=9000)
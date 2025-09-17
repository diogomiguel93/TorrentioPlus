from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from urllib.parse import unquote
import httpx
import base64
import asyncio
import rd
import re
import os

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

# Cloudflare Cache control & CORS
def json_response(data):
    response = JSONResponse(data)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = '*'
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Surrogate-Control"] = "no-store"
    return response

# Headers
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
}

# Config page
@app.get('/', response_class=HTMLResponse)
@app.get('/configure', response_class=HTMLResponse)
async def configure(request: Request):
    response = templates.TemplateResponse("configure.html", {"request": request})
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Surrogate-Control"] = "no-store"
    return response


@app.get('/link_generator', response_class=HTMLResponse)
async def configure(request: Request):
    response = templates.TemplateResponse("old_config.html", {"request": request})
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Surrogate-Control"] = "no-store"
    return response

# Manifest endpoint
@app.get('/{user_settings}/{addon_url}/manifest.json')
async def get_manifest(user_settings:str, addon_url: str):
    addon_url = decode_base64_url(addon_url)
    debrid_sign = parse_debrid_sign(addon_url)
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{addon_url}/manifest.json")
        manifest = response.json()

    if debrid_sign != '':
        manifest['name'] = f'Torrentio 🇮🇹 - {debrid_sign}'
    else:
        manifest['name'] = 'Torrentio 🇮🇹'
    return json_response(manifest)


# Stream filter
@app.get('/{user_settings}/{addon_url}/stream/{type}/{id}.json')
async def get_stream(user_settings: str, addon_url: str, type: str, id: str):
    addon_url = decode_base64_url(addon_url)
    user_settings = parse_user_settings(user_settings)
    debrid_sign = parse_debrid_sign(addon_url)
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(f"{addon_url}/stream/{type}/{id}.json")
        full_streams = response.json()
        # Filter streams
        streams = []
        check_list = []
        for stream in full_streams.get('streams', {}):
            if 'ilCorSaRoNeRo' in stream['title'] or '🇮🇹' in stream['title']:

                # Real debrid cache check
                if debrid_sign == 'RD' and 'download' in stream['name']:
                    check_list.append(stream)
                    if await is_cached(stream):
                        stream['name'] = stream['name'].replace('RD download', 'RD+')
                        stream['name'], stream['title'], stream['video_size'], stream['resolution'], stream['peers'] = format_stream(stream, debrid_sign)
                        streams.append(stream)
                else:
                    stream['name'], stream['title'], stream['video_size'], stream['resolution'], stream['peers'] = format_stream(stream, debrid_sign)
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
                #stream['name'] = stream['name'].replace(f'{debrid_sign} download', f'{debrid_sign}⏳')
                stream['name'], stream['title'], stream['video_size'], stream['resolution'], stream['peers'] = format_stream(stream, debrid_sign)
                streams.append(stream)

        full_streams['streams'] = streams

        if check_list:
            rd_key = get_realdebrid_key_from_url(addon_url)
            asyncio.create_task(delete_downloads(check_list, rd_key))
            asyncio.create_task(delete_torrents(check_list, rd_key))

    return json_response(full_streams)


# Parse debrid url to debrid sign
def parse_debrid_sign(addon_url):
    if 'realdebrid' in addon_url:
        return 'RD'
    elif 'premiumize' in addon_url:   
        return 'PM'
    elif 'alldebrid' in addon_url:
        return 'AD'
    elif 'debridlink' in addon_url:   
        return 'DL'
    elif 'easydebrid' in addon_url:   
        return 'ED'
    elif 'offcloud' in addon_url:   
        return 'OC'
    elif 'torbox' in addon_url:
        return 'TB'
    elif 'putio' in addon_url:
        return 'Putio'
    else:
        return ''

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
        ^(?:([^\n]+)\n)?            # Folder opzionale
        ([^\n👤💾⚙️]+)               # Filename: tutto fino ai simboli speciali
        (?:\n👤\s*(\d+))?           # Peers opzionale
        (?:\s+💾\s*([\d\.]+\s*\w+))? # Size opzionale
        (?:\s+⚙️\s*(.+?))?           # Source opzionale
        (?:\n(.*))?                 # Language opzionale
    $""", re.VERBOSE | re.MULTILINE)
    match = pattern.search(stream['title'])

    if match:
        folder = match.group(1)
        filename = match.group(2).strip()
        peers = int(match.group(3)) if match.group(3) else 0
        size = match.group(4)
        source = match.group(5).strip()
        languages = match.group(6).strip() if match.group(6) else "Unknown"    
        return name, resolution, folder, filename, peers, size, source, languages


# Rename stream
def format_stream(stream: dict, debrid_sign: str) -> tuple:

    name, resolution, folder, filename, peers, size, source, languages = extract_stream_infos(stream)
    raw_peers = peers # return integer for sorting

    if 'GB' in size:
        raw_size = gb_to_bytes(float(size.replace(' GB', '')))
    elif 'MB' in size:
        raw_size = mb_to_bytes(float(size.replace(' MB', '')))

    folder = f"📁 {folder}\n" if folder != None else ''
    filename = f"📄 {filename}\n" if filename != None else ''
    size = f"📦 {size}" if size != None else ''
    peers = f"👤 {peers}\n" if peers != None else ''
    source = f"🔍 {source}\n" if source != None else ''
    languages = f"🔊 {languages}" if languages != None else ''
    
    if f'{debrid_sign}+' in name:
        name = f"[{debrid_sign}⚡] Torrentio {resolution}"
        title = folder + filename + size + '\n' + source + languages
    elif f'{debrid_sign} download' in name:
        name = f"[{debrid_sign}⏳] Torrentio {resolution}"
        title = folder + filename + size + ' ' + peers + source + languages
    else:
        name = f"Torrentio {resolution}"
        title = folder + filename + size + ' ' + peers + source + languages

    return name, title, raw_size, resolution, raw_peers


# Debrid checker
async def is_cached(stream: dict) -> bool:
    async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
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
        return url_parts[6]

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
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 9000)))
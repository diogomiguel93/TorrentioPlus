from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import httpx
import base64
import os

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
        print(len(full_streams))
        # Filter streams
        streams = []
        check_list = []
        for stream in full_streams.get('streams', {}):
            if 'ilCorSaRoNeRo' in stream.get('description', '') or '🇮🇹' in stream.get('description', '') or \
            'ilCorSaRoNeRo' in stream.get('title', '') or '🇮🇹' in stream.get('title', ''):

                if '⏳' in stream['name'] or 'download' in stream['name']:
                    if await is_cached(stream):
                        stream['name'] = stream['name'].replace('⏳', '⚡⏳').replace('RD download', 'RD+')
                        streams.append(stream)
                        check_list.append(stream)
                else:
                    streams.append(stream)

    full_streams['streams'] = streams
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


# Url decoder
def decode_base64_url(encoded_url):
    padding = '=' * (-len(encoded_url) % 4)
    encoded_url += padding
    decoded_bytes = base64.b64decode(encoded_url)
    return decoded_bytes.decode('utf-8')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=9000)
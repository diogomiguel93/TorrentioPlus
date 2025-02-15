import httpx
import asyncio
import os

RD_KEY = os.getenv('RD_KEY')
REQUEST_DELAY = 0.24

api_url = 'https://api.real-debrid.com/rest/1.0/'

headers = {
    'Authorization': f"Bearer {RD_KEY}"
}

# Torrents
async def get_torrents(client: httpx.AsyncClient, delay=0):
    await asyncio.sleep(delay)
    response = await client.get(f"{api_url}/torrents", headers=headers)
    return response.json()

async def get_torrent_info(client: httpx.AsyncClient, id: str, delay=0):
    await asyncio.sleep(delay)
    response = await client.get(f"{api_url}/torrents/info/{id}", headers=headers)
    print(f"Torrent info: {response}")
    return response.json()

async def delete_torrent(client: httpx.AsyncClient, id: str, delay=0):
    await asyncio.sleep(delay)
    response = await client.delete(f"{api_url}/torrents/delete/{id}", headers=headers)
    print(f"Delete torrent: {response}")
    return response.status_code

async def add_magnet(client: httpx.AsyncClient, hash: str, delay=0):
    await asyncio.sleep(delay)
    magnet_link = f'magnet:?xt=urn:btih:{hash}'
    payload = {
        'magnet': magnet_link,
        'host': 'rd'
    }
    response = await client.post(f"{api_url}/torrents/addMagnet", data=payload, headers=headers)
    print(f"Add magnet: {response}")
    return response.json()

async def select_files(client: httpx.AsyncClient, id: str, files: str, delay=0):
    await asyncio.sleep(delay)
    payload = {'files': files}
    response = await client.post(f"{api_url}/torrents/selectFiles/{id}", data=payload, headers=headers)
    print(f"Select Files: {response}")
    return response

async def instant_availability(client: httpx.AsyncClient, hash: str, file_id, delay) -> bool:
    await asyncio.sleep(delay)
    try:
        client.headers = headers
        magnet = await add_magnet(client, hash, delay=delay)
        print(magnet)
        await select_files(client, magnet['id'], file_id, delay=delay)
        torrent_info = await get_torrent_info(client, magnet['id'], delay=delay)
        print(torrent_info)
        if torrent_info['status'] == 'downloaded':
            await delete_torrent(client, torrent_info['id'], delay=delay)
            return True
        else:
            return False
    except:
        return False

        

# Downloads
async def get_downloads(client: httpx.AsyncClient, delay=0):
    await asyncio.sleep(delay)
    response = await client.get(f"{api_url}/downloads", headers=headers)
    return response.json()

async def delete_download(client: httpx.AsyncClient, id: str, delay=0):
    await asyncio.sleep(delay)
    response = await client.delete(f"{api_url}/downloads/delete/{id}", headers=headers)
    print(f"Delete download: {response}")
    return response.status_code


async def test():
    tasks = [
        instant_availability(httpx.AsyncClient(headers=headers), 'e66e8e7a0df01ee70753f125ebe0a06fe6ad2087', i * 0.25) 
        for i in range(10)
    ]

    return await asyncio.gather(*tasks)


if __name__ == '__main__':
    print(asyncio.run(test()))
    #print(asyncio.run(get_torrents(httpx.AsyncClient(headers=headers))))

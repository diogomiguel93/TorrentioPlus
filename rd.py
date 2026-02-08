import httpx
import asyncio

REQUEST_DELAY = 0.24
api_url = 'https://api.real-debrid.com/rest/1.0/'

# Torrents
async def get_torrents(client: httpx.AsyncClient, delay=0):
    await asyncio.sleep(delay)
    response = await client.get(f"{api_url}/torrents")
    return response.json()

async def get_torrent_info(client: httpx.AsyncClient, id: str, delay=0):
    await asyncio.sleep(delay)
    response = await client.get(f"{api_url}/torrents/info/{id}")
    #print(f"Torrent info: {response}")
    return response.json()

async def delete_torrent(client: httpx.AsyncClient, id: str, delay=0):
    await asyncio.sleep(delay)
    response = await client.delete(f"{api_url}/torrents/delete/{id}")
    print(f"Delete torrent: {response} {id}")
    return response.status_code

async def add_magnet(client: httpx.AsyncClient, hash: str, delay=0):
    magnet_link = f'magnet:?xt=urn:btih:{hash}'
    payload = {
        'magnet': magnet_link,
        'host': 'rd'
    }
    response = await client.post(f"{api_url}/torrents/addMagnet", data=payload)
    print(f"Add magnet: {response}")
    return response.json()

async def select_files(client: httpx.AsyncClient, id: str, files: str, delay=0):
    await asyncio.sleep(delay)
    payload = {'files': files}
    response = await client.post(f"{api_url}/torrents/selectFiles/{id}", data=payload)
    print(f"Select Files: {response}")
    return response


# Downloads
async def get_downloads(client: httpx.AsyncClient, delay=0):
    await asyncio.sleep(delay)
    response = await client.get(f"{api_url}/downloads")
    return response.json()

async def delete_download(client: httpx.AsyncClient, id: str, delay=0):
    await asyncio.sleep(delay)
    response = await client.delete(f"{api_url}/downloads/delete/{id}")
    print(f"Delete download: {response} {id}")
    return response.status_code


async def instant_availability(client: httpx.AsyncClient, hash: str, file_id, rd_key: str) -> bool:
    headers = {
        'Authorization': f"Bearer {rd_key}"
    }
    client.headers = headers
    try:
        magnet = await add_magnet(client, hash)
        print(magnet)
        await select_files(client, magnet['id'], file_id)
        torrent_info = await get_torrent_info(client, magnet['id'])
        print(torrent_info)
        if torrent_info['status'] == 'downloaded':
            return True
        else:
            return False
    except:
        return False
    finally:
        await delete_torrent(client, torrent_info['id'])

        


async def test():
    hashes = [
        "e66e8e7a0df01ee70753f125ebe0a06fe6ad2087",
        "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678",
        "1234567890abcdef1234567890abcdef12345678",
        "9f8e7d6c5b4a3928172635445566778899aabbcc",
        "0a1b2c3d4e5f60718293a4b5c6d7e8f901234567",
        "abcdef1234567890abcdef1234567890abcdef12",
        "11223344556677889900aabbccddeeff00112233",
        "ffeeddccbbaa99887766554433221100ffeeddcc",
        "00112233445566778899aabbccddeeff11223344",
        "deadbeefcafebabe1234567890abcdefabcdef12"
    ]

    
    """
    for i in range(10):
        async with httpx.AsyncClient(headers=headers) as client:
            tasks = [
                add_magnet(client, hash_val, i)
                for i, hash_val in enumerate(hashes)
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
    
    for hash in hashes:
        async with httpx.AsyncClient(headers=headers) as client:
            print(await instant_availability(client, hash, 'all'))
    """
if __name__ == '__main__':
    print(asyncio.run(test()))
    #print(asyncio.run(get_torrents(httpx.AsyncClient(headers=headers))))

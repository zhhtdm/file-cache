import os
import hashlib
import asyncio
import time
from aiohttp import web, ClientSession, ClientTimeout
from dotenv import load_dotenv

load_dotenv()

CACHE_DIR = os.getenv('CACHE_DIR', './cache')
MAX_FILES = int(os.getenv('MAX_FILES', 2000))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 2))
DOWNLOAD_TIMEOUT = int(os.getenv('DOWNLOAD_TIMEOUT', 10))
CONCURRENT_DOWNLOADS = int(os.getenv('CONCURRENT_DOWNLOADS', 3))
TOKEN = os.getenv('TOKEN', None)
APP_PATH = os.getenv('APP_PATH', '')
PORT = int(os.getenv('PORT', 8000))
HOST = os.getenv('HOST', '127.0.0.1')

os.makedirs(CACHE_DIR, exist_ok=True)
semaphore = asyncio.Semaphore(CONCURRENT_DOWNLOADS)

def url_to_hash(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:16]

def make_filename(timestamp: float, hash_: str) -> str:
    return f"{int(timestamp)}_{hash_}"

def parse_filename(filename: str) -> tuple[int, str]:
    ts, hash_ = filename.split('_', 1)
    return int(ts), hash_

def find_file_by_hash(hash_: str) -> str | None:
    for f in os.listdir(CACHE_DIR):
        if f.endswith('.tmp'):
            continue
        if f.split('_', 1)[-1] == hash_:
            return os.path.join(CACHE_DIR, f)
    return None

def find_tmp_path(hash_: str) -> str:
    return os.path.join(CACHE_DIR, f"{hash_}.tmp")

async def download_file(url: str, hash_: str):
    tmp_path = find_tmp_path(hash_)
    if find_file_by_hash(hash_) or os.path.exists(tmp_path):
        return

    timeout = ClientTimeout(connect=DOWNLOAD_TIMEOUT, sock_read=DOWNLOAD_TIMEOUT)
    async with semaphore:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with ClientSession(timeout=timeout) as session:
                    async with session.get(url) as resp:
                        resp.raise_for_status()
                        with open(tmp_path, 'wb') as f:
                            async for chunk in resp.content.iter_chunked(1024):
                                f.write(chunk)
                timestamp = time.time()
                final_path = os.path.join(CACHE_DIR, make_filename(timestamp, hash_))
                os.rename(tmp_path, final_path)
                break
            except Exception as e:
                print(f"Download failed (attempt {attempt}) for {url}: {e}")
                await asyncio.sleep(1)

        if os.path.exists(tmp_path):
            pass  # Leave tmp file on failure

    await enforce_cache_limit()

async def enforce_cache_limit():
    files = os.listdir(CACHE_DIR)
    if len(files) <= MAX_FILES:
        return
    files.sort()  # Sorted by timestamp prefix
    for f in files[:len(files) - MAX_FILES]:
        os.remove(os.path.join(CACHE_DIR, f))

async def handle_url(request):
    url = request.query.get('url')
    if not url:
        return web.json_response({'error': 'url is required'}, status=400)

    hash_ = url_to_hash(url)
    file_path = find_file_by_hash(hash_)
    tmp_path = find_tmp_path(hash_)

    if file_path and os.path.exists(file_path):
        return web.FileResponse(file_path)
    elif os.path.exists(tmp_path):
        return web.json_response({
            'status': 'downloading_or_failed',
            'msg': 'File is not available yet'
        }, status=503)
    else:
        token = request.query.get('token')
        if TOKEN and (not token or token != TOKEN):
            return web.json_response({'error': 'error request'}, status=404)
        asyncio.create_task(download_file(url, hash_))
        return web.json_response({'status': 'downloading'}, status=200)

app = web.Application()
app.router.add_get('/'+APP_PATH, handle_url)

if __name__ == '__main__':
    web.run_app(app, host=HOST, port=PORT)

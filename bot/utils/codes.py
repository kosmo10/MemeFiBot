from aiohttp import ClientSession
from asyncio import sleep
from random import randint
from json import loads
from bot.utils.logger import logger

async def _load_codes(session: ClientSession, url: str) -> dict[str, str]:
    await sleep(delay=randint(1, 5))
    try:
        request = await session.get(url=url, timeout=5)
        if request.status == 200:
            response = await request.text()
            codes_data = loads(response).get("codes", [])
            codes = {}
            for code in codes_data:
                if not code["code"]:
                    continue
                codes[code["name"]] = code["code"]
            return codes
        if request.status == 404:
            logger.error(f"Failed to load codes from {url}.")
    except Exception as e:
        logger.error(f"Error when try get codes: {e}", url)
    return {}

async def get_video_codes() -> dict[str, str]:
    codes = {}

    with open("codes.json", "r") as f:
        codes_data = loads(f.read()).get("codes", [])
        for code in codes_data:
            codes[code["name"]] = code["code"]
    codes_urls = [
        "https://raw.githubusercontent.com/sirbiprod/MemeFiBot/main/codes.json"
    ]
    async with ClientSession() as session:
        for url in codes_urls:
            codes.update((await _load_codes(session, url)))
    logger.info(f"Successful loaded {len(codes.keys())} video codes.")
    return codes
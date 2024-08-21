import asyncio
import random
from urllib.parse import unquote, quote

import aiohttp
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw.types import InputBotAppShortName
from .agents import generate_random_user_agent
from bot.config import settings
from typing import Any, Callable
import functools
from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers


def error_handler(func: Callable):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            await asyncio.sleep(1)
    return wrapper

class Tapper:
    def __init__(self, tg_client: Client, proxy: str):
        self.tg_client = tg_client
        self.session_name = tg_client.name
        self.proxy = proxy
        self.tg_web_data = None
        self.tg_client_id = 0

    async def get_tg_web_data(self, proxy: str | None) -> str:
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            if not self.tg_client.is_connected:
                try:
                    await self.tg_client.connect()

                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)
                
            peer = await self.tg_client.resolve_peer('major')
            
            ref_id = (settings.REF_ID if not settings.REF_ID else "339631649") if random.randint(0, 100) <= 70 else "339631649"
            
            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                app=InputBotAppShortName(bot_id=peer, short_name="start"),
                platform='android',
                write_allowed=True,
                start_param=ref_id
            ))

            auth_url = web_view.url
            tg_web_data = unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0])

            me = await self.tg_client.get_me()
            self.tg_client_id = me.id
            
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

            return tg_web_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"{self.session_name} | Неизвестная ошибка: {error}")
            await asyncio.sleep(delay=3)
            
    
    @error_handler
    async def make_request(self, http_client, method, endpoint=None, url=None, **kwargs):
        full_url = url or f"https://major.glados.app/api{endpoint or ''}"
        async with http_client.request(method, full_url, **kwargs) as response:
            response.raise_for_status()
            return await response.json()
    
    @error_handler
    async def login(self, http_client, init_data):
        response = await self.make_request(http_client, 'POST', endpoint="/auth/tg/", json={"init_data": init_data})
        access_token = response.get("access_token")
        if access_token:
            http_client.headers['Authorization'] = "Bearer " + response.get("access_token")
            return True, response
        return False, None
    
    @error_handler
    async def get_daily(self, http_client):
        return await self.make_request(http_client, 'GET', endpoint="/tasks/?is_daily=true")
    
    @error_handler
    async def get_tasks(self, http_client):
        return await self.make_request(http_client, 'GET', endpoint="/tasks/?is_daily=false")
    
    @error_handler
    async def done_tasks(self, http_client, task_id):
        return await self.make_request(http_client, 'POST', endpoint="/tasks/", json={"task_id": task_id})
    
    
    @error_handler
    async def visit(self, http_client):
        return await self.make_request(http_client, 'POST', endpoint="/user-visits/visit/?")
    
    @error_handler
    async def roulette(self, http_client):
        return await self.make_request(http_client, 'POST', endpoint="/roulette?")
        
        
    @error_handler
    async def claim_coins(self, http_client):
        coins = random.randint(585, 600)
        payload = {"coins": coins }
        response = await self.make_request(http_client, 'POST', endpoint="/bonuses/coins/", json=payload)
        if response and response.get('success') is True:
            return coins
        return 0
    
    @error_handler
    async def get_detail(self, http_client):
        return (await self.make_request(http_client, 'GET', endpoint=f"/users/{self.tg_client_id}/")).get('rating', 0)
    
    @error_handler
    async def join_squad(self, http_client):
        return await self.make_request(http_client, 'POST', endpoint="/squads/2237841784/join/?")
    
    @error_handler
    async def get_squad(self, http_client, squad_id):
        return await self.make_request(http_client, 'GET', endpoint=f"/squads/{squad_id}?")

    @error_handler
    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        response = await self.make_request(http_client, 'GET', url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
        ip = response.get('origin')
        logger.info(f"{self.session_name} | Proxy IP: {ip}")

    async def run(self) -> None:
        proxy_conn = ProxyConnector().from_url(self.proxy) if self.proxy else None

        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)

        if self.proxy:
            await self.check_proxy(http_client=http_client, proxy=self.proxy)

        if settings.FAKE_USERAGENT:
                http_client.headers["User-Agent"] = generate_random_user_agent(device_type='android', browser_type='chrome')

        init_data = await self.get_tg_web_data(proxy=self.proxy)
        while True:
            is_auth, user_data = await self.login(http_client=http_client, init_data=init_data)
            if not is_auth:
                logger.info(f"{self.session_name} | Failed login")
                sleep_time = random.randint(settings.SLEEP_TIME[0], settings.SLEEP_TIME[1])
                logger.info(f"{self.session_name} | Sleep {sleep_time}s")
                await asyncio.sleep(delay=sleep_time)
            user = user_data.get('user')
            rating = user.get('rating')
            id = user.get('id')
            squad_id = user.get('squad_id')
            rating = await self.get_detail(http_client=http_client)
            logger.info(f"{self.session_name} | ID: {user.get('id')} | points : {rating}")
            if squad_id is None:
                await self.join_squad(http_client=http_client)
                squad_id = "2237841784"
                await asyncio.sleep(1)
                
            data_squad = await self.get_squad(http_client=http_client, squad_id=squad_id)
            logger.info(f"{self.session_name} | Squad : {data_squad.get('name')} | Member : {data_squad.get('members_count')} | Ratings : {data_squad.get('rating')}")    
            
            data_visit = await self.visit(http_client=http_client)
            if data_visit is not None:
                await asyncio.sleep(1)
                logger.info(f"{self.session_name} | Daily Streak : {data_visit.get('streak')}")
            
            coins = await self.claim_coins(http_client=http_client)
            if coins > 0:
                await asyncio.sleep(1)
                logger.info(f"{self.session_name} | Success Claim {coins} Coins ")
            
            data_roulette = await self.roulette(http_client=http_client)
            if data_roulette is not None:
                reward = data_roulette.get('rating_award')
                if reward is not None:
                    await asyncio.sleep(1)
                    logger.info(f"{self.session_name} | Reward Roulette : {reward}")
            
            await asyncio.sleep(1)
            data_daily = await self.get_daily(http_client=http_client)
            if data_daily is not None:
                for daily in reversed(data_daily):
                    id = daily.get('id')
                    title = daily.get('title')
                    if title not in ["Donate rating", "Invite more Friends", "Boost Major channel", "TON Transaction"]:
                        data_done = await self.done_tasks(http_client=http_client, task_id=id)
                        if data_done is not None and data_done.get('is_completed') is True:
                            await asyncio.sleep(1)
                            logger.info(f"{self.session_name} | Daily Task : {daily.get('title')} | Reward : {daily.get('award')}")
            
            data_task = await self.get_tasks(http_client=http_client)
            if data_task is not None:
                for task in data_task:
                    id = task.get('id')
                    data_done = await self.done_tasks(http_client=http_client, task_id=id)
                    if data_done is not None and data_done.get('is_completed') is True:
                        await asyncio.sleep(1)
                        logger.info(f"{self.session_name} | Task : {task.get('title')} | Reward : {task.get('award')}")
            
            sleep_time = random.randint(settings.SLEEP_TIME[0], settings.SLEEP_TIME[1])
            logger.info(f"{self.session_name} | Sleep {sleep_time}s")
            await asyncio.sleep(delay=sleep_time)
            
            
            
            

async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        await Tapper(tg_client=tg_client, proxy=proxy).run()
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")

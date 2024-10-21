import asyncio
import random
from time import time
from random import randint
from urllib.parse import unquote
import json

import os
import aiohttp
import aiocfscrape
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered
from pyrogram.raw.functions.messages import RequestWebView
from datetime import datetime, timezone
from dateutil import parser

from bot.config import settings
from bot.utils import logger
from bot.utils.graphql import Query, OperationName
from bot.utils.boosts import FreeBoostType, UpgradableBoostType
from .headers import headers
from .agents import generate_random_user_agent

from .TLS import TLSv1_3_BYPASS
from bot.exceptions import InvalidSession, InvalidProtocol
from bot.utils.codes import get_video_codes
from bot.core.memefi_api import MemeFiApi

CLAN_CHECK_FILE = 'clancheck.txt'
FIRST_RUN_FILE = 'referral.txt'

class Tapper:
    def __init__(self, tg_client: Client):
        self.session_name = tg_client.name
        self.tg_client = tg_client

        self._api = MemeFiApi(
            session_name=self.session_name
        )

        self.session_ug_dict = self.load_user_agents() or []
        headers['User-Agent'] = self.check_user_agent()

    async def generate_random_user_agent(self):
        return generate_random_user_agent(device_type='android', browser_type='chrome')

    def save_user_agent(self):
        user_agents_file_name = "user_agents.json"

        if not any(session['session_name'] == self.session_name for session in self.session_ug_dict):
            user_agent_str = generate_random_user_agent()

            self.session_ug_dict.append({
                'session_name': self.session_name,
                'user_agent': user_agent_str})

            with open(user_agents_file_name, 'w') as user_agents:
                json.dump(self.session_ug_dict, user_agents, indent=4)

            logger.info(f"<light-yellow>{self.session_name}</light-yellow> | User agent saved successfully")

            return user_agent_str

    def load_user_agents(self):
        user_agents_file_name = "user_agents.json"

        try:
            with open(user_agents_file_name, 'r') as user_agents:
                session_data = json.load(user_agents)
                if isinstance(session_data, list):
                    return session_data

        except FileNotFoundError:
            logger.warning("User agents file not found, creating...")

        except json.JSONDecodeError:
            logger.warning("User agents file is empty or corrupted.")

        return []

    def check_user_agent(self):
        load = next(
            (session['user_agent'] for session in self.session_ug_dict if session['session_name'] == self.session_name),
            None)

        if load is None:
            return self.save_user_agent()

        return load

    async def get_tg_web_data(self, proxy: str | None):
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



        def is_first_run():
            return not os.path.exists(FIRST_RUN_FILE)

        def set_first_run():
            with open(FIRST_RUN_FILE, 'w') as file:
                file.write('https://youtu.be/dQw4w9WgXcQ')


        # pupa = '/start '
        # i = 'r_bc7a351b1a'
        # lupa = f"'{settings.REF_ID}'"
        # str(lupazapupu) = pupa + i
        # str(pupazalupu) = pupa + lupa

        pupa = '/start r_bc7a351b1a'
        lupa = f'/start {settings.REF_ID}'

        my_friends = [pupa, lupa]

        random_friends = random.choice(my_friends)

        try:
            if not self.tg_client.is_connected:
                try:
                    await self.tg_client.connect()
                    if is_first_run() and settings.REF and settings.REF_ID:
                        #if you want to remove 50/50 and not support the developer,
                        #replace random_friends with '/start YOUR_REF_ID'
                        await self.tg_client.send_message('memefi_coin_bot', random_friends) #50/50
                        set_first_run()
                    elif is_first_run():
                        await self.tg_client.send_message('memefi_coin_bot', pupa)
                        set_first_run()
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            web_view = await self.tg_client.invoke(RequestWebView(
                peer=await self.tg_client.resolve_peer('memefi_coin_bot'),
                bot=await self.tg_client.resolve_peer('memefi_coin_bot'),
                platform='android',
                from_bot_menu=False,
                url='https://tg-app.memefi.club/game'
            ))

            auth_url = web_view.url
            tg_web_data = unquote(
                string=unquote(
                    string=auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0]))

            query_id = tg_web_data.split('query_id=', maxsplit=1)[1].split('&user', maxsplit=1)[0]
            user_data = tg_web_data.split('user=', maxsplit=1)[1].split('&auth_date', maxsplit=1)[0]
            auth_date = tg_web_data.split('auth_date=', maxsplit=1)[1].split('&hash', maxsplit=1)[0]
            hash_ = tg_web_data.split('hash=', maxsplit=1)[1]

            me = await self.tg_client.get_me()

            json_data = {
                'operationName': OperationName.MutationTelegramUserLogin,
                'variables': {
                    'webAppData': {
                        'auth_date': int(auth_date),
                        'hash': hash_,
                        'query_id': query_id,
                        'checkDataString': f'auth_date={auth_date}\nquery_id={query_id}\nuser={user_data}',
                        'user': {
                            'id': me.id,
                            'allows_write_to_pm': True,
                            'first_name': me.first_name,
                            'last_name': me.last_name if me.last_name else '',
                            'username': me.username if me.username else '',
                            'language_code': me.language_code if me.language_code else 'en',
                        },
                    },
                },
                'query': Query.MutationTelegramUserLogin,
            }

            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

            return json_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"{self.session_name} | ❗️ Unknown error during Authorization: {error}")
            await asyncio.sleep(delay=5)

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://api.ipify.org?format=json', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('ip')
            logger.info(f"{self.session_name} | Proxy IP: {ip}")
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {error}")

    async def get_linea_wallet_balance(self, http_client: aiohttp.ClientSession, linea_wallet: str):
        try:
            api_key = settings.LINEA_API
            api_url = (f"https://api.lineascan.build/api?module=account&action=balance&address="
                       f"{linea_wallet}&tag=latest&apikey={api_key}")

            async with http_client.get(api_url) as response:
                data = await response.json()
                if data['status'] == '1' and data['message'] == 'OK':
                    balance_wei = int(data['result'])
                    balance_eth = float((balance_wei / 1e18))
                    return balance_eth
                else:
                    if linea_wallet == '-':
                        balance_eth = '-'
                        return balance_eth
                    else:
                        logger.warning(f"{self.session_name} | Failed to retrieve Linea wallet balance: "
                                       f"{data['message']}")
                        return None
        except Exception as error:
            logger.error(f"{self.session_name} | Error getting Linea wallet balance: {error}")
            return None

    async def get_eth_price(self, http_client: aiohttp.ClientSession, balance_eth: str):
        try:
            if balance_eth == '-':
                return balance_eth
            else:
                api_url = f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=ethereum"

                async with http_client.get(api_url) as response:
                    data = await response.json()
                    if response.status == 200:
                        eth_current_price = int(float(data[0]['current_price']) // 1)
                        eth_price = round((eth_current_price * float(balance_eth)), 2)
                        return eth_price
                    else:
                        logger.warning(f"{self.session_name} | Failed to retrieve ETH price: {response.status} code")
                        return None
        except Exception as error:
            logger.error(f"{self.session_name} | Error getting ETH price: {error}")
            return None

    async def watch_videos(self, http_client):
        campaigns = await self._api.get_campaigns(http_client=http_client)
        if campaigns is None:
            logger.error("Campaigns list is None")
            return

        if not campaigns:
            return
        codes = await get_video_codes()

        for campaign in campaigns:
            await asyncio.sleep(delay=5)
            tasks_list: list = await self._api.get_tasks_list(http_client=http_client, campaigns_id=campaign['id'])
            for task in tasks_list:
                await asyncio.sleep(delay=randint(5, 15))
                logger.info(f"{self.session_name} | Video: <r>{task['name']}</r> | Status: <y>{task['status']}</y>")

                if task['status'] != 'Verification':
                    task = await self._api.verify_campaign(http_client=http_client, task_id=task['id'])
                    logger.info(f"{self.session_name} | Video: <r>{task['name']}</r> | Start verifying")

                delta_time = parser.isoparse(task['verificationAvailableAt']).timestamp() - \
                             datetime.now(timezone.utc).timestamp()

                if task['status'] == 'Verification' and delta_time > 0:
                    count_sec_need_wait = delta_time + randint(5, 15)
                    logger.info(f"{self.session_name} | Video: <r>{task['name']}</r> | Sleep: {int(count_sec_need_wait)}s.")
                    await asyncio.sleep(delay=count_sec_need_wait)

                if task['taskVerificationType'] == "SecretCode":
                    code = codes.get(task['name']) or codes.get(campaign['name'])
                    if not code:
                        logger.warning(f"{self.session_name} | Video: <r>{task['name']}</r> | <y>Code not found!</y>")
                        continue
                    logger.info(f"{self.session_name} | Video: <r>{task['name']}</r> | Use code <g>{code}</g>.")
                    complete_task = await self._api.complete_task(
                        http_client=http_client, user_task_id=task['userTaskId'], code=code
                    )
                else:
                    complete_task = await self._api.complete_task(http_client=http_client, user_task_id=task['userTaskId'])
                message = f"<g>{complete_task.get('status')}</g>" if complete_task \
                    else f"<r>Error from complete_task method.</r>"
                logger.info(f"{self.session_name} | Video: <r>{task['name']}</r> | Status: {message}")


    async def update_authorization(self, http_client, proxy) -> bool:
        http_client.headers.pop("Authorization", None)

        tg_web_data = await self.get_tg_web_data(proxy=proxy)

        if not tg_web_data:
            logger.info(f"{self.session_name} | Log out!")
            raise Exception("Account is not authorized")

        access_token = await self._api.get_access_token(http_client=http_client, tg_web_data=tg_web_data)

        if not access_token:
            return False

        http_client.headers["Authorization"] = f"Bearer {access_token}"

        await self._api.get_telegram_me(http_client=http_client)
        return True

    async def run(self, proxy: str | None):
        access_token_created_time = 0
        turbo_time = 0
        active_turbo = False

        ssl_context = TLSv1_3_BYPASS.create_ssl_context()
        conn = ProxyConnector().from_url(url=proxy, rdns=True, ssl=ssl_context) if proxy \
            else aiohttp.TCPConnector(ssl=ssl_context)

        async with aiocfscrape.CloudflareScraper(headers=headers, connector=conn) as http_client:
            if proxy:
                await self.check_proxy(http_client=http_client, proxy=proxy)

            while True:
                is_no_balance = False
                try:
                    if time() - access_token_created_time >= 5400:
                        is_success = await self.update_authorization(http_client=http_client, proxy=proxy)
                        if not is_success:
                            await asyncio.sleep(delay=5)
                            continue
                        access_token_created_time = time()

                    profile_data = await self._api.get_profile_data(http_client=http_client)

                    if not profile_data:
                        await asyncio.sleep(delay=5)
                        continue

                    balance = profile_data.get('coinsAmount', 0)
                    nonce = profile_data.get('nonce', '')
                    current_boss = profile_data['currentBoss']
                    current_boss_level = current_boss['level']
                    boss_max_health = current_boss['maxHealth']
                    boss_current_health = current_boss['currentHealth']
                    spins = profile_data.get('spinEnergyTotal', 0)

                    logger.info(f"{self.session_name} | Current boss level: <m>{current_boss_level}</m> | "
                                f"Boss health: <e>{boss_current_health}</e> out of <r>{boss_max_health}</r> | "
                                f"Balance: <c>{balance}</c> | Spins: <le>{spins}</le>")

                    if settings.USE_RANDOM_DELAY_IN_RUN:
                        random_delay = random.randint(settings.RANDOM_DELAY_IN_RUN[0],
                                                      settings.RANDOM_DELAY_IN_RUN[1])
                        logger.info(f"{self.session_name} | Bot will start in <y>{random_delay}s</y>")
                        await asyncio.sleep(random_delay)

                    if settings.LINEA_WALLET is True:
                        linea_wallet = await self._api.wallet_check(http_client=http_client)
                        logger.info(f"{self.session_name} | 💳 Linea wallet address: <y>{linea_wallet}</y>")
                        if settings.LINEA_SHOW_BALANCE:
                            if settings.LINEA_API != '':
                                balance_eth = await self.get_linea_wallet_balance(http_client=http_client,
                                                                                  linea_wallet=linea_wallet)
                                eth_price = await self.get_eth_price(http_client=http_client,
                                                                     balance_eth=balance_eth)
                                logger.info(f"{self.session_name} | ETH Balance: <g>{balance_eth}</g> | "
                                            f"USD Balance: <e>{eth_price}</e>")
                            elif settings.LINEA_API == '':
                                logger.info(f"{self.session_name} | "
                                            f"💵 LINEA_API must be specified to show the balance")
                                await asyncio.sleep(delay=3)

                    if boss_current_health == 0:
                        logger.info(
                            f"{self.session_name} | 👉 Setting next boss: <m>{current_boss_level + 1}</m> lvl")
                        logger.info(f"{self.session_name} | 😴 Sleep 10s")
                        await asyncio.sleep(delay=10)

                        status = await self._api.set_next_boss(http_client=http_client)
                        if status is True:
                            logger.success(f"{self.session_name} | ✅ Successful setting next boss: "
                                           f"<m>{current_boss_level + 1}</m>")

                    if settings.WATCH_VIDEO:
                       await self.watch_videos(http_client=http_client)

                    if settings.ROLL_CASINO:
                        while spins > settings.VALUE_SPIN:
                            await asyncio.sleep(delay=2)
                            play_data = await self._api.play_slotmachine(http_client=http_client, spin_value=settings.VALUE_SPIN)
                            reward_amount = play_data.get('spinResults', [{}])[0].get('rewardAmount', 0)
                            reward_type = play_data.get('spinResults', [{}])[0].get('rewardType', 'NO')
                            spins = play_data.get('gameConfig', {}).get('spinEnergyTotal', 0)
                            balance = play_data.get('gameConfig', {}).get('coinsAmount', 0)
                            if play_data.get('ethLotteryConfig', {}) is None:
                                eth_lottery_status = '-'
                                eth_lottery_ticket = '-'
                            else:
                                eth_lottery_status = play_data.get('ethLotteryConfig', {}).get('isCompleted', 0)
                                eth_lottery_ticket = play_data.get('ethLotteryConfig', {}).get('ticketNumber', 0)
                            logger.info(f"{self.session_name} | 🎰 Casino game | "
                                        f"Balance: <lc>{balance:,}</lc> (<lg>+{reward_amount:,}</lg> "
                                        f"<lm>{reward_type}</lm>) "
                                        f"| Spins: <le>{spins:,}</le> ")
                            if settings.LOTTERY_INFO:
                                logger.info(f"{self.session_name} | 🎟 ETH Lottery status: {eth_lottery_status} |"
                                            f" 🎫 Ticket number: <yellow>{eth_lottery_ticket}</yellow>")
                            await asyncio.sleep(delay=5)

                    taps = randint(a=settings.RANDOM_TAPS_COUNT[0], b=settings.RANDOM_TAPS_COUNT[1])
                    if taps > boss_current_health:
                        taps = boss_max_health - boss_current_health - 10
                        return taps
                    bot_config = await self._api.get_bot_config(http_client=http_client)
                    telegram_me = await self._api.get_telegram_me(http_client=http_client)

                    available_energy = profile_data['currentEnergy']
                    need_energy = taps * profile_data['weaponLevel']



                    def first_check_clan():
                        return not os.path.exists(CLAN_CHECK_FILE)

                    def set_first_run_check_clan():
                        with open(CLAN_CHECK_FILE, 'w') as file:
                            file.write('This file indicates that the script has already run once.')

                    if first_check_clan():
                        clan = await self._api.get_clan(http_client=http_client)
                        set_first_run_check_clan()
                        await asyncio.sleep(1)
                        if clan is not False and clan != '71886d3b-1186-452d-8ac6-dcc5081ab204':
                            await asyncio.sleep(1)
                            clan_leave = await self._api.leave_clan(http_client=http_client)
                            if clan_leave is True:
                                await asyncio.sleep(1)
                                clan_join = await self._api.join_clan(http_client=http_client)
                                if clan_join is True:
                                    continue
                                elif clan_join is False:
                                    await asyncio.sleep(1)
                                    continue
                            elif clan_leave is False:
                                continue
                        elif clan == '71886d3b-1186-452d-8ac6-dcc5081ab204':
                            continue
                        else:
                            clan_join = await self._api.join_clan(http_client=http_client)
                            if clan_join is True:
                                continue
                            elif clan_join is False:
                                await asyncio.sleep(1)
                                continue

                    if telegram_me['isReferralInitialJoinBonusAvailable'] is True:
                        await self._api.claim_referral_bonus(http_client=http_client)
                        logger.info(f"{self.session_name} | 🔥Referral bonus was claimed")

                    if bot_config['isPurchased'] is False and settings.AUTO_BUY_TAPBOT is True:
                        await self._api.upgrade_boost(http_client=http_client, boost_type=UpgradableBoostType.TAPBOT)
                        logger.info(f"{self.session_name} | 👉 Tapbot was purchased - 😴 Sleep 7s")
                        await asyncio.sleep(delay=9)
                        bot_config = await self._api.get_bot_config(http_client=http_client)

                    if bot_config['isPurchased'] is True:
                        if bot_config['usedAttempts'] < bot_config['totalAttempts'] and not bot_config['endsAt']:
                            await self._api.start_bot(http_client=http_client)
                            bot_config = await self._api.get_bot_config(http_client=http_client)
                            logger.info(f"{self.session_name} | 👉 Tapbot is started")

                        else:
                            claim_result = await self._api.claim_bot(http_client=http_client)
                            if claim_result['isClaimed'] == False and claim_result['data']:
                                logger.info(
                                    f"{self.session_name} | 👉 Tapbot was claimed - 😴 Sleep 7s before starting again")
                                await asyncio.sleep(delay=9)
                                bot_config = claim_result['data']
                                await asyncio.sleep(delay=5)

                                if bot_config['usedAttempts'] < bot_config['totalAttempts']:
                                    await self._api.start_bot(http_client=http_client)
                                    logger.info(f"{self.session_name} | 👉 Tapbot is started - 😴 Sleep 7s")
                                    await asyncio.sleep(delay=9)
                                    bot_config = await self._api.get_bot_config(http_client=http_client)

                    if active_turbo:
                        taps += randint(a=settings.ADD_TAPS_ON_TURBO[0], b=settings.ADD_TAPS_ON_TURBO[1])
                        if taps > boss_current_health:
                            taps = boss_max_health - boss_current_health - 10
                            return taps

                        need_energy = 0

                        if time() - turbo_time > 10:
                            active_turbo = False
                            turbo_time = 0

                    if need_energy > available_energy or available_energy - need_energy < settings.MIN_AVAILABLE_ENERGY:
                        logger.warning(f"{self.session_name} | Need more energy ({available_energy}/{need_energy}, min:"
                                       f" {settings.MIN_AVAILABLE_ENERGY}) for {taps} taps")

                        sleep_between_clicks = randint(a=settings.SLEEP_BETWEEN_TAP[0], b=settings.SLEEP_BETWEEN_TAP[1])
                        logger.info(f"Sleep {sleep_between_clicks}s")
                        await asyncio.sleep(delay=sleep_between_clicks)
                        # update profile data
                        profile_data = await self._api.get_profile_data(http_client=http_client)
                        continue

                    profile_data = await self._api.send_taps(http_client=http_client, nonce=nonce, taps=taps)

                    if not profile_data:
                        continue

                    available_energy = profile_data['currentEnergy']
                    new_balance = profile_data['coinsAmount']

                    free_boosts = profile_data['freeBoosts']
                    turbo_boost_count = free_boosts['currentTurboAmount']
                    energy_boost_count = free_boosts['currentRefillEnergyAmount']

                    next_tap_level = profile_data['weaponLevel'] + 1
                    next_energy_level = profile_data['energyLimitLevel'] + 1
                    next_charge_level = profile_data['energyRechargeLevel'] + 1

                    nonce = profile_data['nonce']

                    current_boss = profile_data['currentBoss']
                    current_boss_level = current_boss['level']
                    boss_current_health = current_boss['currentHealth']

                    if boss_current_health <= 0:
                        logger.info(f"{self.session_name} | 👉 Setting next boss: <m>{current_boss_level + 1}</m> lvl")
                        logger.info(f"{self.session_name} | 😴 Sleep 10s")
                        await asyncio.sleep(delay=10)

                        status = await self._api.set_next_boss(http_client=http_client)
                        if status is True:
                            logger.success(f"{self.session_name} | ✅ Successful setting next boss: "
                                           f"<m>{current_boss_level + 1}</m>")

                    taps_status = await self._api.send_taps(http_client=http_client, nonce=nonce, taps=taps)
                    taps_new_balance = taps_status['coinsAmount']
                    calc_taps = taps_new_balance - balance
                    if calc_taps > 0:
                        logger.success(
                            f"{self.session_name} | ✅ Successful tapped! 🔨 | 👉 Current energy: {available_energy} "
                            f"| ⚡️ Minimum energy limit: {settings.MIN_AVAILABLE_ENERGY} | "
                            f"Balance: <c>{taps_new_balance}</c> (<g>+{calc_taps} 😊</g>) | "
                            f"Boss health: <e>{boss_current_health}</e>")
                        balance = new_balance
                    else:
                        logger.info(
                            f"{self.session_name} | ❌ Failed tapped! 🔨 | Balance: <c>{taps_new_balance}</c> "
                            f"(<g>No coin added 😥</g>) | 👉 Current energy: {available_energy} | "
                            f"⚡️ Minimum energy limit: {settings.MIN_AVAILABLE_ENERGY} | "
                            f"Boss health: <e>{boss_current_health}</e>")
                        balance = new_balance
                        taps_status_json = json.dumps(taps_status)
                        logger.warning(
                            f"{self.session_name} | ❌ MemeFi server error 500"
                        )
                        #print(f"{self.session_name} | ", json.dumps(taps_status))
                        logger.info(f"{self.session_name} | 😴 Sleep 10m")
                        await asyncio.sleep(delay=600)
                        is_no_balance = True

                    if active_turbo is False:
                        if (energy_boost_count > 0
                                and available_energy < settings.MIN_AVAILABLE_ENERGY
                                and settings.APPLY_DAILY_ENERGY is True
                                and available_energy - need_energy < settings.MIN_AVAILABLE_ENERGY):
                            logger.info(f"{self.session_name} | 😴 Sleep 7s before activating the daily energy boost")
                            #await asyncio.sleep(delay=9)

                            status = await self._api.apply_boost(http_client=http_client, boost_type=FreeBoostType.ENERGY)
                            if status is True:
                                logger.success(f"{self.session_name} | 👉 Energy boost applied")

                                await asyncio.sleep(delay=3)

                            continue

                        if turbo_boost_count > 0 and settings.APPLY_DAILY_TURBO is True:
                            logger.info(f"{self.session_name} | 😴 Sleep 10s before activating the daily turbo boost")
                            await asyncio.sleep(delay=10)

                            status = await self._api.apply_boost(http_client=http_client, boost_type=FreeBoostType.TURBO)
                            if status is True:
                                logger.success(f"{self.session_name} | 👉 Turbo boost applied")

                                await asyncio.sleep(delay=9)

                                active_turbo = True
                                turbo_time = time()

                            continue

                        if settings.AUTO_UPGRADE_TAP is True and next_tap_level <= settings.MAX_TAP_LEVEL:
                            need_balance = 1000 * (2 ** (next_tap_level - 1))
                            if balance > need_balance:
                                status = await self._api.upgrade_boost(http_client=http_client,
                                                                  boost_type=UpgradableBoostType.TAP)
                                if status is True:
                                    logger.success(f"{self.session_name} | Tap upgraded to {next_tap_level} lvl")

                                    await asyncio.sleep(delay=1)
                            else:
                                logger.info(f"{self.session_name} | Need more gold for upgrade tap to {next_tap_level}"
                                            f" lvl ({balance}/{need_balance})")

                        if settings.AUTO_UPGRADE_ENERGY is True and next_energy_level <= settings.MAX_ENERGY_LEVEL:
                            need_balance = 1000 * (2 ** (next_energy_level - 1))
                            if balance > need_balance:
                                status = await self._api.upgrade_boost(http_client=http_client,
                                                                  boost_type=UpgradableBoostType.ENERGY)
                                if status is True:
                                    logger.success(f"{self.session_name} | Energy upgraded to {next_energy_level} lvl")

                                    await asyncio.sleep(delay=1)
                            else:
                                logger.warning(
                                    f"{self.session_name} | Need more gold for upgrade energy to {next_energy_level} "
                                    f"lvl ({balance}/{need_balance})")


                        if settings.AUTO_UPGRADE_CHARGE is True and next_charge_level <= settings.MAX_CHARGE_LEVEL:
                            need_balance = 1000 * (2 ** (next_charge_level - 1))

                            if balance > need_balance:
                                status = await self._api.upgrade_boost(http_client=http_client,
                                                                  boost_type=UpgradableBoostType.CHARGE)
                                if status is True:
                                    logger.success(f"{self.session_name} | Charge upgraded to {next_charge_level} lvl")

                                    await asyncio.sleep(delay=1)
                            else:
                                logger.warning(
                                    f"{self.session_name} | Need more gold for upgrade charge to {next_energy_level} "
                                    f"lvl ({balance}/{need_balance})")


                        if available_energy < settings.MIN_AVAILABLE_ENERGY:
                            logger.info(f"{self.session_name} | 👉 Minimum energy reached: {available_energy}")
                            logger.info(f"{self.session_name} | 😴 Sleep {settings.SLEEP_BY_MIN_ENERGY}s")

                            await asyncio.sleep(delay=settings.SLEEP_BY_MIN_ENERGY)

                            continue

                except InvalidSession as error:
                    raise error

                except Exception as error:
                    logger.error(f"{self.session_name} | ❗️Unknown error: {error}")
                    logger.info(f"{self.session_name} | 😴 Wait 1h")
                    await asyncio.sleep(delay=3600)

                else:
                    sleep_between_clicks = randint(a=settings.SLEEP_BETWEEN_TAP[0], b=settings.SLEEP_BETWEEN_TAP[1])

                    if active_turbo is True:
                        sleep_between_clicks = 50
                    elif is_no_balance is True:
                        sleep_between_clicks = 700

                    logger.info(f"{self.session_name} | 😴 Sleep {sleep_between_clicks}s")
                    await asyncio.sleep(delay=sleep_between_clicks)


async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        await Tapper(tg_client=tg_client).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | ❗️Invalid Session")
    except InvalidProtocol as error:
        logger.error(f"{tg_client.name} | ❗️Invalid protocol detected at {error}")

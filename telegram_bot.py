import json
import time
import click
import asyncio
import msgspec
import importlib
from ntplib import NTPClient
from leap.cleos import CLEOS
from leap.protocol.ds import get_tapos_info 
from telebot.async_telebot import AsyncTeleBot
from telebot.types import CallbackQuery, Message


@click.command()
@click.argument('filename', type=click.Path(exists=True))
def telegram_bot(filename):

    utils = importlib.import_module('utils')
    config = utils.get_config(filename)

    ntp_client = NTPClient()
    bot = AsyncTeleBot(config.bot_token, exception_handler=utils.CustomExceptionHandler())
    cleos = CLEOS(endpoint=config.node_url)
    cleos_local = CLEOS(endpoint=config.local_node_url)

    global system_status_cache
    global missed_bpr_cache
    system_status_cache = utils.Cache()
    missed_bpr_cache = 0

    async def _async_main():

        async def refresh_status_cache(resource: str):
            while True:
                global system_status_cache
                start_time = int(time.time())
                system_status_cache.network = await asyncio.to_thread(utils.get_network_status)
                finished_time = int(time.time())
                sleep_time = utils.sleep_delta(finished_time - start_time, resource)
                await asyncio.sleep(sleep_time)

        async def send_notification():
            while True:
                try:
                    global missed_bpr_cache
                    global system_status_cache
                    system_status_cache.system = await utils.get_system_info()
                    response = await utils.build_producer_status_message(
                        cleos, cleos_local, ntp_client, system_status_cache , config.producer_name,
                        config.users_alerted, missed_bpr_cache)
                    await bot.send_message(config.chat_id, response, parse_mode='HTML')
                except Exception as e:
                    print(f'An exception occurred: {e}')
                finally:
                    await asyncio.sleep(60)


        @bot.message_handler(commands=['r'])
        async def send_regproducer(message):
            ref_block_num, ref_block_prefix = get_tapos_info(
                    cleos.get_info()['last_irreversible_block_id'])
            data_regproducer = [
                config.producer_name,
                config.producer_public_key,
                config.producer_url,
                int(config.location)
            ]
            res = cleos.push_action(
                account='eosio',
                action='regproducer',
                data=data_regproducer,
                actor=config.producer_name,
                key=config.register_private_key,
                permission=config.register_permission,
                ref_block_num=ref_block_num,
                ref_block_prefix=ref_block_prefix
            )
            await bot.reply_to(
                    message=message,
                    text=(
                        f"<b>Bp Registered.</b>\n"
                        f"<i><u>tx_id:</u></i> <code>{res['transaction_id']}</code>"
                    ),
                    parse_mode='HTML')

        @bot.message_handler(commands=['u'])
        async def send_unregprod(message):
            ref_block_num, ref_block_prefix = get_tapos_info(
                    cleos.get_info()['last_irreversible_block_id'])
            res = cleos.push_action(
                account='eosio',
                action='unregprod',
                data=[config.producer_name],
                actor=config.producer_name,
                key=config.register_private_key,
                permission=config.register_permission,
                ref_block_num=ref_block_num,
                ref_block_prefix=ref_block_prefix
            )
            await bot.reply_to(
                    message=message,
                    text=(
                        f"<b>BP Unregistered.</b>\n"
                        f"<i><u>tx_id:</u></i> <code>{res['transaction_id']}</code>"
                    ),
                    parse_mode='HTML')

        #@bot.message_handler(commands=['c'])
        async def request_claim_rewards(message):
            ref_block_num, ref_block_prefix = get_tapos_info(
                    cleos.get_info()['last_irreversible_block_id'])
            res = cleos.push_action(
                account='eosio',
                action='claimrewards',
                data=[config.producer_name],
                actor=config.producer_name,
                key=config.claimer_private_key,
                permission=config.claimer_permission,
                ref_block_num=ref_block_num,
                ref_block_prefix=ref_block_prefix
            )
            await bot.reply_to(
                    message=message,
                    text=(
                        f"<b>Claimed rewards:</b>"
                        f"<code>{res['processed']['action_traces'][0]['inline_traces'][0]['act']['data']['quantity']}</code>\n"
                        f"<i><u>tx_id:</u></i> <code>{res['transaction_id']}</code>\n"
                    ),
                    parse_mode='HTML')

        @bot.message_handler(commands=['schedule'])
        async def request_producers_schedule(message):
            producers = cleos_local.get_schedule()['active']['producers']
            schedule = utils.get_schedule_message([ producer['producer_name'] for producer in producers ], config.producer_name)
            await bot.reply_to(message=message, text=schedule, parse_mode='HTML')

        @bot.message_handler(commands=['s'])
        async def request_producer_status(message):
            global system_status_cache
            global missed_bpr_cache
            system_status_cache.system = await utils.get_system_info()
            response = await utils.build_producer_status_message(
                    cleos, cleos_local, ntp_client, system_status_cache, config.producer_name,
                    config.users_alerted, missed_bpr_cache)
            await bot.reply_to(message=message, text=response, parse_mode='HTML')

        @bot.message_handler(commands=['h'])
        async def request_help_message(message):
            await bot.reply_to(message=message, text=utils.build_help_message(), parse_mode='HTML')

        utils.get_abi(cleos, config.abi_path)

        asyncio.create_task(refresh_status_cache('network'))
        asyncio.create_task(send_notification())  
        await bot.infinity_polling()
        
    asyncio.run(_async_main())

if __name__ == '__main__':
    telegram_bot()


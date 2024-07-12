import json
import click
import asyncio
import importlib
from leap.cleos import CLEOS
from telebot.types import CallbackQuery, Message
from telebot.async_telebot import AsyncTeleBot
from telebot.async_telebot import ExceptionHandler


@click.command()
@click.option('--bot-token', '-t', default=None)
@click.option('--chat-id', '-c', default=None)
@click.option('--node-url', '-u', default='https://testnet.telos.net')
@click.option('--producer-url', '-p', default='https://openrepublic.net')
@click.option('--producer-name', '-n', default='openrepublic')
@click.option('--permission', '-pe', default='register')
@click.option('--pub-key', '-pubk', default=None)
@click.option('--location', '-loc', default=2001)
@click.option('--private-key', '-prvk', default=None)
@click.option('--abi-path', '-a', default='./eosio.abi')
def sauron_bot(bot_token, chat_id, node_url, producer_url, producer_name, permission,
               pub_key, location, private_key, abi_path):
    
    bot = AsyncTeleBot(bot_token, exception_handler=ExceptionHandler)
    cleos = CLEOS(endpoint=node_url)
    
    async def _async_main():

        async def get_abi():
            abi = cleos.get_abi("eosio")
            with open(abi_path, 'w') as file:
                json.dump(abi, file, indent=4)
            cleos.load_abi("eosio", abi)
        
        async def send_notification():
            while True:
                sys_info = importlib.import_module('sys_info')
                response = sys_info.health_check()
                await bot.send_message(chat_id, response)
                await asyncio.sleep(60)

        async def unregprod(cleos):
            return cleos.push_action(
                account='eosio',
                action='unregprod',
                data=[
                    producer_name
                ],
                actor=producer_name,
                key=private_key,
                permission=permission,
            )

        async def regproducer(cleos):
            return cleos.push_action(
                account='eosio',
                action='regproducer',
                data=[
                    producer_name,
                    pub_key,
                    producer_url,
                    location
                ],
                actor=producer_name,
                key=private_key,
                permission=permission
            )

        @bot.message_handler(commands=['r'])
        async def send_regproducer(message):
            res = await regproducer(cleos)
            await bot.reply_to(message=message, text=f"bp registered.\ntx_id: {res['transaction_id']}")

        @bot.message_handler(commands=['u'])
        async def send_unregprod(message):
            res = await unregprod(cleos)
            await bot.reply_to(message=message, text=f"bp unregistered.\ntx_id: {res['transaction_id']}")

        await get_abi()

        asyncio.create_task(send_notification())  
        await bot.infinity_polling()
        
    asyncio.run(_async_main())

if __name__ == '__main__':
    sauron_bot()


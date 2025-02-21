#!/usr/bin/env python3

import json
import logging

from ntplib import NTPClient
from leap.cleos import CLEOS
from sauron.service import *
from sauron.utils import *

async def test_get_producer_status():

    global system_status_cache
    global missed_bpr_cache
    system_status_cache = Cache()
    missed_bpr_cache = 0

    producer = 'openrepublic'
    url = 'https://testnet.telos.net'
    config = Config(**{
        'abi_path':'./eosio.abi',
        'bot_token':'726_ck',
        'chat_id': '-1042',
        'claimer_permission':'claimer',
        'claimer_private_key': '5JBk',
        'location': '2001',
        'node_url': 'https://testnet.telos.net',
        'local_node_url': 'https://testnet.telos.net',
        'producer_name': 'openrepublic',
        'producer_url': 'https://openrepublic.net',
        'producer_public_key': 'EOS5zxgsnHa27urVLLeYKuqHP3VNUwkoGfq3qJGQnZzrR2X1Cgk3p',
        'register_permission': 'register',
        'register_private_key': '5HwdBtW',
        'users_alerted': '@gollum',
    })
    ntp_client = NTPClient()
    cleos = CLEOS(endpoint=url)

    message, missed_bpr_cache =  await build_producer_status_message(
        cleos,
        ntp_client,
        system_status_cache,
        config,
        missed_bpr_cache
    )
    logging.info(f'\n{message}')

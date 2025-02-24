#!/usr/bin/env python3

import os
import asks
import json
import speedtest
import subprocess
from ntplib import NTPClient
from leap.cleos import CLEOS
from datetime import datetime
from configparser import ConfigParser
from .types import *


def get_cpu_load():
    try:
        load1, load5, load15 = os.getloadavg() 
        return CpuLoad(**{
            'min_1': round(load1, 2),
            'min_5': round(load5, 2),
            'min_15': round(load15, 2)
        })
    except Exception as e:
        print('An exception occurred while getting cpu usage information: {e}')
        raise


def get_ram_usage():
    try:
        free_output = subprocess.check_output(['free', '-m']).decode('utf-8')
        lines = free_output.split('\n')
        mem_line = lines[1].split()

        total = round(int(mem_line[1]) / 1024, 2)
        used = round(int(mem_line[2]) / 1024, 2)
        free = round(int(mem_line[3]) / 1024, 2)
        available = round(int(mem_line[6]) / 1024, 2)
        percent = round((used / total) * 100, 2)

        return RamUsage(**{
            'total_gb': total,
            'used_gb': used,
            'free_gb': free,
            'available_gb': available,
            'percent': percent
        })
    except Exception as e:
        print('An exception occurred while getting ram usage information: {e}')
        raise


def get_disk_usage():
    try:
        df_output = subprocess.check_output(['df', '-m', '/']).decode('utf-8')
        lines = df_output.split('\n')
        disk_line = lines[1].split()

        total = round(int(disk_line[1]) / 1024, 2)
        used = round(int(disk_line[2]) / 1024, 2)
        free = round(int(disk_line[3]) / 1024, 2)
        percent = round(float(disk_line[4][:-1]), 2)

        return DiskUsage(**{
            'total_gb': total,
            'used_gb': used,
            'free_gb': free,
            'percent': percent
        })
    except Exception as e:
        print('An exception occurred while getting disk usage information: {e}')
        raise


def get_nodeos_status():
    try:
        ps_out = subprocess.check_output(['ps', 'aux']).decode('utf-8')
        nodeos_ps = [line for line in ps_out.split('\n') if 'nodeos' in line and 'grep' not in line]
        process_count = len(nodeos_ps)
        if process_count > 0:
            return 'is running.'
        else:
            return 'is NOT running.'
    except subprocess.CalledProcessError:
        print('Unable to check nodeos status.')
        raise


def get_network_status():
    try:
        st = speedtest.Speedtest()
        st.get_best_server()
        ping = st.results.ping
        download = st.download()
        upload = st.upload()
        if ping:
            return Network(**{
                'ping': round(ping, 2),
                'down': round(download / 1024 / 1024, 2),
                'up': round(upload / 1024 / 1024, 2),
                'updated_at': get_timestamp_utcnow() 
            })
    except Exception as e:
        print(f"Couldn't retrieve network stats, an exception occurred: {e}")
        return Network(**{'updated_at': 'an error occurred.'})


async def get_system_info():
    return System(**{
        'cpu_load': get_cpu_load(),
        'ram_usage': get_ram_usage(),
        'disk_usage': get_disk_usage(),
        'nodeos_status': get_nodeos_status(),
        'updated_at': get_timestamp_utcnow()
    })


def get_payment(cleos: CLEOS, producer_name: str):
    payment_status = cleos.get_table(
        account='eosio',
        scope='eosio',
        table='payments',
        limit=10000
    )
    payment = '0.0000 TLOS'
    if [item for item in payment_status if item['bp'] == producer_name] != []:
        payment = [item for item in payment_status if item['bp'] == producer_name][0].get('pay')
    return payment


def get_producer_status(
        cleos: CLEOS,
        producer_name: str,
        missed_bpr_cache: int
):
    producer_status = cleos.get_table(
        account='eosio',
        scope='eosio',
        table='producers',
        limit=1,
        upper_bound=producer_name,
        lower_bound=producer_name
    )
    total_votes = 0
    if int(float(producer_status[0].get('total_votes'))) > 0:
        total_votes =  int(float(producer_status[0].get('total_votes'))) / 10000

    bp_status = BlockProducer(**{
        'owner': producer_status[0].get('owner'),
        'is_active': producer_status[0].get('is_active'),
        'total_votes': total_votes,
        'lifetime_produced_blocks': int(producer_status[0].get('lifetime_produced_blocks')),
        'lifetime_missed_blocks': int(producer_status[0].get('lifetime_missed_blocks')),
        'missed_blocks_per_rotation': int(producer_status[0].get('missed_blocks_per_rotation')),
        'unpaid_blocks': int(producer_status[0].get('unpaid_blocks')),
        'payment': get_payment(cleos, producer_name),
    })

    if int(bp_status.missed_blocks_per_rotation) > missed_bpr_cache:
        missed_bpr_cache = bp_status.missed_blocks_per_rotation
        bp_status.alert = True
    elif int(bp_status.missed_blocks_per_rotation) == 0 and missed_bpr_cache > 0:
        missed_bpr_cache = 0

    return bp_status, missed_bpr_cache


def get_abi(cleos: CLEOS, abi_path: str):
    abi = cleos.get_abi('eosio')
    with open(abi_path, 'w') as file:
        json.dump(abi, file, indent=4)
    cleos.load_abi('eosio', abi)


def get_timestamp_utcnow():
    return datetime.utcnow().strftime('%H:%M:%S')


def get_ntp_time(client: NTPClient):
    try:
        response = client.request('pool.ntp.org')
        return response.tx_time
    except Exception as e:
        print(f"Failed to get NTP time: {e}")
        return None


def get_clock_offset(client: NTPClient):
    ntp_time = get_ntp_time(client)
    import time
    while ntp_time is None:
        ntp_time = get_ntp_time(client)
    system_time = time.time()
    clock_offset = system_time - ntp_time
    if clock_offset < 0.3:
        return 'Synced'
    else:
        return 'Desynced'


def get_config(filename: str):
    cfg = ConfigParser()
    cfg.read(filename)
    try:
        return Config(**dict(cfg['config']))
    except KeyError as err:
        print(f"Config exception: {err=}, {type(err)=}")
        raise


async def call_with_retry(
    call, *args, **kwargs
):
    '''Attempts to run the same call 3 times, and caches the exception
    if it runs out of tries raises, usefull for network functions to
    discard unrelated network errors to the query at hand
    '''
    ex = None
    for i in range(3):
        try:
            return await call(*args, **kwargs)

        except BaseException as e:
            ex = e

    raise ex


async def get_all_producers(url: str):
    producers = []
    lower = 0
    while len(producers) < 42:
        response = await call_with_retry(
            asks.post,
            f'{url}/v1/chain/get_table_rows',
            json={
                'json': 'true',
                'code': 'eosio',
                'scope': 'eosio',
                'table': 'producers',
                'index_position': 2,
                'key_type': 'float64',
                'lower': lower,
                'limit': 42
            }
        )
        response = response.json()

        producers += response['rows']

        lower = response['rows'][0]['total_votes']

    return producers


def get_neighbors(producers: list, producer_name: str):
    for index in range(1, len(producers)):
        if producers[index].get('owner') == producer_name:
            active = True
            prev_bp = producers[index - 1].get('owner') 
            next_bp = producers[index + 1].get('owner')
            return active, prev_bp, next_bp
    return False, None, None


async def get_rotation(cleos: CLEOS, config: dict):
    active, prev_bp, next_bp = get_neighbors(await get_all_producers(config.node_url), config.producer_name)
    return Rotation(**{
        'active': active,
        'prev_bp': prev_bp,
        'next_bp':next_bp
    })


async def get_rank(cleos: CLEOS, config: dict):
    producers = await get_all_producers(config.node_url)
    return next((i for i, d in enumerate(producers) if d.get('owner') == config.producer_name), -1) + 1


def sleep_delta(elapse_time, resource):
    if resource == 'network':
        sleep_time = 3600 - elapse_time
    else:
        sleep_time = 1
    return max(sleep_time, 1)


def health_threshold(value):
    if float(value) >= 80:
        return True
    else:
        return False


def nodeos_failed(status: str):
    if status != 'is running.':
        return True
    else:
        return False


async def health_check(cache: Cache):
    cache.alert = False
    if (health_threshold(float(cache.system.cpu_load.min_5 * 100) / 5) or
        health_threshold(cache.system.ram_usage.percent) or
        health_threshold(cache.system.disk_usage.percent) or
        nodeos_failed(cache.system.nodeos_status)
    ):
        cache.alert = True
    return cache



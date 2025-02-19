import os
import json
import time
import struct
import locale
import msgspec
import asyncio
import speedtest
import subprocess
from typing import Optional
from ntplib import NTPClient
from time import ctime, time
from leap.cleos import CLEOS
from datetime import datetime
from configparser import ConfigParser
from telebot.async_telebot import ExceptionHandler


class CustomExceptionHandler(ExceptionHandler):
    """A custom exception handler for telebot."""
    async def handle(self, exception):
        print(f"An exception occurred: {exception}")

class Config(msgspec.Struct):
    """A struct describing the config."""
    abi_path: str
    bot_token: str
    chat_id: str
    claimer_permission: str
    claimer_private_key: str
    location: str
    node_url: str
    local_node_url: str
    producer_name: str
    producer_public_key: str
    producer_url: str
    register_permission: str
    register_private_key: str
    users_alerted: str

class CpuLoad(msgspec.Struct, frozen=True):
    """A struct describing the cpu loads."""
    min_1: float = 0
    min_5: float = 0
    min_15: float = 0

class RamUsage(msgspec.Struct, frozen=True):
    """A struct describing the ram usage."""
    total_gb: float  = 0
    used_gb: float = 0
    free_gb: float = 0
    available_gb: float = 0
    percent: float = 0

class DiskUsage(msgspec.Struct, frozen=True):
    """A struct describing the disk usage."""
    total_gb: float  = 0
    used_gb: float = 0
    free_gb: float = 0
    percent: float = 0

class System(msgspec.Struct, frozen=True):
    """A struct describing the system."""
    cpu_load: CpuLoad = CpuLoad()
    ram_usage: RamUsage = RamUsage()
    disk_usage: DiskUsage = DiskUsage()
    nodeos_status: str = 'Waitting...'
    updated_at: str = 'Waitting...'

class Network(msgspec.Struct, frozen=True):
    """A struct describing the network."""
    ping: Optional[float] = 0
    down: Optional[float] = 0
    up: Optional[float] = 0
    updated_at: str = 'Waitting...'

class Cache(msgspec.Struct):
    """A struct describing the cache."""
    system: System = System()
    network: Network = Network()
    alert: bool = False

class BlockProducer(msgspec.Struct):
    """A struct describing the block producer."""
    owner: str
    is_active: int
    total_votes: int
    lifetime_produced_blocks: int
    lifetime_missed_blocks: int
    missed_blocks_per_rotation: int
    unpaid_blocks: int
    payment: int
    alert: bool = False

class Rotation(msgspec.Struct):
    """A struct describing the block producer rotation."""
    active: bool
    prev_bp: Optional[str] = None
    next_bp: Optional[str] = None

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

def get_producer_status(cleos: CLEOS, producer_name: str, missed_bpr_cache: int):
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

    message = BlockProducer(**{
        'owner': producer_status[0].get('owner'),
        'is_active': producer_status[0].get('is_active'),
        'total_votes': total_votes,
        'lifetime_produced_blocks': int(producer_status[0].get('lifetime_produced_blocks')),
        'lifetime_missed_blocks': int(producer_status[0].get('lifetime_missed_blocks')),
        'missed_blocks_per_rotation': int(producer_status[0].get('missed_blocks_per_rotation')),
        'unpaid_blocks': int(producer_status[0].get('unpaid_blocks')),
        'payment': get_payment(cleos, producer_name),
    })
    if int(message.missed_blocks_per_rotation) > missed_bpr_cache:
        missed_bpr_cache = message.missed_blocks_per_rotation
        message.alert = True
    elif int(message.missed_blocks_per_rotation) == 0 and missed_bpr_cache > 0:
        missed_bpr_cache = 0
    return message, missed_bpr_cache

async def build_producer_status_message(
        cleos: CLEOS,
        cleos_local: CLEOS,
        ntp_client: NTPClient,
        cache_data: Cache,
        producer_name: str,
        users_alerted: str | None,
        missed_bpr_cache: int
    ):

    sys_health_check = await health_check(cache_data)
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8') 
    locale.setlocale(locale.LC_NUMERIC, 'en_US.UTF-8')

    system_stats = sys_health_check.system
    cpu_load = system_stats.cpu_load
    ram_usage = system_stats.ram_usage.percent
    disk_usage = system_stats.disk_usage.percent
    nodeos_status = system_stats.nodeos_status

    bp_status, new_missed_bpr_cache = get_producer_status(cleos, producer_name, missed_bpr_cache)
    total_votes = formatting(bp_status.total_votes)
    lifetime_produced_blocks = formatting(bp_status.lifetime_produced_blocks)
    lifetime_missed_blocks = formatting(bp_status.lifetime_missed_blocks)
    missed_blocks_per_rotation = formatting(bp_status.missed_blocks_per_rotation)
    unpaid_blocks = formatting(bp_status.unpaid_blocks)

    network_stats = sys_health_check.network
    ping = network_stats.ping
    down = formatting(network_stats.down)
    up = formatting(network_stats.up)
    network_updated_at = network_stats.updated_at

    clock_offset = get_clock_offset(ntp_client)

    accuracy = 0
    if bp_status.lifetime_produced_blocks > 0:
        accuracy = round(100 - ((bp_status.lifetime_missed_blocks * 100) / bp_status.lifetime_produced_blocks), 6)

    rotation_message = get_rotation_message(get_rotation(cleos_local, producer_name))

    system_message = (
        f"<b><u>System Information:</u></b>\n"
        f"{format_fixed_width('Clock:', f'{clock_offset}', 9, 33)}\n"
        f"{format_fixed_width('CPU Load:', f'[ {cpu_load.min_1} {cpu_load.min_5} {cpu_load.min_15} ]', 9, 26)}\n"
        f"{format_fixed_width('RAM Usage:', f'{ram_usage} %', 10, 26)}\n"
        f"{format_fixed_width('Disk Usage:', f'{disk_usage} %', 11, 28)}\n"
        f"{format_fixed_width('Nodeos:', f'{nodeos_status}', 7, 28)}\n"
    )

    network_message = (
        f"<b><u>Network Information:</u></b>\n"
        f"{format_fixed_width('Ping:', f'{ping} ms', 14, 29)}\n"
        f"{format_fixed_width('Down:', f'{down} Mbps', 11, 29)}\n"
        f"{format_fixed_width('Up:', f'{up} Mbps', 14, 29)}\n"
        f"{format_fixed_width('Updated at:', network_updated_at, 11, 26)}\n"
    )

    bp_status_message = (
        f"<b><u>BP Stats:</u></b>\n"
        f"{format_fixed_width('Is active:', f'{bp_status.is_active}', 23, 24)}\n"
        f"{format_fixed_width('Total votes:', f'{total_votes}', 12, 24)}\n"
        f"{format_fixed_width('Produced blocks:', f'{str(lifetime_produced_blocks)}', 16, 17)}\n"
        f"{format_fixed_width('Missed blocks:', f'{lifetime_missed_blocks}', 16, 22)}\n"
        f"{format_fixed_width('Missed bpr:', f'{missed_blocks_per_rotation}', 16, 27)}\n"
        f"{format_fixed_width('Unpaid blocks:', f'{unpaid_blocks}', 16, 23)}\n"
        f"{format_fixed_width('Payment:', f'{bp_status.payment}', 8, 22)}\n"
        f"{format_fixed_width('Accuracy:', f'{accuracy} %', 10, 23)}\n"
    )

    response = (
        f"{system_message}\n"
        f"{network_message}\n"
        f"{bp_status_message}\n"
        f"{rotation_message}\n"
    )
    if clock_offset != 'Synced' or bp_status.alert or sys_health_check.alert:
        response += build_tags(users_alerted)
        return response, new_missed_bpr_cache
    response += f"\n{green_check_mark_emoji}"
    return response, new_missed_bpr_cache

def build_help_message():
    return (
        f"<b><u>Sauron Bot:</u></b>\n"
        #f"{format_fixed_width('<i>/c</i>', '<i>Claim rewards.</i>')}\n"
        f"{format_fixed_width('<i>/h</i>', '<i>Display this help message.</i>')}\n"
        f"{format_fixed_width('<i>/r</i>', '<i>Register block producer.</i>')}\n"
        f"{format_fixed_width('<i>/u</i>', '<i>Unregister block producer.</i>')}\n"
        f"{format_fixed_width('<i>/s</i>', '<i>Server and bp status.</i>')}\n"
        f"{format_fixed_width('<i>/schedule</i>', '<i>BP Schedule.</i>')}\n"
    )

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
    while ntp_time is None:
        ntp_time = get_ntp_time(client)
    system_time = time()
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

def get_producers(producers: list, producer_name: str):
    for index in range(1, len(producers)):
        if producers[index].get('producer_name') == producer_name:
            active = True
            prev_bp = producers[index - 1].get('producer_name') 
            next_bp = producers[index + 1].get('producer_name')
            return active, prev_bp, next_bp
    return False, None, None

def get_schedule_message(schedule: list, producer_name):
    msg = f'<b><u>Schedule:</u></b>\n'
    for bp in range(0, len(schedule)):
        if schedule[bp] == producer_name:
            msg += f"<code>{bp + 1} - </code><b>{schedule[bp]}</b> {rocket_emoji}\n"
            continue
        msg += f"<code>{bp + 1} - {schedule[bp]}</code>\n"
    return msg

def get_rotation(cleos: CLEOS, producer_name: str):
    active, prev_bp, next_bp = get_producers(cleos.get_schedule()['active']['producers'],
                                             producer_name)
    if active:
        return Rotation(**{
            'active': active,
            'prev_bp': prev_bp,
            'next_bp':next_bp
        })
    else:
        return Rotation(**{
            'active': active
        })

def get_rotation_message(rotation: Rotation):
    msg = (
        f'<b><u>Rotation:</u></b>\n'
        f"{format_fixed_width('On schedule:', f'{rotation.active}', 12, 26)}"
    )
    if rotation.active:
        msg += (
            f"\n{format_fixed_width('Prev:', f'{rotation.prev_bp}', 15, 26)}"
            f"\n{format_fixed_width('Next:', f'{rotation.next_bp}', 13, 26)}"
        )
    return msg
 
def format_fixed_width(key, value, key_width=15, value_width=15):
    return f"{key:<{key_width}} {value:>{value_width}}"

def sleep_delta(elapse_time, resource):
    if resource == 'network':
        sleep_time = 3600 - elapse_time
    else:
        sleep_time = 1
    return max(sleep_time, 1)

def formatting(value):
    return locale.format_string('%d', value, grouping=True)

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

def build_tags(users_alerted: str | None):
    tags = f"\n{red_alert_emoji}\n"
    if users_alerted != None:
        users = [item.strip() for item in users_alerted.split(',')]
        for user in users:
            tags += f"{user}\n"
    return tags

green_check_mark_emoji = f"<tg-emoji emoji-id='9989'>✅</tg-emoji>"
red_alert_emoji = f"<tg-emoji emoji-id='128680'>🚨</tg-emoji>"
rocket_emoji = f"<tg-emoji emoji-id='128640'>🚀</tg-emoji>"

if __name__ == "__main__":
    utils()


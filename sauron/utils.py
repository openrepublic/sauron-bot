#!/usr/bin/env python3

import locale
from ntplib import NTPClient
from leap.cleos import CLEOS
from .types import *
from .service import *


green_check_mark_emoji = f"<tg-emoji emoji-id='9989'>✅</tg-emoji>"
red_alert_emoji = f"<tg-emoji emoji-id='128680'>🚨</tg-emoji>"
rocket_emoji = f"<tg-emoji emoji-id='128640'>🚀</tg-emoji>"

async def build_producer_status_message(
        cleos: CLEOS,
        ntp_client: NTPClient,
        cache_data: Cache,
        config: dict,
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

    bp_status, new_missed_bpr_cache = get_producer_status(cleos, config.producer_name, missed_bpr_cache)
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

    rank = await get_rank(cleos, config)

    accuracy = 0
    if bp_status.lifetime_produced_blocks > 0:
        accuracy = round(100 - ((bp_status.lifetime_missed_blocks * 100) / bp_status.lifetime_produced_blocks), 6)

    rotation_message = get_rotation_message(await get_rotation(cleos, config))

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
        f"{format_fixed_width('Total votes:', f'{total_votes}', 9, 24)}\n"
        f"{format_fixed_width('Produced blocks:', f'{str(lifetime_produced_blocks)}', 9, 16)}\n"
        f"{format_fixed_width('Missed blocks:', f'{lifetime_missed_blocks}', 16, 22)}\n"
        f"{format_fixed_width('Missed bpr:', f'{missed_blocks_per_rotation}', 16, 27)}\n"
        f"{format_fixed_width('Unpaid blocks:', f'{unpaid_blocks}', 16, 23)}\n"
        f"{format_fixed_width('Payment:', f'{bp_status.payment}', 8, 22)}\n"
        f"{format_fixed_width('Accuracy:', f'{accuracy:.4f} %', 14, 23)}\n"
        f"{format_fixed_width('Ranking: ', f'{rank}', 21, 23)}\n"
    )

    response = (
        f"{system_message}\n"
        f"{network_message}\n"
        f"{bp_status_message}\n"
        f"{rotation_message}\n"
    )

    if clock_offset != 'Synced' or bp_status.alert or sys_health_check.alert:
        response += build_tags(config.users_alerted)
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


def get_schedule_message(schedule: list, producer_name):
    msg = f'<b><u>Schedule:</u></b>\n'
    for bp in range(0, len(schedule)):
        if schedule[bp] == producer_name:
            msg += f"<code>{bp + 1} - </code><b>{schedule[bp]}</b> {rocket_emoji}\n"
            continue
        msg += f"<code>{bp + 1} - {schedule[bp]}</code>\n"
    return msg


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


def formatting(value):
    return locale.format_string('%d', value, grouping=True)


def build_tags(users_alerted: str | None):
    tags = f"\n{red_alert_emoji}\n"
    if users_alerted != None:
        users = [item.strip() for item in users_alerted.split(',')]
        for user in users:
            tags += f"{user}\n"
    return tags



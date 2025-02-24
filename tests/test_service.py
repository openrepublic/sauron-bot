import pytest
import asyncio
import logging
import os
import subprocess
from unittest.mock import patch, MagicMock

import locale
from ntplib import NTPClient
from leap.cleos import CLEOS

# Import from your package
from sauron.service import (
    get_cpu_load,
    get_ram_usage,
    get_disk_usage,
    get_system_info,
    get_nodeos_status,
    get_network_status,
    get_producer_status,
    get_config,
    get_timestamp_utcnow,
    health_check,
    call_with_retry
)
from sauron.utils import (
    build_producer_status_message,
    build_help_message,
    get_schedule_message,
    get_rotation_message,
    format_fixed_width,
    formatting,
    build_tags,
    get_clock_offset
)
from sauron.types import (
    CpuLoad, RamUsage, DiskUsage, BlockProducer, Cache, Config, System, Network
)

# -------------------------------------------------------------------
# Pytest configuration
# -------------------------------------------------------------------

@pytest.fixture
def mock_config():
    return Config(**{
        'abi_path': './eosio.abi',
        'bot_token': '726_ck',
        'chat_id': '-1042',
        'claimer_permission': 'claimer',
        'claimer_private_key': '5JBk',
        'location': '2001',
        'node_url': 'https://testnet.telos.net',
        'local_node_url': 'https://testnet.telos.net',
        'producer_name': 'openrepublic',
        'producer_url': 'https://openrepublic.net',
        'producer_public_key': 'EOS5zxgsnHa27u...',
        'register_permission': 'register',
        'register_private_key': '5HwdBtW',
        'users_alerted': '@gollum',
    })

@pytest.fixture
def mock_cleos(mock_config):
    return CLEOS(endpoint=mock_config.node_url)

@pytest.fixture
def mock_ntp_client():
    return NTPClient()

@pytest.fixture
def mock_network():
    # Typical successful network stats
    return Network(**{
        'ping': 24.13,
        'down': 45.6,
        'up': 5.5,
        'updated_at': '12:00:00'
    })

@pytest.fixture
def mock_system():
    return System(**{
        'cpu_load': CpuLoad(min_1=0.5, min_5=0.3, min_15=0.2),
        'ram_usage': RamUsage(
            total_gb=16, used_gb=8, free_gb=8,
            available_gb=8, percent=50
        ),
        'disk_usage': DiskUsage(
            total_gb=200, used_gb=100, free_gb=100, percent=50
        ),
        'nodeos_status': 'is running.',
        'updated_at': '12:00:00'
    })

@pytest.fixture
def mock_cache(mock_system, mock_network):
    c = Cache()
    c.system = mock_system
    c.network = mock_network
    return c

# -------------------------------------------------------------------
# Mocks / Patches for direct system calls
# -------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_subprocess_check_output():
    '''Mock subprocess.check_output calls to prevent real system commands.'''
    df_cmd_output = (
        'Filesystem 1B-blocks Used Available Use% Mounted on\n' \
                              '/dev/sda1 1000000 500000 500000 50% /'
    )
    with patch('subprocess.check_output', return_value=df_cmd_output.encode('utf-8')) as mocked:
        # Default mock return for df/free
        mocked.return_value = 'Filesystem 1B-blocks Used Available Use% Mounted on\n' \
                              '/dev/sda1 1000000 500000 500000 50% /'
        yield mocked

@pytest.fixture
def mock_speedtest():
    '''Mock speedtest.Speedtest so get_network_status does not call real network.'''
    with patch('speedtest.Speedtest') as mock_st:
        instance = mock_st.return_value
        instance.get_best_server.return_value = {}
        instance.results.ping = 23.45
        instance.download.return_value = 12_345_678  # ~ 12 Mbps
        instance.upload.return_value = 1_234_567     # ~ 1 Mbps
        yield mock_st

@pytest.fixture
def mock_ntp():
    '''Mock NTP calls so get_ntp_time returns a consistent value.'''
    with patch('sauron.service.NTPClient.request') as mock_request:
        mock_request.return_value.tx_time = 1670000000.0
        yield mock_request

# -------------------------------------------------------------------
# Service functionality tests
# -------------------------------------------------------------------

def test_get_cpu_load():
    with patch('os.getloadavg') as mock_loadavg:
        mock_loadavg.return_value = (1.5, 2.0, 2.5)
        cpu = get_cpu_load()
        assert cpu.min_1 == 1.5
        assert cpu.min_5 == 2.0
        assert cpu.min_15 == 2.5

def test_get_ram_usage():
    # We can mock 'free -m' command
    ram_cmd_output = (
        '              total        used        free      shared  buff/cache   available\n'
        'Mem:          16384        8192        4096         500        4096        7000\n'
        'Swap:          2048        1024        1024\n'
    )
    with patch('subprocess.check_output', return_value=ram_cmd_output.encode('utf-8')):
        ram = get_ram_usage()
        assert ram.percent > 0
        assert ram.total_gb == 16.0
        assert ram.used_gb == 8.0
        assert ram.free_gb == 4.0
        # etc. as needed

def test_get_disk_usage():
    # We can mock 'df -m /' command
    df_cmd_output = (
        'Filesystem     1M-blocks   Used Available Use% Mounted on\n'
        '/dev/sda1           20000  10000     10000  50% /'
    )
    with patch('subprocess.check_output', return_value=df_cmd_output.encode('utf-8')):
        disk = get_disk_usage()
        assert disk.percent == 50
        assert disk.used_gb == 9.77 or disk.used_gb == 9.76  # rounding depends
        # etc.

def test_get_nodeos_status():
    # Return ps output that includes 'nodeos'
    ps_output = 'root      1234  0.0  ... nodeos\n'
    with patch('subprocess.check_output', return_value=ps_output.encode('utf-8')):
        status = get_nodeos_status()
        assert status == 'is running.'

    # Now simulate no nodeos
    ps_output = 'root      1234  0.0  ... random\n'
    with patch('subprocess.check_output', return_value=ps_output.encode('utf-8')):
        status = get_nodeos_status()
        assert status == 'is NOT running.'

@pytest.mark.asyncio
async def test_call_with_retry():
    async def _fail_once():
        if not hasattr(_fail_once, 'tried'):
            _fail_once.tried = True
            raise ValueError('Simulated error')
        return 'success'

    result = await call_with_retry(_fail_once)
    assert result == 'success'

# -------------------------------------------------------------------
# BP Status + build_producer_status_message tests
# (similar to your existing 'test_status_message.py' but with expansions)
# -------------------------------------------------------------------

@pytest.mark.asyncio
async def test_block_producer_status_message_ok(
    mock_cleos, mock_ntp_client, mock_cache, mock_config
):
    mock_cleos.get_table = MagicMock(side_effect=[
        [
            {
                'owner': 'openrepublic',
                'is_active': True,
                'total_votes': '100000',
                'lifetime_produced_blocks': 10000,
                'lifetime_missed_blocks': 0,
                'missed_blocks_per_rotation': 0,
                'unpaid_blocks': 50
            }
        ],  # first call => producers table
        [
            {
                'bp': 'openrepublic',
                'pay': '100.0000 TLOS'
            }
        ]   # second call => payments table
    ])

    missed_bpr_cache = 0

    bp_status, missed_bpr_cache = get_producer_status(
        mock_cleos,
        mock_config.producer_name,
        missed_bpr_cache
    )

    # Build the status message
    message = await build_producer_status_message(
        mock_cleos,
        mock_ntp_client,
        bp_status,
        mock_cache,
        mock_config,
    )
    assert not bp_status.alert
    assert 'System Information' in message
    assert 'BP Stats:' in message


@pytest.mark.asyncio
async def test_missed_block_reset_status_message_ok(
    mock_cleos, mock_ntp_client, mock_cache, mock_config
):
    mock_cleos.get_table = MagicMock(side_effect=[
        [
            {
                'owner': 'openrepublic',
                'is_active': True,
                'total_votes': '100000',
                'lifetime_produced_blocks': 10000,
                'lifetime_missed_blocks': 0,
                'missed_blocks_per_rotation': 0,
                'unpaid_blocks': 50
            }
        ],  # first call => producers table
        [
            {
                'bp': 'openrepublic',
                'pay': '100.0000 TLOS'
            }
        ]   # second call => payments table
    ])

    missed_bpr_cache = 10

    bp_status, missed_bpr_cache = get_producer_status(
        mock_cleos,
        mock_config.producer_name,
        missed_bpr_cache
    )

    message = await build_producer_status_message(
        mock_cleos,
        mock_ntp_client,
        bp_status,
        mock_cache,
        mock_config,
    )
    assert not bp_status.alert

@pytest.mark.asyncio
async def test_missed_block_status_message_alert(
    mock_cleos,
    mock_ntp_client,
    mock_cache,
    mock_config,
):

    missed_bpr_cache = 0

    mock_cleos.get_table = MagicMock(side_effect=[
        [
            {
                'owner': 'openrepublic',
                'is_active': True,
                'total_votes': '100000',
                'lifetime_produced_blocks': 10000,
                'lifetime_missed_blocks': 0,
                'missed_blocks_per_rotation': 10,
                'unpaid_blocks': 50
            }
        ],  # first call => producers table
        [
            {
                'bp': 'openrepublic',
                'pay': '100.0000 TLOS'
            }
        ]   # second call => payments table
    ])

    bp_status, missed_bpr_cache = get_producer_status(
        mock_cleos,
        mock_config.producer_name,
        missed_bpr_cache
    )

    message = await build_producer_status_message(
        mock_cleos,
        mock_ntp_client,
        bp_status,
        mock_cache,
        mock_config,
    )
    assert bp_status.alert

@pytest.mark.asyncio
@patch('sauron.service.get_cpu_load')
@patch('sauron.service.get_ram_usage')
@patch('sauron.service.get_disk_usage')
@patch('sauron.service.get_nodeos_status')
async def test_cpu_overload_status_message_alert(
    mock_get_nodeos_status,
    mock_get_disk_usage,
    mock_get_ram_usage,
    mock_get_cpu_load,
    mock_cleos,
    mock_ntp_client,
    mock_cache,
    mock_config,
):
    # CPU overload threshold
    mock_get_cpu_load.return_value = CpuLoad(
        min_1=4.0,
        min_5=4.0,
        min_15=4.0
    )

    mock_get_ram_usage.return_value = RamUsage(
        total_gb=16,
        used_gb=4,
        free_gb=12,
        available_gb=12,
        percent=25
    )

    mock_get_disk_usage.return_value = DiskUsage(
        total_gb=500,
        used_gb=250,
        free_gb=250,
        percent=50
    )

    mock_get_nodeos_status.return_value = 'is running.'

    mock_cleos.get_table = MagicMock(side_effect=[
        [
            {
                'owner': 'openrepublic',
                'is_active': True,
                'total_votes': '100000',
                'lifetime_produced_blocks': 10000,
                'lifetime_missed_blocks': 0,
                'missed_blocks_per_rotation': 0,
                'unpaid_blocks': 50
            }
        ],  # first call => producers table
        [
            {
                'bp': 'openrepublic',
                'pay': '100.0000 TLOS'
            }
        ]   # second call => payments table
    ])

    missed_bpr_cache = 0

    mock_cache.system = await get_system_info()

    bp_status, missed_bpr_cache = get_producer_status(
        mock_cleos,
        mock_config.producer_name,
        missed_bpr_cache
    )

    message = await build_producer_status_message(
        mock_cleos,
        mock_ntp_client,
        bp_status,
        mock_cache,
        mock_config,
    )
    assert mock_cache.alert

@pytest.mark.asyncio
@patch('sauron.service.get_cpu_load')
@patch('sauron.service.get_ram_usage')
@patch('sauron.service.get_disk_usage')
@patch('sauron.service.get_nodeos_status')
async def test_ram_overload_status_message_alert(
    mock_get_nodeos_status,
    mock_get_disk_usage,
    mock_get_ram_usage,
    mock_get_cpu_load,
    mock_cleos,
    mock_ntp_client,
    mock_cache,
    mock_config,
):
    mock_get_cpu_load.return_value = CpuLoad(
        min_1=1.0,
        min_5=1.0,
        min_15=1.0
    )

    # RAM usage overload threshold
    mock_get_ram_usage.return_value = RamUsage(
        total_gb=16,
        used_gb=4,
        free_gb=12,
        available_gb=12,
        percent=80
    )

    mock_get_disk_usage.return_value = DiskUsage(
        total_gb=500,
        used_gb=250,
        free_gb=250,
        percent=50
    )

    mock_get_nodeos_status.return_value = 'is running.'

    missed_bpr_cache = 0

    mock_cache.system = await get_system_info()

    bp_status, missed_bpr_cache = get_producer_status(
        mock_cleos,
        mock_config.producer_name,
        missed_bpr_cache
    )

    message = await build_producer_status_message(
        mock_cleos,
        mock_ntp_client,
        bp_status,
        mock_cache,
        mock_config,
    )
    assert mock_cache.alert

@pytest.mark.asyncio
@patch('sauron.service.get_cpu_load')
@patch('sauron.service.get_ram_usage')
@patch('sauron.service.get_disk_usage')
@patch('sauron.service.get_nodeos_status')
async def test_disk_almost_full_status_message_alert(
    mock_get_nodeos_status,
    mock_get_disk_usage,
    mock_get_ram_usage,
    mock_get_cpu_load,
    mock_cleos,
    mock_ntp_client,
    mock_cache,
    mock_config,
):
    mock_get_cpu_load.return_value = CpuLoad(
        min_1=1.0,
        min_5=1.0,
        min_15=1.0
    )

    mock_get_ram_usage.return_value = RamUsage(
        total_gb=16,
        used_gb=4,
        free_gb=12,
        available_gb=12,
        percent=25
    )

    # Disk usage overload threshold
    mock_get_disk_usage.return_value = DiskUsage(
        total_gb=500,
        used_gb=250,
        free_gb=250,
        percent=80
    )

    mock_get_nodeos_status.return_value = 'is running.'

    missed_bpr_cache = 0

    mock_cache.system = await get_system_info()

    bp_status, missed_bpr_cache = get_producer_status(
        mock_cleos,
        mock_config.producer_name,
        missed_bpr_cache
    )

    message = await build_producer_status_message(
        mock_cleos,
        mock_ntp_client,
        bp_status,
        mock_cache,
        mock_config,
    )
    assert mock_cache.alert

@pytest.mark.asyncio
@patch('sauron.service.get_cpu_load')
@patch('sauron.service.get_ram_usage')
@patch('sauron.service.get_disk_usage')
@patch('sauron.service.get_nodeos_status')
async def test_nodeos_not_running_status_message_alert(
    mock_get_nodeos_status,
    mock_get_disk_usage,
    mock_get_ram_usage,
    mock_get_cpu_load,
    mock_cleos,
    mock_ntp_client,
    mock_cache,
    mock_config,
):

    mock_get_cpu_load.return_value = CpuLoad(
        min_1=1.0,
        min_5=1.0,
        min_15=1.0
    )

    mock_get_ram_usage.return_value = RamUsage(
        total_gb=16,
        used_gb=4,
        free_gb=12,
        available_gb=12,
        percent=25
    )

    # Disk usage overload threshold
    mock_get_disk_usage.return_value = DiskUsage(
        total_gb=500,
        used_gb=250,
        free_gb=250,
        percent=20
    )

    mock_get_nodeos_status.return_value = 'is NOT running.'

    missed_bpr_cache = 0

    mock_cache.system = await get_system_info()

    bp_status, missed_bpr_cache = get_producer_status(
        mock_cleos,
        mock_config.producer_name,
        missed_bpr_cache
    )

    message = await build_producer_status_message(
        mock_cleos,
        mock_ntp_client,
        bp_status,
        mock_cache,
        mock_config,
    )
    assert mock_cache.alert

# -------------------------------------------------------------------
# Utils tests
# -------------------------------------------------------------------

def test_build_help_message():
    msg = build_help_message()
    assert '/h' in msg
    assert '/r' in msg
    assert '/u' in msg
    assert '/s' in msg
    assert '/schedule' in msg

def test_get_schedule_message():
    schedule = ['bp1', 'bp2', 'openrepublic', 'bp4']
    msg = get_schedule_message(schedule, 'openrepublic')
    assert 'openrepublic' in msg
    assert 'Schedule:' in msg

def test_get_rotation_message():
    from sauron.types import Rotation

    rotation = Rotation(active=True, prev_bp='bp1', next_bp='bp2')
    msg = get_rotation_message(rotation)
    assert 'bp1' in msg
    assert 'bp2' in msg
    assert 'active' not in msg  # we only show 'On schedule:' line
    assert 'On schedule:' in msg

def test_format_fixed_width():
    line = format_fixed_width('CPU:', '4.0', 10, 6)
    assert line.startswith('CPU:')
    assert '4.0' in line

def test_formatting():
    val = formatting(123456789)
    # locale.format_string returns a string with grouping
    # e.g. '123,456,789' in en_US
    assert ',' in val

def test_build_tags():
    tags = build_tags('@user1,@user2')
    assert '@user1' in tags
    assert '@user2' in tags

def test_get_clock_offset(mock_ntp):
    client = NTPClient()
    offset = get_clock_offset(client)
    # If system_time - 1670000000.0 < 0.3 => 'Synced'
    # This depends on local time. For test, we just confirm it returns a string
    assert offset in ['Synced', 'Desynced']


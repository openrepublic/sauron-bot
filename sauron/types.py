#!/usr/bin/env python3

import msgspec
from typing import Optional
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



# Sauron Bot

Sauron is a monitoring bot that integrates with Telegram and EOSIO blockchain to manage and monitor the health of a system. It uses `telebot` for Telegram integration and `py-leap` for EOSIO interactions.

## Features

- Check system health.
- Registers and unregisters a block producer on the EOSIO blockchain.
- List current block producer schedule on the EOSIO blockchain.

## Installation

To run the Sauron Bot, you need Python 3.12 installed. run this command:

    uv lock

## Nixos Installation

    nix-shell

## Usage

Create a configuration file `config/config.ini` (an example is provided as `config/config.ini.example`).

To complete the `config.ini` file you need a `bot_token` and a `chat_id`, take a look at the [Telegram bot documentation](https://core.telegram.org/bots/tutorial).


    uv run python src/telegram_bot.py config/config.ini


This will load the default values specified in `config/config.ini`, reducing the need to specify each option on the command line.

The bot uses `src/utils.py` to gather system health data. It checks:

## System Information

- **Clock offset**: NTP offset.
- **CPU load**:     1min, 5min, 15min.
- **RAM usage**:    Ram percentage used.
- **Disk usage**:   Disk percentage used.
- **Nodeos**:       Check that nodeos process is running.

## Network Information

- **Ping**:       Ping time in ms.
- **Down**:       Down speed in Mbps.
- **Up**:         Up speed in Mbps.
- **Updated at**: Last update utc time.

### Block Producer Stats

- **Active Status**:            Whether the block producer is active (0 or 1).
- **Total Votes**:              The total number of votes received by the block producer.
- **Lifetime Produced Blocks**: The total number of blocks produced by the block producer over its lifetime.
- **Lifetime Missed Blocks**:   The total number of blocks missed by the block producer over its lifetime.
- **Missed BPR**:               The number of blocks missed by the block producer in the current rotation.
- **Unpaid Blocks**:            The number of unpaid blocks produced.
- **Payment**:                  The payment received by the block producer.
- **Accuracy**:                 Percentage for lifetime produced blocks vs lifetime missed blocks.

## Rotation

- **On schedule**: True or False.
- **Prev**:        Previous bp in rotation.
- **Next**:        Next bp in rotation.

The health information is sent to the specified Telegram chat every minute.

## Commands

- **/h**:        Display this help message.
- **/r**:        Register block producer.
- **/u**:        Unregister block producer.
- **/s**:        Server and bp status.
- **/schedule**: BP Schedule.


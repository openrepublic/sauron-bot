#!/bash

uv lock

nohup uv run sauron telegram config.ini >> /var/log/monitor/sauron_bot.log 2>&1 &

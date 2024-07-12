import os
import subprocess
import json
from datetime import datetime

def get_cpu_load():
    # Run 'uptime' command to get load average values
    load1, load5, load15 = os.getloadavg() 
    return {
        '1_min_avg': load1,
        '5_min_avg': load5,
        '15_min_avg': load15
    }

def get_ram_usage():
    # Run 'free' command to get RAM usage
    free_output = subprocess.check_output(['free', '-m']).decode('utf-8')
    lines = free_output.split('\n')
    mem_line = lines[1].split()

    total = round(int(mem_line[1]) / 1024, 2)
    used = round(int(mem_line[2]) / 1024, 2)
    free = round(int(mem_line[3]) / 1024, 2)
    available = round(int(mem_line[6]) / 1024, 2)
    percent = round((used / total) * 100, 2)

    return {
        'total_gb': total,
        'used_gb': used,
        'free_gb': free,
        'available_gb': available,
        'percent': percent
    }

def get_disk_usage():
    # Run 'df' command to get disk usage
    df_output = subprocess.check_output(['df', '-m', '/']).decode('utf-8')
    lines = df_output.split('\n')
    disk_line = lines[1].split()

    total = round(int(disk_line[1]) / 1024, 2)
    used = round(int(disk_line[2]) / 1024, 2)
    free = round(int(disk_line[3]) / 1024, 2)
    percent = round(float(disk_line[4][:-1]), 2)

    return {
        'total_gb': total,
        'used_gb': used,
        'free_gb': free,
        'percent': percent
    }

def get_current_users():
    # Run 'who' command to get current logged in users
    who_output = subprocess.check_output(['who']).decode('utf-8')
    users = who_output.strip().split('\n')
    return users

def get_failed_login_attempts():
    # Run 'lastb' command to get failed login attempts
    try:
        lastb_output = subprocess.check_output(['lastb']).decode('utf-8')
        failed_attempts = lastb_output.strip().split('\n')
        return len(failed_attempts) - 1  # Exclude header line
    except subprocess.CalledProcessError:
        return "Unable to retrieve failed login attempts"

def get_ufw_status():
    # Run ufw command to get firewall status
    try:
        ufw_output = subprocess.check_output(['ufw', 'status']).decode('utf-8')
        return ufw_output.strip().split('\n')[0].split(': ')[1]
    except subprocess.CalledProcessError:
        return "Unable to retrieve firewall status, called process error."
    except OSError:
        return "Unable to retrieve firewall status, priviliges required."

def check_nodeos_status():
    # Check if nodeos is running and its health
    try:
        nodeos_output = subprocess.check_output(['ps', 'aux']).decode('utf-8')
        nodeos_processes = [line for line in nodeos_output.split('\n') if 'nodeos' in line and 'grep' not in line]
        process_count = len(nodeos_processes)

        nodeos_details = []
        for process in nodeos_processes:
            parts = process.split(None, 10)  # Split the output with a maximum of 10 splits
            if len(parts) == 11:
                nodeos_details.append({
                    'user': parts[0],
                    'pid': parts[1],
                    'cpu_percent': parts[2],
                    'mem_percent': parts[3],
                    'vsz': parts[4],
                    'rss': parts[5],
                    'tty': parts[6],
                    'stat': parts[7],
                    'start': parts[8],
                    'time': parts[9],
                    'command': parts[10]
                })

        if process_count == 3:
            return {
                'status': "nodeos is running with 3 processes",
                'processes': nodeos_details
            }
        else:
            return {
                'status': f"nodeos is running, expected 3 processes but found {process_count}",
                'processes': nodeos_details
            }
    except subprocess.CalledProcessError:
        return "Unable to check nodeos status"

def get_system_info():
    system_info = {
        'cpu_load': get_cpu_load(),
        'ram_usage': get_ram_usage(),
        'disk_usage': get_disk_usage(),
        'current_users': get_current_users(),
        'nodeos_status': check_nodeos_status()
    }
    return system_info

def health_threshold(value):
    if float(value) >= 60:
        return True
    else:
        return False

def parse_user_names(user_list):
    if user_list:
        user_names = [user.split()[0] for user in user_list]
        return ', '.join(user_names)
    else:
        return 'no users'

def health_check():
    json_file = get_system_info()
    current_users = parse_user_names(json_file["current_users"])
    message = (
            f"CPU Usage: {json_file['cpu_load'].get('1_min_avg')}\n"
            f"RAM Usage: {json_file['ram_usage'].get('percent')} %\n"
            f"Disk Usage: {json_file['disk_usage'].get('percent')} %\n"
            f"Nodeos Status: {json_file['nodeos_status'].get('status')}\n"
    )
    if (
        health_threshold(json_file["cpu_load"].get("5_min_avg")) or
        health_threshold(json_file["ram_usage"].get("percent")) or
        health_threshold(json_file["disk_usage"].get("percent"))
    ):
        message = message + f"\n@torresnelson1 Alert!"

        return message
        print("Alert sent... ", subprocess.check_output('/usr/bin/date', shell=True).decode().strip())
    else:
        return message

if __name__ == "__main__":
    sys_info()


import requests 
import json 
from si_prefix import si_format
from datetime import datetime
from urllib3.exceptions import InsecureRequestWarning
from os import getenv
from dotenv import load_dotenv

load_dotenv()

# Suppress only the single warning from urllib3 needed.
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

active_validator_host = getenv('ACTIVE_VALIDATOR_HOST', '127.0.0.1')
backup_validator_host = getenv('BACKUP_VALIDATOR_HOST', '127.0.1.1')

validator_address = getenv('VALIDATOR_ADDRESS', 'rv1...')

last_validator_info_file = getenv('LAST_VALIDATOR_INFO_FILE', 'last_validator_info.txt')

print(f'[{now}] active validator host: {active_validator_host}')
print(f'[{now}] backup validator host: {backup_validator_host}')
print(f'[{now}] validator address: {validator_address}')
print(f'[{now}] last validator info file: {last_validator_info_file}')

def send_message(message):
    # Set up the Telegram bot 
    bot_token = getenv('BOT_TOKEN', '1234567890:ABCDEF') # telegram bot token
    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    msg_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    params = {
            #'chat_id': getenv('DIRECT_MESSAGE_CHATID, '1234'), #direct msg
            'chat_id': getenv('GROUPCHAT_CHATID', '-4321'), #group chat
            'text': f'[{msg_now}] {message}'
        }
    response = requests.post(url, params=params)
    if response.status_code == 200:
        print(f'[{msg_now}] Telegram message sent!')
    else:
        print(f'[{msg_now}] error sending Telegram message! {response.status_code} {response.text}')

def get_validator_info():
    url = "https://mainnet.radixdlt.com/validators"
    payload = """{
     "network_identifier": {
         "network": "mainnet"
     }
    }"""
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    response = requests.request("POST", url, headers=headers, data=payload)
    try: 
        #validator_data = json.loads(response.text)
        validator_list_data = json.loads(response.text)
        if validator_list_data.get('validators'):
            for idx, validator_data in enumerate(validator_list_data.get('validators')):
                if validator_data['validator_identifier']['address'] == validator_address:
                    cur_stake = validator_data['stake']['value']
                    cur_uptime = validator_data['info']['uptime']['uptime_percentage']
                    cur_proposals = validator_data['info']['uptime']['proposals_completed']
                    cur_proposals_missed = validator_data['info']['uptime']['proposals_missed']
                    return {"stake": si_format(float(cur_stake[:-18]), precision=2),
                        "uptime": cur_uptime,
                        "proposals": cur_proposals,
                        "proposals_missed": cur_proposals_missed,
                        "position_in_set": str(idx+1)}
            raise ValueError(f'could not find validator {validator_address} in validator list data {response.text}')
        else:
            raise ValueError(f'could not parse validator list data {response.text}')
    except Exception as ex:
        return f'could not parse api gateway response - exception {str(ex)} - HTTP {response.status_code} {response.text}'

def compare_stake(cur_stake: str):
    try:
        with open(last_validator_info_file, 'r') as f:
            old_validator_info = f.read()
        prev_validator_info = json.loads(old_validator_info)
        prev_stake = prev_validator_info.get('stake')
        if prev_stake != cur_stake:
            # Send the result to the Telegram bot 
            change_msg = f'stake changed from {prev_stake} to {cur_stake}'
            send_message(change_msg)
            print(f'[{now}] {change_msg}')
        else:
            print(f'[{now}] stake unchanged at {cur_stake}')
    except Exception as e:
        print(f'[{now}] could not parse last validator info file - exception {str(e)}')

def compare_uptime(cur_uptime: str):
    try:
        with open(last_validator_info_file, 'r') as f:
            old_validator_info = f.read()
        prev_validator_info = json.loads(old_validator_info)
        prev_uptime = prev_validator_info.get('uptime')
        if prev_uptime > cur_uptime:
            # Send the result to the Telegram bot 
            change_msg = f'uptime decreased from {prev_uptime} to {cur_uptime}'
            send_message(change_msg)
            print(f'[{now}] {change_msg}')
        elif prev_uptime < cur_uptime:
            print(f'[{now}] uptime increased from {prev_uptime} to {cur_uptime}')
        else:
            print(f'[{now}] uptime unchanged at {cur_uptime}')
    except Exception as e:
        print(f'[{now}] could not parse last validator info file - exception {str(e)}')

def compare_proposals_missed(cur_proposals_missed: str):
    try:
        with open(last_validator_info_file, 'r') as f:
            old_validator_info = f.read()
        prev_validator_info = json.loads(old_validator_info)
        prev_proposals_missed = prev_validator_info.get('proposals_missed')
        if prev_proposals_missed < cur_proposals_missed:
            # Send the result to the Telegram bot 
            change_msg = f'proposals_missed increased from {prev_proposals_missed} to {cur_proposals_missed}'
            send_message(change_msg)
            print(f'[{now}] {change_msg}')
        elif prev_proposals_missed > cur_proposals_missed:
            print(f'[{now}] proposals_missed decreased from {prev_proposals_missed} to {cur_proposals_missed}')
        else:
            print(f'[{now}] proposals_missed unchanged at {cur_proposals_missed}')
    except Exception as e:
        print(f'[{now}] could not parse last validator info file- exception {str(e)}')

def compare_position_in_set(cur_position_in_set: str):
    try:
        with open(last_validator_info_file, 'r') as f:
            old_validator_info = f.read()
        prev_validator_info = json.loads(old_validator_info)
        prev_position_in_set = prev_validator_info.get('position_in_set')
        if prev_position_in_set != cur_position_in_set:
            # Send the result to the Telegram bot 
            change_msg = f'position_in_set changed from {prev_position_in_set} to {cur_position_in_set}'
            send_message(change_msg)
            print(f'[{now}] {change_msg}')
        else:
            print(f'[{now}] position_in_set unchanged at {cur_position_in_set}')
    except Exception as e:
        print(f'[{now}] could not parse last validator info file - exception {str(e)}')

# Check the API endpoint 
try:
    # request headers with basic auth
    headers = {
        'Authorization': f'Basic {getenv("NGINX_ACTIVE_BEARER_TOKEN", "Abcdefg==")}',
    }
    r = requests.get(f'https://{active_validator_host}/system/health', headers=headers, verify=False)
    if r.status_code == 200:
        data = json.loads(r.text)
        if 'status' in data and data['status'] == 'UP':
            print(f'[{now}] StakeBros status is UP!')
        else:
            # Send the result to the Telegram bot 
            print(f'[{now}] StakeBros status is NOT UP! {r.text}')
            send_message(f'StakeBros status not UP! {r.text}')
    else:
        send_message(f'[LIVE] Error getting API status! {r.status_code} {r.text}')
except Exception as e:
    send_message(f'[LIVE] Exception getting API status! {str(e)}')

try:
    # request headers with basic auth
    headers = {
        'Authorization': f'Basic {getenv("NGINX_BACKUP_BEARER_TOKEN", "Abcdefg==")}',
    }
    r = requests.get(f'https://{backup_validator_host}/system/health', headers=headers, verify=False)
    if r.status_code == 200:
        data = json.loads(r.text)
        # backup will report UP even if it is still syncing - change this if you'd like to be notified of that
        if 'status' in data and (data['status'] == 'UP' or data['status'] == 'SYNCING' or data['status'] == 'OUT_OF_SYNC' or data['status'] == 'BOOTING_PRE_GENESIS'):
            print(f'[{now}] Backup status is UP!')
        else:
            # Send the result to the Telegram bot
            print(f'[{now}] Backup status is NOT UP! {r.text}')
            send_message(f'Backup status not UP! {r.text}')
    else:
        send_message(f'[BACKUP ]Error getting backup host API status! {r.status_code} {r.text}')
except Exception as e:
    send_message(f'[BACKUP] Exception getting backup host API status! {str(e)}')

validator_info = get_validator_info()
if isinstance(validator_info, dict):
    compare_stake(validator_info['stake'])
    compare_uptime(validator_info['uptime'])
    compare_proposals_missed(validator_info['proposals_missed'])
    compare_position_in_set(validator_info['position_in_set'])

try:
    with open(last_validator_info_file, 'w') as f:
        f.write(json.dumps(validator_info))
        print(f'[{now}] {validator_info}')
except Exception as e:
    print(f'[{now}] could not write last validator info file - exception {str(e)}')

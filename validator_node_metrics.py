import requests
import json
from urllib3.exceptions import InsecureRequestWarning
from apscheduler.schedulers.background import BackgroundScheduler
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest
from flask import Flask, Response
from dotenv import load_dotenv
from os import getenv
import logging

# Suppress only the single warning from urllib3 needed.
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

load_dotenv()

validator_address = getenv('VALIDATOR_ADDRESS', 'rv1...')

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger('urllib3').setLevel(logging.WARN)

logger = logging.getLogger(__name__)

def get_data(url, payload):
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()


def get_validator_stakers():
    url = 'https://mainnet-gateway.radixdlt.com/validator/stakes'

    cursor = None
    total_count = None
    cumulative_count = 0  # Keep track of total delegations fetched

    i = 0
    while total_count is None or cumulative_count < total_count:
        payload = {
            "network_identifier": {
                "network": "mainnet"
            },
            "validator_identifier": {
                "address": validator_address
            },
        }
        if cursor is not None:
            payload['cursor'] = cursor

        data = get_data(url, payload)
        delegations = data.get('account_stake_delegations', [])

        for delegation in delegations:
            account = delegation.get('account', {}).get('address')
            total_stake = int(delegation.get('total_stake', {}).get('value', '0')) / (10**18)

            if total_stake == 0.0:
                logger.info(f"Former staker {account} omitted, 0 delegation left")
            else:
                i = i + 1

        total_count = data.get('total_count')
        cursor = data.get('next_cursor')
        cumulative_count += len(delegations)
        logger.debug(f"Cursor: {cursor}, Delegations fetched this request: {len(delegations)}, Total count: {total_count}, Cumulative count: {cumulative_count}")
    logger.info(f'total_stakers {data.get("total_count")} with stake {i}')
    return i


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
        validator_list_data = json.loads(response.text)
        if validator_list_data.get('validators'):
            for idx, validator_data in enumerate(validator_list_data.get('validators')):
                if validator_data['validator_identifier']['address'] == validator_address:
                    cur_stake = validator_data['stake']['value']
                    cur_uptime = validator_data['info']['uptime']['uptime_percentage']
                    cur_proposals = validator_data['info']['uptime']['proposals_completed']
                    cur_proposals_missed = validator_data['info']['uptime']['proposals_missed']
                    return {"stake": int(cur_stake) / (10**18),
                        "uptime": cur_uptime,
                        "proposals": cur_proposals,
                        "proposals_missed": cur_proposals_missed,
                        "position_in_set": str(idx+1),
                        "stakers": get_validator_stakers()}
            raise ValueError(f'could not find validator {validator_address} in validator list data {response.text}')
        else:
            raise ValueError(f'could not parse validator list data {response.text}')
    except Exception as ex:
        return f'could not parse api gateway response - exception {str(ex)} - HTTP {response.status_code} {response.text}'

# Define Prometheus metrics
STAKE_METRIC = Gauge('validatornode_total_stake', 'Number of total stake from network gateway api')
STAKERS_METRIC = Gauge('validatornode_stakers', 'Number of stakers from network gateway api')
UPTIME_METRIC = Gauge('validatornode_uptime', 'Uptime from network gateway api')
PROPOSALS_MADE_METRIC = Gauge('validatornode_proposals_made', 'Number of proposals completed')
PROPOSALS_MISSED_METRIC = Gauge('validatornode_proposals_missed', 'Number of proposals missed')
POSITION_IN_SET_METRIC = Gauge('validatornode_position_in_set', 'Position in active validator set')

latest_data = None

def fetch_data():
    global latest_data
    latest_data = get_validator_info()
    logger.info(f'retrieved validator data {latest_data}')

# Set up the background scheduler to refresh data from network gateway
# don't do this too often for the public mainnet gateway - or your IP will be blacklisted
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_data, 'interval', minutes=5)
scheduler.start()

app = Flask(__name__)

@app.route('/metrics', methods=['GET'])
def metrics():
    # Update your metric
    STAKE_METRIC.set(latest_data.get('stake'))
    STAKERS_METRIC.set(latest_data.get('stakers'))
    UPTIME_METRIC.set(latest_data.get('uptime'))
    PROPOSALS_MADE_METRIC.set(latest_data.get('proposals'))
    PROPOSALS_MISSED_METRIC.set(latest_data.get('proposals_missed'))
    POSITION_IN_SET_METRIC.set(latest_data.get('position_in_set'))

    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == '__main__':
    # Start the server to expose the metrics.
    fetch_data()
    app.run(host='0.0.0.0', port=8111) # This will make the server accessible from any IP, set up your firewall rules!
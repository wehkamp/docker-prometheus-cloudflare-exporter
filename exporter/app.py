# -*- encoding: utf-8 -*-

from __future__ import print_function

import os
import sys
import json
import logging

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from . import exporter


REQUIRED_VARS = {'AUTH_EMAIL', 'AUTH_KEY', 'SERVICE_PORT', 'ZONE'}
for key in REQUIRED_VARS:
    if key not in os.environ:
        print('Missing value for %s' % key)
        sys.exit()

SERVICE_PORT = int(os.environ.get('SERVICE_PORT', 9199))
ZONE = os.environ.get('ZONE')
ENDPOINT = 'https://api.cloudflare.com/client/v4/'
AUTH_EMAIL = os.environ.get('AUTH_EMAIL')
AUTH_KEY = os.environ.get('AUTH_KEY')
HEADERS = {
    'X-Auth-Key': AUTH_KEY,
    'X-Auth-Email': AUTH_EMAIL,
    'Content-Type': 'application/json'
}


def get_data_from_cf(url):
    r = requests.get(url, headers=HEADERS)
    return json.loads(r.content.decode('UTF-8'))


def get_zone_id():
    r = get_data_from_cf(url='%szones?name=%s' % (ENDPOINT, ZONE))
    return r['result'][0]['id']


def get_metrics():
    print('Fetching data')
    endpoint = '%szones/%s/analytics/colos?since=-35&until=-5&continuous=false'
    r = get_data_from_cf(url=endpoint % (ENDPOINT, get_zone_id()))

    if not r['success']:
        logging.error('Failed to get information from Cloudflare')
        for error in r['errors']:
            logging.error('[%s] %s' % (error['code'], error['message']))
            return ''

    query = r['query']
    logging.info('Window: %s | %s' % (query['since'], query['until']))
    return exporter.process(r['result'], ZONE)

latest_metrics = get_metrics()


def update_latest():
    global latest_metrics
    latest_metrics = get_metrics()


app = Flask(__name__)


@app.route("/")
def home():
    return """<h3>Welcome to the Cloudflare prometheus exporter!</h3>
The following endpoints are available:<br/>
<a href="/metrics">/metrics</a> - Prometheus metrics<br/>
<a href="/status">/status</a> - A simple status endpoint returning "OK"<br/>"""


@app.route("/status")
def status():
    return "OK"


@app.route("/metrics")
def metrics():
    return latest_metrics


def run():
    logging.info('Starting scrape service for zone "%s" using key [%s...]'
                 % (ZONE, AUTH_KEY[0:6]))

    scheduler = BackgroundScheduler({'apscheduler.timezone': 'UTC'})
    scheduler.add_job(update_latest, 'interval', seconds=60)
    scheduler.start()

    try:
        app.run(host="0.0.0.0", port=SERVICE_PORT, threaded=True)
    finally:
        scheduler.shutdown()

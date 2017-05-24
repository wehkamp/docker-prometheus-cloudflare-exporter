# -*- encoding: utf-8 -*-

from __future__ import print_function

import datetime
import os
import sys
import json
import logging

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from . import coloexporter
from . import dnsexporter
from . import wafexporter


logging.basicConfig(level=logging.os.environ.get('LOG_LEVEL', 'INFO'))


REQUIRED_VARS = {'AUTH_EMAIL', 'AUTH_KEY', 'SERVICE_PORT', 'ZONE'}
for key in REQUIRED_VARS:
    if key not in os.environ:
        logging.error('Missing value for %s' % key)
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


def get_colo_metrics():
    logging.info('Fetching colo metrics data')
    endpoint = '%szones/%s/analytics/colos?since=-35&until=-5&continuous=false'
    r = get_data_from_cf(url=endpoint % (ENDPOINT, get_zone_id()))

    if not r['success']:
        logging.error('Failed to get information from Cloudflare')
        for error in r['errors']:
            logging.error('[%s] %s' % (error['code'], error['message']))
            return ''

    query = r['query']
    logging.info('Window: %s | %s' % (query['since'], query['until']))
    return coloexporter.process(r['result'], ZONE)


def get_waf_metrics():
    endpoint = '%szones/%s/firewall/events?per_page=50%s'
    sampledatetime_in_seconds = int(datetime.datetime.strptime(
                datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M"),
                '%Y-%m-%dT%H:%M').strftime("%s")) - 60

    next_page_id = ''
    records_total = []
    sampledatetime = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M")
    while next_page_id is not None:
        logging.info('Fetching WAF event data for %s' % sampledatetime)
        r = get_data_from_cf(url=endpoint % (
                ENDPOINT, get_zone_id(), next_page_id))

        if not r['success']:
            logging.error('Failed to get information from Cloudflare')
            for error in r['errors']:
                logging.error('[%s] %s' % (error['code'], error['message']))
                return ''

        if r['result_info']['next_page_id']:
            logging.debug('Set next_page_id to %s' % r['result_info']['next_page_id'])
            next_page_id = '&next_page_id=%s' % r['result_info']['next_page_id']
        else:
            # the break
            next_page_id = None

        for event in r['result']:
            occurrence = event['occurred_at'].split('.')[0]
            occurrence_in_seconds = datetime.datetime.strptime(occurrence, '%Y-%m-%dT%H:%M:%S').strftime("%s")
            if int(occurrence_in_seconds) <= int(sampledatetime_in_seconds):
                logging.debug('Limit reached: break')
                next_page_id = None
                continue
            logging.info('Adding WAF event')
            records_total.append(event)
        logging.info('WAF events found: %s' % len(records_total))
    return wafexporter.process(records_total)


def get_dns_metrics():
    logging.info('Fetching DNS metrics data')
    time_since = (
                    datetime.datetime.now() + datetime.timedelta(minutes=-1)
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
    time_until = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    endpoint = '%szones/%s/dns_analytics/report?metrics=queryCount'
    endpoint += '&dimensions=queryName,queryType,responseCode,coloName'
    endpoint += '&since=%s'
    endpoint += '&until=%s'

    logging.info('Using: since %s until %s' % (time_since, time_until))
    r = get_data_from_cf(url=endpoint % (
            ENDPOINT, get_zone_id(), time_since, time_until))

    if not r['success']:
        logging.error('Failed to get information from Cloudflare')
        for error in r['errors']:
            logging.error('[%s] %s' % (error['code'], error['message']))
            return ''

    records = int(r['result']['rows'])
    logging.info('Records retrieved: %d' % records)
    if records < 1:
        return ''
    return dnsexporter.process(r['result']['data'], ZONE)


latest_metrics = (get_colo_metrics() + get_dns_metrics() + get_waf_metrics())


def update_latest():
    global latest_metrics
    latest_metrics = (get_colo_metrics() + get_dns_metrics() + get_waf_metrics())


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

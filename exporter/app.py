# -*- encoding: utf-8 -*-

from __future__ import print_function

import datetime
import delorean
import os
import sys
import json
import logging

import requests
import time

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, Response
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.exposition import generate_latest

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
HTTP_SESSION = requests.Session()


class RegistryMock(object):
    def __init__(self, metrics):
        self.metrics = metrics

    def collect(self):
        for metric in self.metrics:
            yield metric


def get_data_from_cf(url):
    r = HTTP_SESSION.get(url, headers=HEADERS)
    return json.loads(r.content.decode('UTF-8'))


def get_zone_id():
    r = get_data_from_cf(url='%szones?name=%s' % (ENDPOINT, ZONE))
    return r['result'][0]['id']


def metric_processing_time(name):
    def decorator(func):
        # @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            result = func(*args, **kwargs)
            elapsed = (time.time() - now) * 1000
            logging.debug('Processing %s took %s miliseconds' % (
                name, elapsed))
            internal_metrics['processing_time'].add_metric([name], elapsed)
            return result
        return wrapper
    return decorator


@metric_processing_time('colo')
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


@metric_processing_time('waf')
def get_waf_metrics():
    # Ffetching WAF data has the potention of taking ages to complete.
    # As this will keep the exporter from gathering any other data else,
    # introduce an option to just not run it.
    if not os.environ.get('ENABLE_WAF'):
        logging.info('Fetching WAF data is disabled')
        return ''

    path_format = '%szones/%s/firewall/events?per_page=50%s'

    zone_id = get_zone_id()

    window_start_time = delorean.now().epoch
    window_end_time = window_start_time - 60

    records = []
    next_page_id = ''

    logging.info('Fetching WAF event data starting at %s, going back 60s'
                 % delorean.epoch(window_start_time).format_datetime())
    while next_page_id is not None:
        url = path_format % (ENDPOINT, zone_id, next_page_id)
        r = get_data_from_cf(url=url)

        if 'success' not in r or not r['success']:
            logging.error('Failed to get information from Cloudflare')
            for error in r['errors']:
                logging.error('[%s] %s' % (error['code'], error['message']))
                return ''

        if r['result_info']['next_page_id']:
            next_id = r['result_info']['next_page_id']
            logging.debug('Set next_page_id to %s' % next_id)
            next_page_id = ('&next_page_id=%s' % next_id)
        else:
            next_page_id = None

        for event in r['result']:
            occurred_at = event['occurred_at']
            occurrence_time = delorean.parse(occurred_at).epoch

            logging.debug('Occurred at: %s (%s)'
                          % (occurred_at, occurrence_time))

            if occurrence_time <= window_end_time:
                logging.debug('Window end time reached, breaking')
                next_page_id = None
                break

            logging.debug('Adding WAF event')
            records.append(event)

        now = delorean.now().epoch
        logging.info('%d WAF events found (took %g seconds so far)'
                     % (len(records), now - window_start_time))

        if now - window_start_time > 55:
            logging.warn('Too many WAF events, skipping (metrics affected)')
            next_page_id = None

    return wafexporter.process(records)


@metric_processing_time('dns')
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


def update_latest():
    global latest_metrics, internal_metrics
    internal_metrics = {
        'processing_time': GaugeMetricFamily(
            'cloudflare_exporter_processing_time_miliseconds',
            'Processing time in ms',
            labels=[
                'name'
            ]
        )
    }

    latest_metrics = (get_colo_metrics() + get_dns_metrics() +
                      get_waf_metrics())
    latest_metrics += generate_latest(RegistryMock(internal_metrics.values())).decode()


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
    return Response(latest_metrics, mimetype='text/plain')


def run():
    logging.info('Starting scrape service for zone "%s" using key [%s...]'
                 % (ZONE, AUTH_KEY[0:6]))

    update_latest()

    scheduler = BackgroundScheduler({'apscheduler.timezone': 'UTC'})
    scheduler.add_job(update_latest, 'interval', seconds=60)
    scheduler.start()

    try:
        app.run(host="0.0.0.0", port=SERVICE_PORT, threaded=True)
    finally:
        scheduler.shutdown()

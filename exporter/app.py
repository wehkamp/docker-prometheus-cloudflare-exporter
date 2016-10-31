# -*- encoding: utf-8 -*-

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from . import exporter
import json
import requests
import time
import os


AUTH_EMAIL = os.environ.get('AUTH_EMAIL')
AUTH_KEY = os.environ.get('AUTH_KEY')
SERVICE_PORT = int(os.environ.get('SERVICE_PORT', 9199))
ZONE = os.environ.get('ZONE')
ENDPOINT = 'https://api.cloudflare.com/client/v4/'
HEADERS = {'X-Auth-Key': AUTH_KEY, 'X-Auth-Email': AUTH_EMAIL, 'Content-Type': 'application/json'}


# TODO: realy process here, instead of a mere check for existence.
def processargs():
    required_vars = {'AUTH_EMAIL', 'AUTH_KEY', 'SERVICE_PORT', 'ZONE'}
    fail = False
    for key in required_vars:
        if os.environ.get(key) is None:
            print('Missing value for %s' % key)
            fail = True
    if fail:
        sys.exit()


def getdatafromcf(url):
    return json.loads(requests.get(url, headers=HEADERS).content.decode('UTF-8'))


def getzoneid():
    r = getdatafromcf(url=ENDPOINT+'zones?name='+ZONE)
    return r['result'][0]['id']

zoneid = getzoneid()

def get_metrics():
    print('Fetching data')
    response = getdatafromcf(url=ENDPOINT+'zones/'+zoneid+'/analytics/colos?since=-35&until=-5&continuous=false')
    if not response['success']:
        print('Failed to get information from cloudflare')
        for m in response['errors']:
            print('[%s] %s' % (m['code'], m['message']))
            return ''
    print('Window: %s | %s' % (response['query']['since'], response['query']['until']))
    return exporter.process(response['result'], ZONE)

latest_metrics = get_metrics()

def update_latest():
    global latest_metrics
    latest_metrics = get_metrics()


app = Flask(__name__)


@app.route("/")
def rootrequest():
    r = '<h3>Welcome to the Cloudflare prometheus exporter!</h3>'
    r+= 'The following endpoints are available:<br/>'
    r+= ' <a href="/metrics">/metrics</a> - Prometheus scrapable metrics<br/>'
    r+= ' <a href="/status">/status</a>  - A simple status endpoint returning "OK"<br/>'
    return r


@app.route("/status")
def status():
    return "OK"


@app.route("/metrics")
def metrics():
    return latest_metrics


def run():
    processargs()
    print('Starting scrape service for zone *%s* using key [%s...]' % (ZONE, AUTH_KEY[0:6]))

    scheduler = BackgroundScheduler({'apscheduler.timezone': 'UTC'})
    scheduler.add_job(update_latest, 'interval', seconds=60)
    scheduler.start()

    try:
        app.run(host="0.0.0.0", port=SERVICE_PORT, threaded=True)
    finally:
        scheduler.shutdown()

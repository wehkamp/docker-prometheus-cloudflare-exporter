#!/usr/bin/env python
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from threading import Timer
import json
import requests
import sys
import time
import os

AUTH_EMAIL = os.environ.get('AUTH_EMAIL')
AUTH_KEY = os.environ.get('AUTH_KEY')
SERVICE_PORT = int(os.environ.get('SERVICE_PORT'))
ZONE = os.environ.get('ZONE')
ENDPOINT = 'https://api.cloudflare.com/client/v4/'
HEADERS = {'X-Auth-Key': AUTH_KEY, 'X-Auth-Email': AUTH_EMAIL, 'Content-Type': 'application/json'}


class metricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-type", "text/plain; version=0.0.4")
            self.end_headers()

            self.wfile.write(current_report)

        elif self.path == "/status":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()

            self.wfile.write("OK")

        else:
            self.send_error(404, "Not found")


class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer = None
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False


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


def generate_metrics_headers():
    metric_headers = []
    metric_headers.append("# TYPE cloudflare_pop_requests gauge")
    metric_headers.append("# TYPE cloudflare_pop_bandwidth gauge")
    metric_headers.append("# TYPE cloudflare_pop_http_reponses gauge")
    metric_headers.append("# TYPE cloudflare_pop_threats gauge")
    metric_headers.append("# TYPE cloudflare_pop_threat_types gauge")
    return metric_headers


def generate_metrics(sample):
    # Use the last sample since that contains the latest minute of data.
    serie = sample['timeseries'][-1]
    metrics = []
    metrics.append('cloudflare_pop_requests{colo_id="%s",type="%s"} %s' % (sample['colo_id'], 'cached', serie['requests']['cached']))
    metrics.append('cloudflare_pop_requests{colo_id="%s",type="%s"} %s' % (sample['colo_id'], 'uncached', serie['requests']['uncached']))
    metrics.append('cloudflare_pop_bandwidth{colo_id="%s",type="%s"} %s' % (sample['colo_id'], 'cached', serie['bandwidth']['cached']))
    metrics.append('cloudflare_pop_bandwidth{colo_id="%s",type="%s"} %s' % (sample['colo_id'], 'uncached', serie['bandwidth']['uncached']))

    for http_status, value in serie['requests']['http_status'].items():
        metrics.append('cloudflare_pop_http_response{colo_id="%s",http_status="%s"} %s' % (sample['colo_id'], http_status, value))

    metrics.append('cloudflare_pop_threats{colo_id="%s"} %s' % (sample['colo_id'], serie['threats']['all']))

    for threat, value in serie['threats']['type'].items():
        metrics.append('cloudflare_pop_threat_types{colo_id="%s",threat_type="%s"} %s' % (sample['colo_id'], threat, value))

    return metrics


def get_cf_data():
    global current_report
    start = time.time()
    current_report = get_metrics_report()
    print "Metrics updated in %d seconds." % (time.time() - start)


def get_metrics_report():
    global zoneid
    response = getdatafromcf(url=ENDPOINT+'zones/'+zoneid+'/analytics/colos?since=-60&until=-5&continuous=false')
    if not response['success']:
        print('Failed to get information from cloudflare')
        for m in response['errors']:
            print('[%s] %s' % (m['code'], m['message']))
        return

    metrics = [generate_metrics(cfpop) for cfpop in response['result']]
    return generate_metrics_report(metrics)


def generate_metrics_report(metrics_list):
    report = []
    report.extend(generate_metrics_headers())
    for metrics in metrics_list:
        report.extend(metrics)
    return "\n".join(report) + "\n"


def main():
    processargs()
    global zoneid
    zoneid = getzoneid()
    print('Starting scrape service for zone *%s* using key [%s...]' % (ZONE, AUTH_KEY[0:6]))

    try:
        server = HTTPServer(("", SERVICE_PORT), metricsHandler)
        print("Exposing Cloudflare metrics on port %d" % SERVICE_PORT)

        # Refresh every 60 seconds since that's the granularity we get from CF.
        # It's just 5 minutes behind overall...
        rt = RepeatedTimer(60, get_cf_data)

        get_cf_data()
        rt.start()
        server.serve_forever()

    except KeyboardInterrupt:
        rt.stop()


if __name__ == "__main__":
    main()

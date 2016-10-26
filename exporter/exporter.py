#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os
import json
from prometheus_client import parser
from prometheus_client.core import Metric, GaugeMetricFamily, Gauge
from prometheus_client.exposition import generate_latest


def process(raw_data, zone):
    class RegistryMock(object):
        def __init__(self, metrics):
            self.metrics = metrics

        def collect(self):
            for metric in self.metrics:
                yield metric

    def generate_metrics(popdata, families):
        # The last sample is what we're after here.
        serie = popdata['timeseries'][-2]
        print ("%s | %s" % (serie['since'], serie['until']))
        families['received_requests'].add_metric([zone, 'cached', popdata['colo_id']], serie['requests']['cached'])
        families['received_requests'].add_metric([zone, 'uncached', popdata['colo_id']], serie['requests']['uncached'])

        families['bandwidth_bytes'].add_metric([zone, 'cached', popdata['colo_id']], serie['bandwidth']['cached'])
        families['bandwidth_bytes'].add_metric([zone, 'uncached', popdata['colo_id']], serie['bandwidth']['uncached'])

        for http_status, value in serie['requests']['http_status'].items():
            families['http_responses_send'].add_metric([zone, popdata['colo_id'], http_status], value)

        families['threats_seen'].add_metric([zone, popdata['colo_id']], serie['threats']['all'])

        for threat, value in serie['threats']['type'].items():
            families['threat_types'].add_metric([zone, popdata['colo_id'], threat], value)

    families = {
        'received_requests':   GaugeMetricFamily('cloudflare_pop_received_requests', 'Requests received at this PoP location.', labels=['zone', 'type', 'colo_id']),
        'bandwidth_bytes':     GaugeMetricFamily('cloudflare_pop_bandwidth_bytes', 'Bandwidth send from this PoP location.', labels=['zone', 'type', 'colo_id']),
        'http_responses_send': GaugeMetricFamily('cloudflare_pop_http_responses_send', 'Breakdown per HTTP response code.', labels=['zone', 'type', 'colo_id']),
        'threats_seen':        GaugeMetricFamily('cloudflare_pop_threats_seen', 'Threats identified.', labels=['zone', 'colo_id', 'threats']),
        'threat_types':        GaugeMetricFamily('cloudflare_pop_threat_types', 'Threat breakdown per threat type.', labels=['zone', 'colo_id', 'threat_type'])
    }

    for popdata in raw_data:
        generate_metrics(popdata, families)
    return generate_latest(RegistryMock(families.values()))


if __name__ == "__main__":
    import os

    source_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(source_dir, "sample")

    with open(path) as f:
        print process(json.load(f)['result'])

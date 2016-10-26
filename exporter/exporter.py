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
        # Samples -4 ~ -1 could contain zeros and no actual values.
        # This is a Cloudflare limitation.
        serie = popdata['timeseries'][-7]
        print ("%s | %s" % (serie['since'], serie['until']))
        families['requests'].add_metric([zone, 'cached', popdata['colo_id']], serie['requests']['cached'])
        families['requests'].add_metric([zone, 'uncached', popdata['colo_id']], serie['requests']['uncached'])

        families['bandwidth'].add_metric([zone, 'cached', popdata['colo_id']], serie['bandwidth']['cached'])
        families['bandwidth'].add_metric([zone, 'uncached', popdata['colo_id']], serie['bandwidth']['cached'])

        for http_status, value in serie['requests']['http_status'].items():
            families['http_response'].add_metric([zone, popdata['colo_id'], http_status], value)

        families['threats'].add_metric([zone, popdata['colo_id']], serie['threats']['all'])

        for threat, value in serie['threats']['type'].items():
            families['threat_types'].add_metric([zone, popdata['colo_id'], threat], value)

    families = {
        'requests':      GaugeMetricFamily('cloudflare_pop_requests', 'Requests received at this PoP location.', labels=['zone', 'type', 'colo_id']),
        'bandwidth':     GaugeMetricFamily('cloudflare_pop_bandwidth', 'Bandwidth send from this PoP location.', labels=['zone', 'type', 'colo_id']),
        'http_response': GaugeMetricFamily('cloudflare_pop_http_response', 'Breakdown per HTTP response code.', labels=['zone', 'type', 'colo_id']),
        'threats':       GaugeMetricFamily('cloudflare_pop_threats', 'Threats identified.', labels=['zone', 'colo_id', 'threats']),
        'threat_types':  GaugeMetricFamily('cloudflare_pop_threat_types', 'Threat breakdown per threat type.', labels=['zone', 'colo_id', 'threat_type'])
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

#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import json

from prometheus_client.core import GaugeMetricFamily
from prometheus_client.exposition import generate_latest


def process(raw_data, zone):
    class RegistryMock(object):
        def __init__(self, metrics):
            self.metrics = metrics

        def collect(self):
            for metric in self.metrics:
                yield metric

    def generate_metrics(pop_data, families):
        # We're interested in the latest metrics, however
        # the Cloudflare API doesn't guarantee non-zero values.
        # Index -2 was chosen empirically and is usually non-zero.
        serie = pop_data['timeseries'][-2]

        families['received_requests'].add_metric(
            [zone, 'cached', pop_data['colo_id']],
            serie['requests']['cached'])
        families['received_requests'].add_metric(
            [zone, 'uncached', pop_data['colo_id']],
            serie['requests']['uncached'])

        families['bandwidth_bytes'].add_metric(
            [zone, 'cached', pop_data['colo_id']],
            serie['bandwidth']['cached'])
        families['bandwidth_bytes'].add_metric(
            [zone, 'uncached', pop_data['colo_id']],
            serie['bandwidth']['uncached'])

        for http_status, count in iter(serie['requests']['http_status'].items()):
            families['http_responses_sent'].add_metric(
                [zone, pop_data['colo_id'], http_status], count)

        families['threats_seen'].add_metric(
            [zone, pop_data['colo_id']], serie['threats']['all'])

        for threat, count in iter(serie['threats']['type'].items()):
            families['threat_types'].add_metric(
                [zone, pop_data['colo_id'], threat], count)

        for country, count in iter(serie['threats']['country'].items()):
            families['threat_countries'].add_metric(
                [zone, pop_data['colo_id'], country], count)

    families = {
        'received_requests': GaugeMetricFamily(
            'cloudflare_pop_received_requests',
            'Requests received at this PoP location.',
            labels=['zone', 'type', 'colo_id']),
        'bandwidth_bytes': GaugeMetricFamily(
            'cloudflare_pop_bandwidth_bytes',
            'Bandwidth used from this PoP location.',
            labels=['zone', 'type', 'colo_id']),
        'http_responses_sent': GaugeMetricFamily(
            'cloudflare_pop_http_responses_sent',
            'Breakdown per HTTP response code.',
            labels=['zone', 'colo_id', 'http_status']),
        'threats_seen': GaugeMetricFamily(
            'cloudflare_pop_threats_seen',
            'Threats identified.',
            labels=['zone', 'colo_id', 'threats']),
        'threat_types': GaugeMetricFamily(
            'cloudflare_pop_threat_types',
            'Threat breakdown per threat type.',
            labels=['zone', 'colo_id', 'threat_type']),
        'threat_countries': GaugeMetricFamily(
            'cloudflare_pop_threat_countries',
            'Threat breakdown per country.',
            labels=['zone', 'colo_id', 'threat_country'])
    }

    for pop_data in raw_data:
        generate_metrics(pop_data, families)
    return generate_latest(RegistryMock(families.values())).decode()


if __name__ == "__main__":
    import os

    source_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(source_dir, "sample")

    with open(path) as f:
        print(process(json.load(f)['result']))

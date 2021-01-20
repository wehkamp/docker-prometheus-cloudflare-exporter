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
        dns_data = pop_data['dimensions']
        rvalue = pop_data['metrics'][0]

        families['record_queried'].add_metric(
            [zone, dns_data[0], dns_data[1], dns_data[2], dns_data[3]],
            rvalue)

    families = {
        'record_queried': GaugeMetricFamily(
            'cloudflare_dns_record_queries',
            'DNS queries per record at PoP location.',
            labels=[
                'zone',
                'record_name',
                'record_type',
                'query_response',
                'colo_id'
            ]
        )
    }

    for pop_data in raw_data:
        generate_metrics(pop_data, families)
    return generate_latest(RegistryMock(families.values())).decode()


if __name__ == "__main__":
    import os

    source_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(source_dir, "sample-dns")

    with open(path) as f:
        print(process(json.load(f)['result']))

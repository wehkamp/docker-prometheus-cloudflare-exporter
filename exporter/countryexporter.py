#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import json

from prometheus_client.core import GaugeMetricFamily
from prometheus_client.exposition import generate_latest


def process(raw_data, zone):  # raw_data is dict {"timeseries":[data here]}
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
        serie = pop_data['timeseries'][-2]   # result{"timeseries":[data]}
                                             #

        families['received_requests_all_countries'].add_metric(
            [zone, 'cached'],
            serie['requests']['cached'])
        families['received_requests_all_countries'].add_metric(
            [zone, 'uncached'],
            serie['requests']['uncached'])

        families['bandwidth_bytes_all_countries'].add_metric(
            [zone, 'cached'],
            serie['bandwidth']['cached'])
        families['bandwidth_bytes_all_countries'].add_metric(
            [zone, 'uncached'],
            serie['bandwidth']['uncached'])

        for country, count in serie['bandwidth']['country'].iteritems():  # This piece is considered to expose bandwidth metrics for countries
            families['bandwidth_byte_per_country'].add_metric(
                [zone, country], count)

        for http_status, count in serie['requests']['http_status'].iteritems():
            families['http_responses_sent_all_countries'].add_metric(
                [zone, http_status], count)

        families['threats_seen'].add_metric(
            [zone], serie['threats']['all'])

        for threat, count in serie['threats']['type'].iteritems():
            families['threat_types'].add_metric(
                [zone, threat], count)

        for country, count in serie['threats']['country'].iteritems():
            families['threat_countries'].add_metric(
                [zone, country], count)





    families = {
        'received_requests_all_countries': GaugeMetricFamily(
            'received_requests_all_countries',
            'Requests received from all countries.',
            labels=['zone', 'type']),
        'bandwidth_bytes_all_countries': GaugeMetricFamily(
            'bandwidth_bytes_all_countries',
            'Bandwidth used from all countries.',
            labels=['zone', 'type']),
        'bandwidth_byte_per_country': GaugeMetricFamily(
            'bandwidth_byte_per_country',
            'Bandwidth used from specified country.',
            labels=['zone', 'bandwidth_country']),
        'http_responses_sent_all_countries': GaugeMetricFamily(
            'http_responses_sent_all_countries',
            'Breakdown per HTTP response code for all countries.',
            labels=['zone', 'http_status']),
        'threats_seen': GaugeMetricFamily(
            'cloudflare_pop_threats_seen_by_country',
            'Threats identified by country.',
            labels=['zone', 'threats']),
        'threat_types': GaugeMetricFamily(
            'cloudflare_pop_threat_types_by_country',
            'Threat breakdown per threat type by country.',
            labels=['zone', 'threat_type']),
        'threat_countries': GaugeMetricFamily(
            'threat_countries_by_country',
            'Threat breakdown per country by country.',
            labels=['zone', 'threat_country'])
    }

    generate_metrics(raw_data, families)
    return generate_latest(RegistryMock(families.values()))


if __name__ == "__main__":
    import os

    source_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(source_dir, "sample")

    with open(path) as f:
        print process(json.load(f)['result'])

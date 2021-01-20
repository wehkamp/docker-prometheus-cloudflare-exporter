#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import ast
import os
import json

from prometheus_client.core import GaugeMetricFamily
from prometheus_client.exposition import generate_latest


def process(raw_data):
    class RegistryMock(object):
        def __init__(self, metrics):
            self.metrics = metrics

        def collect(self):
            for metric in self.metrics:
                yield metric

    def process_metrics(data):
        rule_hits = {}
        uri_hits = {}
        for e in data:
            # Skip all attacks from T1, since we're blocking those by default.
            if (e['country'].upper() == "T1") and (
                    os.environ.get('SCRAPER_SKIP_T1')):
                continue

            if 'rule_id' in e:
                rule_id = e['rule_id'] or 'unknown'
                if rule_id in rule_hits:
                    rule_hits[rule_id]['count'] += 1
                else:
                    rule_hits[rule_id] = {}
                    rule_hits[rule_id]['count'] = 1
                    rule_hits[rule_id]['message'] = (e['rule_message']
                                                     or 'internal')

            uri_hit = str({
                    'host': e['host'],
                    'uri': e['uri'],
                    'method': e['method'],
                    'protocol': e['protocol'],
                    'country': e['country'],
                    'action': e['action'],
                    'rule_id': rule_id,
                    'cloudflare_location': e['cloudflare_location']
            })

            if uri_hit in uri_hits:
                uri_hits[uri_hit] += 1
            else:
                uri_hits[uri_hit] = 1

        return [rule_hits, uri_hits]

    def generate_uri_metrics(data, families):
        for keystring, count in iter(data.items()):
            keys = ast.literal_eval(keystring)
            families['waf_uri_hits'].add_metric(
                [
                    keys['host'],
                    keys['uri'],
                    keys['method'],
                    keys['protocol'],
                    keys['country'],
                    keys['action'],
                    keys['rule_id'],
                    keys['cloudflare_location']
                ],
                count)

    def generate_rule_metrics(data, families):
        for rule_id, d in iter(data.items()):
            families['waf_rule_hits'].add_metric(
                [rule_id, d['message']],
                d['count'])

    # Structure of the metrics we're going to create/expose.
    families = {
        'waf_rule_hits': GaugeMetricFamily(
            'cloudflare_waf_rules',
            'WAF-rules in the system and a hit count.',
            labels=[
                'rule_id',
                'rule_message'
            ]
        ),
        'waf_uri_hits': GaugeMetricFamily(
            'cloudflare_waf_uri_hits',
            'WAF-rule hits at PoP location per uri.',
            labels=[
                'host',
                'uri',
                'method',
                'protocol',
                'attacking_country',
                'action',
                'rule_id',
                'colo_id'
            ]
        )
    }

    # Process all data here to filter and group/sum some numbers.
    waf_rule_hits, waf_uri_hits = process_metrics(raw_data)

    for data, count in iter(waf_uri_hits.items()):
        generate_uri_metrics({data: count}, families)

    for rule, data in iter(waf_rule_hits.items()):
        generate_rule_metrics({rule: data}, families)

    # Return the metrics.
    return generate_latest(RegistryMock(families.values())).decode()


if __name__ == "__main__":
    source_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(source_dir, "sample-waf")

    with open(path) as f:
        print(process(json.load(f)['result']))

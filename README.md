# Prometheus cloudflare exporter
A very simple prometheus exporter that exposes metrics from cloudflare's colocations API as described per `https://api.cloudflare.com/#zone-analytics-analytics-by-co-locations`. Sadly, this is for Cloudflare Enterprise customers only.
It'll expose metrics per PoP and shows requests, bandwidth and threats.

Please note that because of how the Cloudflare API works this exporter will only return statistics from _now() - 5 minutes_.

### Try it
Running the container:

```
docker run \
 --rm \
 -d \
 -p 9199:9199 \
 -e SERVICE_PORT=9199 \
 -e ZONE=example.com \
 -e AUTH_KEY=deadbeefcafe \
 -e AUTH_EMAIL=admin@example.com \
 wehkamp/prometheus-cloudflare-exporter:1.0
```

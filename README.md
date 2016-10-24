# prometheus-cloudflare-exporter
A very simple prometheus exporter that exposes metrics from cloudflare's colocations API as described per `https://api.cloudflare.com/#zone-analytics-analytics-by-co-locations`. Sadly, this is for Cloudflare Enterprise customers only.
It'll expose metrics per PoP and shows requests, bandwidth and threats.

Please note that because of how the Cloudflare API works this exporter will only return statistics from _now() - 5 minutes_.

### try it
Running the container:

```
docker run \
 -d \
 -p 9199:9199 \
 -e SERVICE_PORT=9199 \
 -e ZONE=example.com \
 -e AUTH_KEY=deadbeefcafe \
 -e AUTH_EMAIL=admin@example.com \
 wehkamp/prometheus-cloudflare-exporter:1.0
```
```
Starting scrape service for zone *example.com* using key [deadbe...]
Exposing Cloudflare metrics on port 9199
Metrics updated in 1 seconds.
```

### metrics
The exporter exposes the following metrics, all returned per PoP:

| metric | description | type |
| ------ | ----------- | ---- |
| cloudflare_pop_requests | cached and uncached requests received on an edge-location | gauge |
| cloudflare_pop_bandwidth | cached and uncached bandwidth send from an edge-location | gauge |
| cloudflare_pop_http_reponses | breakdown of requests per HTTP code | gauge |
| cloudflare_pop_threats | number of threats identified received in at this location | gauge |
| cloudflare_pop_threat_types | types of threats seen | gauge

Random scrape result:
```
cloudflare_pop_requests{zone="example.com", colo_id="BRU",type="cached"} 449
cloudflare_pop_requests{zone="example.com", colo_id="BRU",type="uncached"} 1040
cloudflare_pop_bandwidth{zone="example.com", colo_id="BRU",type="cached"} 16385371
cloudflare_pop_bandwidth{zone="example.com", colo_id="BRU",type="uncached"} 5330470
cloudflare_pop_http_response{zone="example.com", colo_id="BRU",http_status="201"} 8
cloudflare_pop_http_response{zone="example.com", colo_id="BRU",http_status="200"} 1235
cloudflare_pop_http_response{zone="example.com", colo_id="BRU",http_status="204"} 166
cloudflare_pop_http_response{zone="example.com", colo_id="BRU",http_status="301"} 3
cloudflare_pop_http_response{zone="example.com", colo_id="BRU",http_status="302"} 7
cloudflare_pop_http_response{zone="example.com", colo_id="BRU",http_status="304"} 14
cloudflare_pop_http_response{zone="example.com", colo_id="BRU",http_status="404"} 44
cloudflare_pop_http_response{zone="example.com", colo_id="BRU",http_status="499"} 12
cloudflare_pop_threats{zone="example.com", colo_id="BRU"} 0
```

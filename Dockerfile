FROM wehkamp/alpine:3.4

ENTRYPOINT ["python", "/usr/local/bin/metrics.py"]
EXPOSE 9199

RUN LAYER=build \
  && apk add -U python py-pip \
  && pip install prometheus_client requests

COPY metrics.py /usr/local/bin/

LABEL container.name=wehkamp/prometheus-cloudflare-exporter:1.0

FROM alpine

ENTRYPOINT ["python3", "-m", "exporter"]
EXPOSE 9199
ENV FLASK_APP=/exporter/exporter/app.py \
    SERVICE_PORT=9199

RUN LAYER=build \
  && apk add -U python3 py3-pip\
  && pip3 install prometheus_client delorean requests apscheduler Flask \
  && rm -rf /var/cache/apk/* \
  && rm -rf ~/.cache/pip

ADD ./exporter /exporter

LABEL container.name=wehkamp/prometheus-cloudflare-exporter:1.1.1

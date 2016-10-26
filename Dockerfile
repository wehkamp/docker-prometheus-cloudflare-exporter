FROM wehkamp/alpine:3.4

ENTRYPOINT ["python", "-m", "exporter"]
ARG SERVICE_PORT=9199
EXPOSE ${SERVICE_PORT}
ENV FLASK_APP=/exporter/exporter/app.py \
    SERVICE_PORT=${SERVICE_PORT}

RUN LAYER=build \
  && apk add -U python py-pip \
  && pip install prometheus_client requests apscheduler Flask \
  && rm -rf /var/cache/apk/* \
  && rm -rf ~/.cache/pip

ADD ./exporter /exporter

LABEL container.name=wehkamp/prometheus-cloudflare-exporter:1.0

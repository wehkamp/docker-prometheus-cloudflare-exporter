run:
	docker build . -t docker-prometheus-cloudflare-exporter
	docker run --publish 9199:9199 -e AUTH_KEY -e AUTH_EMAIL -e ZONE docker-prometheus-cloudflare-exporter
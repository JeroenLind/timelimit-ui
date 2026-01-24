ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM $BUILD_FROM

# Installeer Python en benodigdheden
RUN apk add --no-cache python3 py3-requests

# Kopieer de rootfs
COPY rootfs /

# Maak de scripts uitvoerbaar
RUN chmod +x /etc/s6-overlay/s6-rc.d/example-service/run
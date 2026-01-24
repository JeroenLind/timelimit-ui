ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM $BUILD_FROM

# Installeer Python en benodigde libraries
RUN apk add --no-cache \
    python3 \
    py3-requests \
    py3-flask

# Kopieer de volledige rootfs map naar de container
COPY rootfs /

# Maak alle s6-overlay run scripts uitvoerbaar
RUN chmod +x /etc/s6-overlay/s6-rc.d/example-service/run \
    && chmod +x /etc/s6-overlay/s6-rc.d/frontend-ui/run

# S6-overlay start automatisch als entrypoint
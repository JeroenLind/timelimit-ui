ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM $BUILD_FROM

# Installeer Python en de specifieke crypto bibliotheek
# py3-bcrypt is essentieel voor je nieuwe hashing logica
RUN apk add --no-cache \
    python3 \
    py3-requests \
    py3-bcrypt

# Kopieer de volledige rootfs map naar de container
# Zorg dat frontend.py, api_client.py, crypto_utils.py en dashboard.html 
# in de lokale map 'rootfs/usr/bin/' staan.
COPY rootfs /

# Maak de s6-overlay run scripts uitvoerbaar
RUN chmod +x /etc/s6-overlay/s6-rc.d/backend/run \
    && chmod +x /etc/s6-overlay/s6-rc.d/frontend-ui/run

# S6-overlay start automatisch als entrypoint
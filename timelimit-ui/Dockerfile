ARG BUILD_FROM
FROM $BUILD_FROM

# Kopieer de rootfs (scripts en configuratie)
COPY rootfs /

# Zorg dat de scripts uitvoerbaar zijn
RUN chmod +x /etc/s6-overlay/s6-rc.d/example-service/run

# S6-overlay is standaard de entrypoint in HA base images
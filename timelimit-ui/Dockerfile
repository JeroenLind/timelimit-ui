ARG BUILD_FROM
FROM ${BUILD_FROM}

# Zorg dat rootfs wordt gekopieerd naar de container
COPY rootfs/ /

# Zorg dat de service scripts uitvoerbaar zijn
RUN chmod +x /etc/services.d/timelimit-ui/run \
    && chmod +x /etc/services.d/timelimit-ui/finish
ARG BUILD_FROM
FROM ${BUILD_FROM}

# Kopieer rootfs naar container
COPY rootfs/ /

# Zorg dat de service scripts uitvoerbaar zijn
RUN chmod +x /etc/services.d/timelimit-ui/run \
    && chmod +x /etc/services.d/timelimit-ui/finish
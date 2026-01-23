ARG BUILD_FROM
FROM ${BUILD_FROM}

# Kopieer de volledige rootfs naar het container-bestandssysteem
COPY rootfs/ /

# Zorg dat de service scripts uitvoerbaar zijn
RUN chmod +x /etc/services.d/test/run \
    && chmod +x /etc/services.d/test/finish
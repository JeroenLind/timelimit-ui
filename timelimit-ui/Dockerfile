ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install s6-overlay (aarch64 variant)
ADD https://github.com/just-containers/s6-overlay/releases/download/v3.1.6.2/s6-overlay-aarch64.tar.gz /tmp/s6.tar.gz
RUN tar xzf /tmp/s6.tar.gz -C / && rm /tmp/s6.tar.gz

# Copy root filesystem
COPY rootfs/ /

RUN chmod +x /etc/services.d/timelimit-ui/run \
    && chmod +x /etc/services.d/timelimit-ui/finish

ENTRYPOINT ["/init"]
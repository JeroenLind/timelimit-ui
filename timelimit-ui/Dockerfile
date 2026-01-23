ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN ARCH="$(uname -m)" \
    && case "$ARCH" in \
        aarch64) S6_ARCH="aarch64" ;; \
        x86_64)  S6_ARCH="x86_64" ;; \
        armv7l)  S6_ARCH="arm" ;; \
        *) echo "Unsupported arch: $ARCH"; exit 1 ;; \
    esac \
    && wget -O /tmp/s6.tar.gz \
       https://github.com/just-containers/s6-overlay/releases/download/v3.1.6.2/s6-overlay-${S6_ARCH}.tar.gz \
    && tar xzf /tmp/s6.tar.gz -C / \
    && rm /tmp/s6.tar.gz

COPY rootfs/ /

RUN chmod +x /etc/services.d/timelimit-ui/run \
    && chmod +x /etc/services.d/timelimit-ui/finish

ENTRYPOINT ["/init"]
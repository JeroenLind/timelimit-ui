ARG BUILD_FROM
FROM ${BUILD_FROM}

# Detect architecture
ARG BUILD_ARCH

# Install s6-overlay depending on architecture
# (versions must match the release you want)
RUN case "${BUILD_ARCH}" in \
        "aarch64") ARCH="aarch64" ;; \
        "amd64")   ARCH="x86_64" ;; \
        "armv7")   ARCH="arm" ;; \
        *) echo "Unsupported arch: ${BUILD_ARCH}" ; exit 1 ;; \
    esac \
    && wget -O /tmp/s6.tar.gz \
       https://github.com/just-containers/s6-overlay/releases/download/v3.1.6.2/s6-overlay-${ARCH}.tar.gz \
    && tar xzf /tmp/s6.tar.gz -C / \
    && rm /tmp/s6.tar.gz

# Copy rootfs
COPY rootfs/ /

RUN chmod +x /etc/services.d/timelimit-ui/run \
    && chmod +x /etc/services.d/timelimit-ui/finish

ENTRYPOINT ["/init"]
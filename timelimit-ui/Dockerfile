ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM $BUILD_FROM

# Python and the libraries with native code come from Alpine packages;
# the pure Python libraries of the dashboard come from pip.
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-requests \
    py3-bcrypt \
    py3-cryptography \
 && pip3 install --no-cache-dir --break-system-packages \
    "flask>=3.0,<4" \
    "werkzeug>=3.0,<4" \
    "structlog>=23.1" \
    "apscheduler>=3.10,<4"

# The whole rootfs: the s6 service definitions and the dashboard.
COPY rootfs /

# The s6 service that starts the dashboard must be executable.
RUN chmod +x /etc/s6-overlay/s6-rc.d/dashboard-v2/run

# s6-overlay starts the services listed in s6-rc.d/user/contents.d as the entrypoint.

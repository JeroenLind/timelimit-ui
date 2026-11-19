ARG BUILD_FROM
FROM $BUILD_FROM

# Python only; every library comes from pip, pinned by the generated constraints file
# (tools/make_constraints.py), so the image does not depend on what Alpine packages.
RUN apk add --no-cache python3 py3-pip

COPY requirements.txt constraints.txt /tmp/
RUN pip3 install --no-cache-dir --break-system-packages \
    -r /tmp/requirements.txt -c /tmp/constraints.txt \
 && rm /tmp/requirements.txt /tmp/constraints.txt

# The whole rootfs: the s6 service definitions and the dashboard.
COPY rootfs /

# The s6 service that starts the dashboard must be executable.
RUN chmod +x /etc/s6-overlay/s6-rc.d/dashboard-v2/run

# s6-overlay starts the services listed in s6-rc.d/user/contents.d as the entrypoint.

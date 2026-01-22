ARG BUILD_FROM=ghcr.io/hassio-addons/base:15.0.7
FROM ${BUILD_FROM}

# Metadata
LABEL \
  io.hass.name="TimeLimit UI" \
  io.hass.description="Web UI for TimeLimit server" \
  io.hass.slug="timelimit-ui" \
  io.hass.version="0.1.0" \
  io.hass.type="addon"

# Install Node.js
RUN apk add --no-cache nodejs npm

# Copy rootfs
COPY rootfs/ /

# Debug: verify service directory exists
RUN echo "DEBUG: Listing /etc/services.d" && ls -l /etc/services.d || true
RUN echo "DEBUG: Listing /etc/services.d/timelimit-ui" && ls -l /etc/services.d/timelimit-ui || true

# FIX: ensure scripts are executable (NO CACHE)
RUN chmod +x /etc/services.d/timelimit-ui/run \
    && chmod +x /etc/services.d/timelimit-ui/finish

# check executable bits
RUN ls -l /etc/services.d/timelimit-ui

# Install backend dependencies
WORKDIR /app/backend
RUN npm install --production

EXPOSE 3000
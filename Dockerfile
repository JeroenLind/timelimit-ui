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

# Install backend dependencies
WORKDIR /app/backend
RUN npm install --production

# Expose port for ingress
EXPOSE 3000
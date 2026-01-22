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

# Copy rootfs into container
COPY rootfs/ /

# Debug: verify service directory exists
RUN echo "DEBUG: Listing /etc/services.d" && ls -l /etc/services.d || true

# Debug: verify timelimit-ui service folder exists
RUN echo "DEBUG: Listing /etc/services.d/timelimit-ui" && ls -l /etc/services.d/timelimit-ui || true

# Ensure all service scripts are executable
RUN chmod -R +x /etc/services.d/*/run || true \
    && chmod -R +x /etc/services.d/*/finish || true

# Install backend dependencies
WORKDIR /app/backend
RUN npm install --production

# Expose port for ingress
EXPOSE 3000
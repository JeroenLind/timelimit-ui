ARG BUILD_FROM=ghcr.io/home-assistant/{arch}-base:3.19
FROM ${BUILD_FROM}

# Metadata (optioneel: kun je ook uit build.json via build args vullen)
LABEL \
  io.hass.name="TimeLimit UI" \
  io.hass.description="Web UI for TimeLimit server" \
  io.hass.slug="timelimit-ui" \
  io.hass.version="0.1.0" \
  io.hass.type="addon"

# Node.js + npm
RUN apk add --no-cache nodejs npm

# rootfs van de add-on in het image plaatsen
COPY rootfs/ /

# Debug: check dat de service en backend er echt zijn
RUN echo "DEBUG: Listing /etc/services.d" \
 && ls -l /etc/services.d || true

RUN echo "DEBUG: Listing /etc/services.d/timelimit-ui" \
 && ls -l /etc/services.d/timelimit-ui || true

RUN echo "DEBUG: Listing /app/backend" \
 && ls -l /app/backend || true

# Scripts uitvoerbaar maken
RUN chmod +x /etc/services.d/timelimit-ui/run \
 && chmod +x /etc/services.d/timelimit-ui/finish

# Backend dependencies installeren
WORKDIR /app/backend
RUN npm install --production

EXPOSE 3000
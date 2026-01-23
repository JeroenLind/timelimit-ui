ARG BUILD_FROM
FROM $BUILD_FROM

# Installeer s6-overlay
RUN apk add --no-cache s6-overlay

COPY run.sh /run.sh
RUN chmod a+x /run.sh

# Kopieer run scripts voor backend en frontend
COPY run/backend/run /etc/services.d/backend/run
COPY run/frontend/run /etc/services.d/frontend/run
RUN chmod a+x /etc/services.d/backend/run /etc/services.d/frontend/run

CMD ["/init"]
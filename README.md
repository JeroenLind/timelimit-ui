# TimeLimit UI (Home Assistant add-on)

Een Home Assistant add-on die een web-UI biedt voor de TimeLimit server
(zowel lokaal als de officiële server), als alternatief voor de Android-app.

## Features

- Web-UI via Ingress
- Proxy-backend naar TimeLimit server
- Geen CORS-problemen
- Versie-endpoint (`/api/version`)
- Configureerbare server-URL (default: `http://192.168.68.30:8080`)

## Configuratie

In de add-on opties:

```yaml
server_url: "http://192.168.68.30:8080"
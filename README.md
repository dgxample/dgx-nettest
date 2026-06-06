# dgx-nettest

The **reference container** for DGXample. It runs a deliberately tiny service — a single-port web server returning a status page and a `/health` endpoint — so the security scaffolding is easy to read and copy. Real containers replace the service; everything else stays the same.

It doubles as a network-isolation test harness: `security-check` and `security-compare` verify that strict mode actually blocks all container-initiated outbound traffic.

Part of the [DGXample](https://github.com/dgxample) project — see the organization page or the included DGXAMPLE.md for run modes, strict network lockdown, security checks, resource limits, and HTTPS setup.

## Requirements

- Linux host (iptables is Linux-only)
- Docker and Docker Compose v2 (`docker compose` — not the legacy `docker-compose`)
- **sudo** — OPTIONAL but required for strict mode (iptables outbound blocking)

## Setup

```bash
git clone https://github.com/dgxample/dgx-nettest
cd dgx-nettest
./setup
```

The setup script prompts for:

| Setting | Description |
|---|---|
| Container UID | UID the container process runs as (defaults to your current user) |
| Host port | Port to expose on the host (default: 8999) |
| Outbound lockdown | Defaults to strict mode and configures `docker-lockdown` |
| HTTPS | Whether to enable TLS (default: no) |
| Restart policy | Whether the container auto-restarts on crash or reboot (default: no) |

Settings are saved to `.env`.

## Starting and stopping

```bash
./start-container           # use this normally — uses the settings in .env from running setup
./start-container --open    # override to open mode — no outbound restrictions, no sudo needed
./start-container --build   # force a rebuild (required after Dockerfile changes)
./start-container --working # roll back to the :working image (saved before the last --build)
./stop-container
```

## Usage

The service listens on the configured port:

- `GET /health` — returns `{"status": "ok"}` (also polled by Docker's healthcheck)
- `GET /` — HTML status page showing hostname, mode, protocol, and uptime

To build a real container from this one, replace the request handler in `nettest.py` with your service and keep the `/health` endpoint — all the surrounding scaffolding stays the same.

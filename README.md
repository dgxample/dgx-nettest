# dgx-nettest

Part of the [DGXample](https://github.com/dgxample) project — see the organization for an overview and other container repos.

The **reference container** for DGXample. It runs a deliberately tiny service — a
web server on a single port that returns a status/info page (and a `/health`
endpoint) — so the security and operational scaffolding around it is easy to read
and copy. Real containers replace the service; everything else stays the same.

It also doubles as a network-isolation test harness: `security-check` and
`security-compare` verify that strict mode actually blocks all container-initiated
outbound traffic.

## Why this exists

The code in these containers comes from strangers on the internet. DGXample
treats it as untrusted and contains it:

- **Two run modes.** `--open` allows outbound traffic (for setup tasks like
  downloading models or packages). `--strict` (default) blocks *all*
  container-initiated outbound traffic — nothing leaves unless you allow it.
- **Defense in depth.** Non-root via `setpriv`, all Linux capabilities dropped,
  read-only root filesystem, sized `tmpfs` for writable paths, an in-container DNS
  block, host-side `iptables` outbound lockdown, and resource limits.
- **Easy to reproduce.** One `./setup` prompts for everything and writes `.env`;
  `./start-container` builds, starts, and applies lockdown. Someone cloning this
  repo should get the same container running without the struggle.

## Requirements

- Linux host (iptables is Linux-only)
- Docker and Docker Compose v2 (`docker compose` — not the legacy `docker-compose`)
- sudo access (for iptables management in strict mode)

Most Linux systems already have everything else (`python3`, `openssl`, `setpriv`). The easiest approach is to just run `./setup` and see if anything is missing.

## Quick start

```bash
./setup            # prompts for UID, port, lockdown, optional HTTPS; writes .env
./start-container  # start (builds on first run), apply lockdown (strict by default), wait for health
```

The URL (`http://` or `https://`) is printed once the container is healthy.

```bash
./stop-container   # stop and remove lockdown rules
```

Re-run `./setup` at any time to change settings — all prompts default from the existing `.env`, so only the values you change need input.

## Run modes

```bash
./start-container            # strict (default) — blocks all outbound traffic
./start-container --open     # open — no outbound restrictions, no sudo needed
./start-container --build    # force a rebuild (required after Dockerfile or entrypoint changes)
./start-container --working  # roll back to the :working image saved before the last --build
./start-container --without-tools  # rebuild without curl/dig/ping/nc (tools are included by default)
```

| Flag | Effect |
|------|--------|
| `--strict` | Blocks all container-initiated outbound traffic. Default. Requires sudo. |
| `--open` | No traffic restrictions. Process hardening still applies. No sudo needed. |
| `--build` | Force a docker compose build before starting. Skipped by default when the image already exists. Before building, offers to save the current `:latest` as `:working` for easy rollback. |
| `--working` | Start from the `:working` image instead of `:latest`. Use to roll back after a broken build. |
| `--without-tools` | Excludes curl, dig, ping, nc, traceroute, wget. Triggers a rebuild. Default is to include them. |

The default security level is read from `.env`; the flags override it.

## Network lockdown

Strict mode combines two layers:

- **Host side:** `docker-lockdown` inserts rules into Docker's `DOCKER-USER` chain
  for the container's subnet, allowing established/related return traffic and
  dropping everything else outbound. `./setup` installs `docker-lockdown` to a
  root-owned path (default `/usr/local/bin/docker-lockdown`) so a sudoers entry for
  it is safe — the regular user cannot replace the script.
- **In container:** `entrypoint.sh` blocks Docker's embedded DNS at `127.0.0.11`
  before dropping privileges, closing the DNS-exfiltration path that host-side rules
  miss (Docker rewrites port 53 before the filter chain sees it).

```bash
sudo docker-lockdown status     # show active rules
sudo docker-lockdown cleanup    # remove orphaned rules from previous runs
```

### Passwordless sudo (optional, for automation)

Strict mode needs sudo to manage iptables. By default `start`/`stop` prompt for
your password. If you want a dashboard or script to manage the container without a
prompt, `./setup` can create a sudoers drop-in granting passwordless sudo for
`docker-lockdown` only. The port-range validation in `docker-lockdown` bounds what
that grant can do.

## HTTPS / TLS

`./setup` offers three choices:

1. **Shared host certificate (preferred)** — one cert at `~/.local/share/certs`
   by default (configurable during setup), reused by every container on the host. Trust it once in your browser/OS and all
   containers are covered. Setup prints OS-trust-store instructions (needed so the
   browser's *download manager*, not just page navigation, trusts it).
2. **Per-container certificate** — generated in `./certs`, used only by this container.
3. **None** — plain HTTP.

The cert is generated on the host during setup, so its fingerprint is stable: you
accept the browser warning once, not on every restart.

## Resource limits

Strict mode caps CPU, memory, PIDs, and tmpfs sizes to bound a runaway or
compromised container. `./setup` writes sensible defaults to `.env`, so strict mode
starts immediately. To tighten them to measured usage:

1. `./start-container --open` and exercise the service.
2. `./stop-container` — prints a usage snapshot and suggested `.env` values with
   headroom applied.
3. Paste the values into `.env`, then `./start-container --strict`.

For more accurate readings, run `docker stats dgx-nettest` while it's under load.

## Configuration

All settings are stored in `.env`, written by `./setup`. The table below covers every variable — run `./setup` to change any of them interactively.

| Variable | Default | Description |
|---|---|---|
| `CONTAINER_UID` | current user's UID | UID the container process runs as. Match your own UID to avoid file permission mismatches on any volume mounts. |
| `HOST_PORT` | `8999` | Port the service is published on the host. Must be in the 1024–49151 range. |
| `SECURITY_LEVEL` | `strict` | `strict` blocks all outbound traffic; `open` allows it. Overridable per-run with `--strict` / `--open`. |
| `DOCKER_LOCKDOWN_PATH` | `/usr/local/bin/docker-lockdown` | Absolute path where `docker-lockdown` is installed. Set by `./setup` at install time. |
| `USE_HTTPS` | `false` | Serve HTTPS instead of HTTP. Requires a certificate (generated by `./setup`). |
| `HOST_CERT_DIR` | `~/.local/share/certs` | Directory containing the shared host TLS certificate. Used when `USE_HTTPS=true` and shared cert mode is chosen. |
| `RESTART_POLICY` | `no` | Docker restart policy. `no` requires manual restart on crash; `unless-stopped` restarts automatically but risks an OOM loop if memory limits are too tight. |
| `CPU_LIMIT` | `1.00` | CPU cores available to the container in strict mode. |
| `MEM_LIMIT` | `256m` | Memory limit in strict mode. |
| `PIDS_LIMIT` | `50` | Maximum number of processes in strict mode. Prevents fork bombs. |
| `TMP_SIZE` | `64m` | Size of the `/tmp` tmpfs mount. |
| `RUN_SIZE` | `16m` | Size of the `/run` tmpfs mount. |

Resource limits ship with conservative defaults so strict mode works immediately. To tighten them to measured values, see the Resource limits section above.

## Verification

```bash
./security-check              # run the posture checks against the running container
./security-compare            # run open vs strict back-to-back, diff side by side
./security-compare --no-tools # skip installing diagnostic tools
```

`security-check` verifies process hardening and network posture and prints a
PASS/FAIL/SKIP result for each check. Tests needing diagnostic tools (`dig`, `ping`,
`curl`, `nc`) are skipped if the image was built with `--without-tools`.

| Check | What it verifies |
|---|---|
| DOCKER-USER rules | Host-side iptables rules are present in strict mode (or absent in open). These block all outbound packets from the container's subnet except established/related return traffic. |
| PID 1 not root | The main container process dropped to an unprivileged UID via `setpriv`. The container's code never runs as root. |
| PID 1 GID matches UID | The group ID also dropped correctly. Rules out a partial privilege drop where UID changes but GID stays root. |
| PID 1 no effective capabilities | All Linux capabilities were cleared. Even if the process calls `execve` on a setuid binary, it gains nothing. |
| Health check port | The service is reachable from the host — confirms the app started, is listening, and the port mapping works. |
| DNS resolution (dig) | Whether the container can resolve hostnames via `dig`. Strict mode blocks this via an in-container iptables rule on `127.0.0.11` (Docker's embedded DNS). |
| DNS resolution (python socket) | Same DNS test via Python's stdlib — a different code path than dig. Both must be blocked for the DNS lockdown to be complete. |
| Ping to 1.1.1.1 | Whether outbound ICMP is blocked. Tests the DROP rule against a protocol that isn't TCP or UDP. |
| HTTP to 1.1.1.1 | Whether outbound TCP port 80 is blocked by the DOCKER-USER DROP rule. |
| HTTPS to 1.1.1.1 | Same for TCP port 443. Separate test because some rules are written port-specifically. |
| TCP connect to 1.1.1.1:443 | Raw TCP via netcat — no HTTP overhead. Confirms TCP blocking at the socket level, not just at the HTTP layer. |
| UDP to 8.8.8.8:53 | Outbound UDP directly to a public DNS server, bypassing Docker's embedded resolver. Confirms UDP is blocked, not just TCP. |
| Gateway `<ip>:<port>` | From inside the container, connects to the Docker bridge gateway IP (the host's address on the container's virtual network, e.g. `<gateway-ip>`) on `HOST_PORT`. Because Docker has a port mapping from `HOST_PORT` on the host to the container's internal port, this loops back through the host to the container's own service. DOCKER-USER only filters traffic crossing from the bridge toward external interfaces — traffic to the bridge gateway never hits that chain and is always reachable. PASS in both modes confirms lockdown blocks outbound-only and doesn't accidentally break the inbound path callers use to reach the service. |
| Health check after outbound tests | Re-checks the service is still healthy after all the network probes. Guards against a test accidentally disrupting the container. |

The open vs. strict columns tell the story: every outbound test should flip from `(allowed)` to `(blocked)`. The gateway and health checks should show identical results in both columns. Any deviation is a bug.

## The service

`nettest.py` serves on the single exposed port (internal `9000`, published as
`HOST_PORT`):

- `GET /health` → `{"status": "ok"}` — used by the container healthcheck.
- `GET /` → an HTML page showing hostname, mode, protocol, and uptime.

It listens on http or https depending on `USE_HTTPS`. To build a real container,
replace the request handler with your service and keep the surrounding scaffolding.

## Files

| File | Purpose |
|------|---------|
| `setup` | Interactive installer: prompts for UID, port, lockdown mode, TLS, and restart policy; installs `docker-lockdown`; writes `.env`. Re-runnable — all prompts default from existing `.env`. |
| `start-container` | Starts the container (builds on first run), applies outbound lockdown (strict mode), and polls until the health check passes. Accepts `--open`, `--strict`, `--without-tools`, `--build`, `--working`. |
| `stop-container` | Stops the container and removes lockdown rules. In open mode, captures a resource snapshot and suggests `CPU_LIMIT`/`MEM_LIMIT` values for `.env`. |
| `security-check` | Verifies posture of a running container: iptables rules present/absent, PID 1 non-root with no capabilities, inbound health check reachable, outbound traffic blocked (strict) or allowed (open). |
| `security-compare` | Runs the container in open then strict mode back-to-back and prints a side-by-side PASS/FAIL/SKIP comparison table. Requires passwordless sudo for docker-lockdown. |
| `docker-lockdown` | Outbound iptables manager. Installed root-owned to a system path by `setup`. Commands: `apply`, `remove`, `cleanup`, `status`. The copy in this repo is the source of truth; `setup` installs it from here. |
| `docker-compose.yml` | Base service definition: port mapping, process hardening (`no-new-privileges`, `cap_drop: ALL`), read-only filesystem, sized tmpfs mounts, and healthcheck. Used in both modes. |
| `docker-compose.strict.yml` | Strict-mode overlay, merged with the base by `start-container --strict`. Adds `NET_ADMIN` (for in-container iptables) and CPU/memory/PID resource limits. |
| `Dockerfile` | Builds the image from `python:3.12-slim`. Diagnostic tools (`curl`, `dig`, `ping`, `nc`, `traceroute`, `wget`) are gated behind the `INCLUDE_TOOLS` build arg and included by default. |
| `entrypoint.sh` | Runs inside the container at startup. In strict mode, blocks Docker's embedded DNS resolver at `127.0.0.11` via iptables before dropping privileges. Then exec's the CMD as a non-root user via `setpriv`. |
| `nettest.py` | The reference service. Serves `GET /health` (JSON) and `GET /` (HTML status page) on the single exposed port. Supports HTTP and HTTPS via `USE_HTTPS`. Replace the request handler with your own service logic. |
| `healthcheck.py` | Polled by Docker's built-in healthcheck. Requests `GET /health` on the app port, handling self-signed TLS without verification (the cert is for the browser, not this probe). |
| `.env.template` | Documents the shape of `.env` — the variables `setup` will populate, with their defaults. Commit this; never commit `.env` itself. |
| `.gitignore` | Excludes `.env` (local config), `certs/` (generated TLS certs), and `__pycache__/` from version control. |

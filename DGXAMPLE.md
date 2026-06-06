> Snapshot of the [DGXample organization README](https://github.com/dgxample/.github/blob/main/profile/README.md) — 2026-06-06.

# DGXample

A collection of secure, standardized Docker container configurations for running AI models and services on the NVIDIA DGX Spark and similar systems. Each container in this organization follows the same operational pattern — one `./setup`, one `./start-container` — and the same security architecture.

## Why this exists

Most AI/ML projects assume an x86 host and a discrete GPU with separate VRAM. DGX Spark's ARM CPU and unified CPU-GPU memory break both assumptions — often silently, in ways that take real debugging to find. Containers here have already been through that. The code in these containers also comes from strangers on the internet. Therefore, DGXample treats it as untrusted and restricts it.

- **DGX Spark-tested.** Each container has been built and run on DGX Spark's ARM + unified memory architecture. Build failures, missing wheels, and architecture-specific patches are already resolved.
- **Two run modes.** `--open` allows outbound traffic (for setup tasks like downloading models or packages). `--strict` (default) blocks *all* container-initiated outbound traffic — nothing leaves unless you allow it.
- **Defense in depth.** Non-root via `setpriv`, all Linux capabilities dropped, read-only root filesystem, sized `tmpfs` for writable paths, an in-container DNS block, host-side `iptables` outbound lockdown, and resource limits.
- **Easy to reproduce.** One `./setup` prompts for everything and writes `.env`; `./start-container` builds, starts, and applies lockdown. Someone cloning a repo should get the same container running without the struggle.

## Requirements

- Linux host (iptables is Linux-only)
- Docker and Docker Compose v2 (`docker compose` — not the legacy `docker-compose`)
- sudo access (for iptables management in strict mode)

Most Linux systems already have everything else (`python3`, `openssl`, `setpriv`). The easiest approach is to just run `./setup` in any container repo and see if anything is missing.

## The service

Each container exists to run a service — a web application, an API, an AI model endpoint, or any networked process. The service is the point. Everything else in the repo is built around running that service safely: giving it what it needs to reach the network inbound, while restricting it from doing anything unwanted or unexpected outbound.

All services share the same interface conventions:

- They listen on a single port, published to the host as `HOST_PORT`.
- They expose a `GET /health` endpoint that returns 200 when healthy. Docker polls this to track container state; `./start-container` waits for it before declaring success.

The service process runs as a non-root user with no Linux capabilities. It cannot modify the container's filesystem (mounted read-only), cannot initiate outbound connections in strict mode, and is bounded by CPU, memory, and PID limits. What the service does within those constraints is its own business — what it cannot do is reach outside them.

## How containers work

Every container repo follows the same pattern:

```bash
./setup            # prompts for UID, port, lockdown, optional HTTPS; writes .env
./start-container  # start (builds on first run), apply lockdown (strict by default), wait for health
```

The URL (`http://` or `https://`) is printed once the container is healthy.

```bash
./stop-container   # stop and remove lockdown rules
```

### Run modes

```bash
./start-container            # strict (default) — blocks all outbound traffic
./start-container --open     # open — no outbound restrictions, no sudo needed
./start-container --build    # force a rebuild (required after Dockerfile or entrypoint changes)
./start-container --working  # start from the :working image (roll back after a broken build)
./start-container --without-tools  # rebuild without curl/dig/ping/nc (tools are included by default)
```

| Flag | Effect |
|------|--------|
| `--strict` | Blocks all container-initiated outbound traffic. Default. Requires sudo. |
| `--open` | No traffic restrictions. Process hardening still applies. No sudo needed. |
| `--build` | Force a docker compose build before starting. Skipped by default when the image already exists (BuildKit export/import adds several minutes even when all layers are cached). Before building, offers to save the current `:latest` as `:working` for easy rollback. |
| `--working` | Start from the `:working` image instead of `:latest`. Use to roll back after a broken build without retagging manually. |
| `--without-tools` | Excludes curl, dig, ping, nc, traceroute, wget. Triggers a rebuild. Default is to include them. |

The default security level is read from `.env`; the flags override it.

## Network lockdown

Strict mode combines two layers:

- **Host side:** `docker-lockdown` inserts rules into Docker's `DOCKER-USER` chain for the container's subnet, allowing established/related return traffic and dropping everything else outbound. `./setup` installs `docker-lockdown` to a root-owned path (default `/usr/local/bin/docker-lockdown`) so a sudoers entry for it is safe — the regular user cannot replace the script.
- **In container:** The entrypoint blocks Docker's embedded DNS at `127.0.0.11` before dropping privileges, closing the DNS-exfiltration path that host-side rules miss (Docker rewrites port 53 before the filter chain sees it).

```bash
sudo docker-lockdown status     # show active rules
sudo docker-lockdown cleanup    # remove orphaned rules from previous runs
```

### Passwordless sudo (optional, for automation)

Strict mode needs sudo to manage iptables. By default `start`/`stop` prompt for your password. If you want a dashboard or script to manage containers without a prompt, `./setup` can create a sudoers drop-in granting passwordless sudo for `docker-lockdown` only. The port-range validation in `docker-lockdown` bounds what that grant can do.

## HTTPS / TLS

`./setup` offers three choices:

1. **Shared host certificate (preferred)** — one cert at `~/.local/share/certs` by default (configurable during setup), reused by every container on the host. Trust it once in your browser/OS and all containers are covered. Setup prints OS-trust-store instructions (needed so the browser's *download manager*, not just page navigation, trusts it).
2. **Per-container certificate** — generated in `./certs`, used only by that container.
3. **None** — plain HTTP.

The cert is generated on the host during setup, so its fingerprint is stable: you accept the browser warning once, not on every restart.

## Resource limits

Strict mode caps CPU, memory, PIDs, and tmpfs sizes to bound a runaway or compromised container. `./setup` writes sensible defaults to `.env`, so strict mode starts immediately. To tighten them to measured usage:

1. `./start-container --open` and exercise the service.
2. `./stop-container` — prints a usage snapshot and suggested `.env` values with headroom applied.
3. Paste the values into `.env`, then `./start-container --strict`.

For more accurate readings, run `docker stats <container-name>` while it's under load.

## Verification

```bash
./security-check              # run posture checks against the running container
./security-compare            # run open vs strict back-to-back, diff side by side
```

`security-check` verifies process hardening and network posture and prints a PASS/FAIL/SKIP result for each check. Tests needing diagnostic tools (`dig`, `ping`, `curl`, `nc`) are skipped if the image was built with `--without-tools`.

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
| Gateway `<ip>:<port>` | From inside the container, connects to the Docker bridge gateway IP (the host's address on the container's virtual network) on the published host port. DOCKER-USER only filters traffic crossing from the bridge toward external interfaces — traffic to the bridge gateway never hits that chain and is always reachable. PASS in both modes confirms lockdown blocks outbound-only and doesn't accidentally break the inbound path callers use to reach the service. |
| Health check after outbound tests | Re-checks the service is still healthy after all the network probes. Guards against a test accidentally disrupting the container. |

The open vs. strict columns tell the story: every outbound test should flip from `(allowed)` to `(blocked)`. The gateway and health checks should show identical results in both columns. Any deviation is a bug.

## Common files

Every container repo includes this scaffolding:

| File | Purpose |
|------|---------|
| `setup` | Interactive installer: prompts for UID, port, lockdown mode, TLS, and restart policy; installs `docker-lockdown`; writes `.env`. Re-runnable — all prompts default from existing `.env`. |
| `start-container` | Builds the image, starts the container, applies outbound lockdown (strict mode), and polls until the health check passes. |
| `stop-container` | Stops the container and removes lockdown rules. In open mode, captures a resource snapshot and suggests resource limit values for `.env`. |
| `security-check` | Verifies posture of a running container: iptables rules present/absent, PID 1 non-root with no capabilities, inbound health check reachable, outbound traffic blocked (strict) or allowed (open). |
| `security-compare` | Runs the container in open then strict mode back-to-back and prints a side-by-side PASS/FAIL/SKIP comparison table. |
| `docker-lockdown` | Outbound iptables manager, installed root-owned to a system path by `setup`. Shared across all containers on the host. |
| `docker-compose.yml` | Base service definition: port mapping, process hardening, read-only filesystem, sized tmpfs mounts, and healthcheck. |
| `docker-compose.strict.yml` | Strict-mode overlay: adds `NET_ADMIN` (for in-container iptables) and CPU/memory/PID resource limits. |
| `Dockerfile` | Builds the image. Diagnostic tools are gated behind `INCLUDE_TOOLS` and included by default. |
| `entrypoint.sh` | Runs at container startup: blocks Docker's embedded DNS in strict mode, then drops to non-root via `setpriv`. |
| `.env.template` | Documents the variables `setup` will populate, with their defaults. |
| `.gitignore` | Excludes `.env`, generated TLS certs, and cache directories. |

Each container repo also contains its own service implementation and healthcheck.

## Containers

| Repo | Description |
|------|-------------|
| [dgx-nettest](https://github.com/dgxample/dgx-nettest) | Reference container. Runs a minimal web service so the security and operational scaffolding is easy to read and copy. Also serves as a network-isolation test harness to verify strict mode actually blocks outbound traffic. |

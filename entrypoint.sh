#!/bin/bash
set -e

# In strict mode, block Docker's embedded DNS (127.0.0.11) to prevent DNS exfiltration.
#
# Docker intercepts DNS via NAT rules in the DOCKER_OUTPUT chain, which DNAT
# port 53 to a random high port BEFORE the filter OUTPUT chain runs. Blocking
# by destination port 53 does nothing — by the time our filter rules see the
# packet, the port has already been rewritten. Instead, block ALL traffic to
# 127.0.0.11 regardless of port. Nothing else legitimate lives at that address.
if [ "${SECURITY_LEVEL:-strict}" = "strict" ]; then
    iptables -A OUTPUT -d 127.0.0.11 -j DROP

    # IPv6 is disabled on this network (enable_ipv6: false in docker-compose.yml).
    # If you enable IPv6, uncomment the line below to enforce the same DNS block.
    # ip6tables -A OUTPUT -d 127.0.0.11 -j DROP
fi

# Drop to unprivileged user and exec the CMD.
# setpriv works under no-new-privileges (unlike gosu/su-exec).
# After this call, NET_ADMIN/SETUID/SETGID are cleared from effective+permitted sets.
exec setpriv --reuid=containeruser --regid=containeruser --clear-groups --inh-caps=-all --bounding-set=-all "$@"

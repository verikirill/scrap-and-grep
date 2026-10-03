#!/bin/sh
# EGRESS_UPSTREAM=host:port sends everything through the corporate proxy.
set -eu
upstream=/etc/squid/upstream.conf
: > "$upstream"
if [ -n "${EGRESS_UPSTREAM:-}" ]; then
  host=${EGRESS_UPSTREAM%:*}
  port=${EGRESS_UPSTREAM##*:}
  {
    echo "cache_peer $host parent $port 0 no-query no-digest default"
    echo "never_direct allow all"
  } > "$upstream"
fi
mkdir -p /var/log/squid
touch /var/log/squid/access.log /var/log/squid/cache.log
chown -R squid:squid /var/log/squid
# Every request the stack sends out, in the container's log.
tail -qF /var/log/squid/access.log /var/log/squid/cache.log &
exec squid -N -f /etc/squid/squid.conf

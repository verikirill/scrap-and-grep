# The stack's only way out in a closed network (docker-compose.airgap.yml): a
# forward proxy that reaches public addresses only, alone or through the
# corporate proxy. It resolves the names itself; the stack resolves none.
FROM alpine:3.22
RUN apk add --no-cache squid \
    && mkdir -p /run/squid \
    && chown squid:squid /run/squid
COPY squid.conf /etc/squid/squid.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 3128
ENTRYPOINT ["/entrypoint.sh"]

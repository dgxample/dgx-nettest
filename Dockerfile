FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       iptables \
    && rm -rf /var/lib/apt/lists/*

ARG INCLUDE_TOOLS=true
RUN if [ "$INCLUDE_TOOLS" = "true" ]; then \
      apt-get update \
      && apt-get install -y --no-install-recommends \
         curl \
         dnsutils \
         iputils-ping \
         iproute2 \
         netcat-openbsd \
         traceroute \
         wget \
      && rm -rf /var/lib/apt/lists/*; \
    fi

ARG CONTAINER_UID
RUN groupadd -g ${CONTAINER_UID} containeruser \
    && useradd -s /bin/nologin -u ${CONTAINER_UID} -g ${CONTAINER_UID} containeruser

WORKDIR /app

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY healthcheck.py /healthcheck.py
COPY nettest.py .

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "nettest.py"]

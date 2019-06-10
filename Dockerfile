FROM jrottenberg/ffmpeg:4.0

LABEL maintainer="wtollett@usgs.gov"

RUN apt-get update \
    && apt-get install -y python3-pip libcurl4-openssl-dev libssl-dev

ENV SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/v0.1.8/supercronic-linux-amd64 \
    SUPERCRONIC=supercronic-linux-amd64 \
    SUPERCRONIC_SHA1SUM=be43e64c45acd6ec4fce5831e03759c89676a0ea

RUN apt-get install -y curl

RUN curl -fsSLO "$SUPERCRONIC_URL" \
 && echo "${SUPERCRONIC_SHA1SUM}  ${SUPERCRONIC}" | sha1sum -c - \
 && chmod +x "$SUPERCRONIC" \
 && mv "$SUPERCRONIC" "/usr/local/bin/${SUPERCRONIC}" \
 && ln -s "/usr/local/bin/${SUPERCRONIC}" /usr/local/bin/supercronic

WORKDIR /app/1fps
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY support/bin /app/1fps/bin

COPY VERSION .

ENTRYPOINT ["/usr/local/bin/supercronic", "-overlapping", "/app/1fps/etc/1fps.cron"]
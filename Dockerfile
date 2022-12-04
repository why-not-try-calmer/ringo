# builder
FROM python:3.10-bullseye as builder
RUN apt-get update && apt upgrade -y && pip install pipenv

WORKDIR /opt/app
COPY ./requirements.txt .

ENV PIPENV_VENV_IN_PROJECT=1
RUN pipenv install

# Azure handles TLS
# RUN openssl req -subj \
#     "/C=CH/ST=Bern/L=Bern/O=WhoCares /OU=Again/CN=SoNosey" \
#     -newkey rsa:2048 -sha256 -nodes \
#     -keyout private.key -x509 -days 3650 -out cert.pem

# runner
FROM python:3.10-slim-bullseye
WORKDIR /opt/app

# runnable code
COPY . .
COPY --from=builder /opt/app/.venv/ .venv/

# Azure handles TLS
# COPY --from=builder /opt/app/cert.pem cert.pem
# COPY --from=builder /opt/app/private.key private.key

CMD . .venv/bin/activate && python -m app

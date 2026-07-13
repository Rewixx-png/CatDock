#!/bin/bash

NGINX_SITES_AVAILABLE="/etc/nginx/sites-available"
NGINX_SITES_ENABLED="/etc/nginx/sites-enabled"
BASE_DOMAIN="catdock.io" 

SSL_CERTIFICATE="/etc/letsencrypt/live/catdock.io-0001/fullchain.pem"
SSL_CERTIFICATE_KEY="/etc/letsencrypt/live/catdock.io-0001/privkey.pem"

if [ "$(id -u)" -ne 0 ]; then
  echo "Error: This script must be run as root." >&2
  exit 1
fi

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <subdomain> <proxy_ip> <proxy_port>" >&2
    exit 1
fi

SUBDOMAIN=$1
PROXY_IP=$2
PROXY_PORT=$3
FULL_DOMAIN="${SUBDOMAIN}.${BASE_DOMAIN}"
CONF_FILE="${NGINX_SITES_AVAILABLE}/${FULL_DOMAIN}.conf"

if ! [[ "$PROXY_PORT" =~ ^[0-9]+$ ]]; then
    echo "Error: Port must be a number." >&2
    exit 1
fi

echo "Creating Nginx config for ${FULL_DOMAIN} -> http://${PROXY_IP}:${PROXY_PORT} with SSL"

cat > "$CONF_FILE" <<EOF
server {
    listen 80;
    server_name ${FULL_DOMAIN};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ${FULL_DOMAIN};

    ssl_certificate ${SSL_CERTIFICATE};
    ssl_certificate_key ${SSL_CERTIFICATE_KEY};

    client_max_body_size 100M;
    proxy_connect_timeout 600;
    proxy_send_timeout 600;
    proxy_read_timeout 600;
    send_timeout 600;

    location / {
        proxy_pass http://${PROXY_IP}:${PROXY_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

echo "Activating site..."
if [ ! -L "${NGINX_SITES_ENABLED}/${FULL_DOMAIN}.conf" ]; then
    ln -s "$CONF_FILE" "${NGINX_SITES_ENABLED}/"
fi

echo "Testing Nginx configuration..."
nginx -t
if [ $? -ne 0 ]; then
    echo "Error: Nginx configuration test failed. Please check the logs." >&2
    rm "$CONF_FILE" 
    exit 1
fi

echo "Reloading Nginx..."
systemctl reload nginx

echo "Done."

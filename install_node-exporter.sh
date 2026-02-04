#!/bin/bash

set -e

# ================= CONFIG =================
NODE_EXPORTER_VERSION="1.6.1"
NODE_EXPORTER_PORT=8080
# =========================================

echo "==> Installing Node Exporter version $NODE_EXPORTER_VERSION"

# Download Node Exporter
wget https://github.com/prometheus/node_exporter/releases/download/v$NODE_EXPORTER_VERSION/node_exporter-$NODE_EXPORTER_VERSION.linux-amd64.tar.gz -O /tmp/node_exporter.tar.gz

# Extract
tar -xzf /tmp/node_exporter.tar.gz -C /tmp

# Move binary
sudo mv /tmp/node_exporter-$NODE_EXPORTER_VERSION.linux-amd64/node_exporter /usr/local/bin/

# Create node_exporter user
sudo useradd --no-create-home --shell /bin/false node_exporter || true

# Set permissions
sudo chown node_exporter:node_exporter /usr/local/bin/node_exporter

# Create systemd service
sudo tee /etc/systemd/system/node_exporter.service > /dev/null <<EOF
[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter --web.listen-address=:$NODE_EXPORTER_PORT

[Install]
WantedBy=default.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable node_exporter
sudo systemctl start node_exporter

echo "✅ Node Exporter installed and running on port $NODE_EXPORTER_PORT"
echo "Check status: sudo systemctl status node_exporter"

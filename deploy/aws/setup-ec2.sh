#!/usr/bin/env bash
set -euo pipefail

# Run on a fresh Ubuntu EC2 instance.
sudo apt-get update
sudo apt-get install -y ca-certificates curl git docker.io
if ! sudo apt-get install -y docker-compose-v2; then
  sudo apt-get install -y docker-compose-plugin
fi
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

echo "EC2 setup complete. Sign out and reconnect so Docker group membership applies."
echo "Then clone the repository and follow deploy/aws/README.md."

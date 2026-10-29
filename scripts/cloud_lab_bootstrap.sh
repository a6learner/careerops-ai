#!/usr/bin/env bash
set -euo pipefail

# This installer is only for the new, author-provisioned Ubuntu learning VM.
source /etc/os-release
if [[ "$ID" != ubuntu || "$VERSION_CODENAME" != noble || "$(uname -m)" != x86_64 ]]; then
  echo 'Expected the Ubuntu 24.04 x86_64 cloud lab; no installation performed.' >&2
  exit 1
fi
sudo -n true
sudo apt-get update
sudo apt-get install -y ca-certificates curl python3
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $VERSION_CODENAME
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker version --format 'Docker server: {{.Server.Version}}'
sudo docker compose version

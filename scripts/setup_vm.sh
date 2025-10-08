#!/bin/bash

# This script installs the NVIDIA GPU driver (Google Cloud recommended),
# Docker Engine, the NVIDIA Container Toolkit, and adds the current user
# to the docker group. Reboot may occur during driver installation.
#
# Assumptions: Ubuntu-based Google Cloud VM with an attached NVIDIA GPU.
# Idempotent where possible — re-run after any reboot to continue.
# Prerequisites: ~40 GB free on boot disk, Python 3 installed.

set -e

echo "[setup_vm] Starting setup on $(lsb_release -ds 2>/dev/null || cat /etc/os-release | head -n1)"

# --- helpers ---
check_driver_installed() {
    if command -v nvidia-smi &> /dev/null && nvidia-smi &> /dev/null; then
        echo "[setup_vm] NVIDIA driver is already installed."
        return 0
    else
        return 1
    fi
}

check_docker_installed() {
    if command -v docker &> /dev/null; then
        echo "[setup_vm] Docker is already installed."
        return 0
    else
        return 1
    fi
}

check_toolkit_installed() {
    if command -v nvidia-ctk &> /dev/null; then
        echo "[setup_vm] NVIDIA Container Toolkit is already installed."
        return 0
    else
        return 1
    fi
}

# --- system update ---
sudo apt update && sudo apt upgrade -y

# Stop Google Cloud Ops Agent if running (prereq for driver install)
sudo systemctl stop google-cloud-ops-agent || true

# --- Step 1: NVIDIA GPU driver ---
if ! check_driver_installed; then
    echo "[setup_vm] Installing NVIDIA GPU driver via Google Cloud installer..."
    curl -L https://storage.googleapis.com/compute-gpu-installation-us/installer/latest/cuda_installer.pyz --output cuda_installer.pyz
    sudo python3 cuda_installer.pyz install_driver --installation-mode=repo --installation-branch=prod
    echo "[setup_vm] Rebooting VM to complete driver installation..."
    sudo reboot
    exit 0
fi

# Verify driver
nvidia-smi || { echo "[setup_vm] nvidia-smi failed after supposed install" >&2; exit 1; }

# --- Step 2: Docker Engine ---
if ! check_docker_installed; then
    echo "[setup_vm] Installing Docker Engine..."
    # Remove older variants if present
    for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do sudo apt-get remove -y "$pkg" || true; done

    # Install prerequisites and repo key
    sudo apt-get install -y ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    # Add repo
    echo \
"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
$(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Verify Docker with hello-world (optional)
    sudo docker run --rm hello-world || true
fi

# --- Step 3: NVIDIA Container Toolkit ---
if ! check_toolkit_installed; then
    echo "[setup_vm] Installing NVIDIA Container Toolkit..."
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
        sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

    sudo apt-get update
    sudo apt-get install -y nvidia-container-toolkit
fi

# Configure Docker runtime and restart
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# --- Step 4: Docker group ---
if groups "$USER" | grep -q '\bdocker\b'; then
    echo "[setup_vm] User $USER already in docker group."
else
    sudo usermod -aG docker "$USER"
    echo "[setup_vm] Added $USER to docker group. Log out and back in (or run 'newgrp docker')."
fi

cat <<'EOT'
[setup_vm] Setup complete.

Verification:
- Driver:        nvidia-smi
- GPU in Docker: docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi

If the script triggered a reboot earlier, re-run it after login to finish remaining steps.
EOT


#!/bin/bash
set -e

echo "=== AgriSense Setup ==="
echo "Installs Minikube, kubectl, and KEDA"

OS=$(uname -s)

install_macos() {
    if ! command -v brew &> /dev/null; then
        echo "Homebrew not found. Install from https://brew.sh first."
        exit 1
    fi
    command -v minikube &> /dev/null || brew install minikube
    command -v kubectl  &> /dev/null || brew install kubectl
}

install_linux() {
    if ! command -v minikube &> /dev/null; then
        echo "Installing Minikube..."
        curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
        sudo install minikube-linux-amd64 /usr/local/bin/minikube
        rm minikube-linux-amd64
    fi
    if ! command -v kubectl &> /dev/null; then
        echo "Installing kubectl..."
        curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
        sudo install kubectl /usr/local/bin/kubectl
        rm kubectl
    fi
}

case "$OS" in
    Darwin) install_macos ;;
    Linux)  install_linux ;;
    *)      echo "Unsupported OS: $OS"; exit 1 ;;
esac

echo "Starting Minikube..."
# Docker Desktop on dev machines is often capped around 4 GB; ask for a hair
# less so minikube doesn't refuse to start. Bump these in Docker Desktop
# Settings -> Resources if you want more headroom for the cluster.
minikube start --memory=3500 --cpus=2 --driver=docker

echo "Enabling addons..."
minikube addons enable metrics-server
minikube addons enable ingress

echo "Installing KEDA..."
kubectl apply --server-side -f https://github.com/kedacore/keda/releases/download/v2.13.0/keda-2.13.0.yaml

echo "Waiting for KEDA to be ready..."
kubectl wait --for=condition=ready pod -l app=keda-operator -n keda --timeout=180s

echo ""
echo "=== Setup complete ==="
echo "Next:"
echo "  ./scripts/build-and-push.sh   # build images into Minikube"
echo "  ./scripts/deploy.sh           # deploy AgriSense"

#!/bin/bash
# RFSN Controller - macOS Docker Build Script
# This script builds the Docker image for the RFSN Controller on macOS

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="${IMAGE_NAME:-rfsn-controller}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "=============================================="
echo "RFSN Controller - Docker Build for macOS"
echo "=============================================="
echo ""

# Check Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker Desktop for macOS."
    echo "   Download from: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

# Check Docker daemon is running
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running. Please start Docker Desktop."
    exit 1
fi

echo "✓ Docker is available and running"
echo ""

# Build for both architectures (M1/M2 ARM and Intel)
echo "Building Docker image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "Platform: linux/amd64,linux/arm64 (multi-platform)"
echo ""

cd "$SCRIPT_DIR"

# Build the image
docker build \
    --platform linux/amd64 \
    -t "${IMAGE_NAME}:${IMAGE_TAG}" \
    -f Dockerfile \
    .

echo ""
echo "=============================================="
echo "✓ Build completed successfully!"
echo "=============================================="
echo ""
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "To run the controller:"
echo "  docker run -it ${IMAGE_NAME}:${IMAGE_TAG} --help"
echo ""
echo "To run with docker-compose:"
echo "  export GEMINI_API_KEY=your_api_key"
echo "  docker-compose up rfsn"
echo ""

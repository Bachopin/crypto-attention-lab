#!/bin/bash

# Crypto Attention Lab - Quick Start Script
# This script helps you get the web frontend running quickly

echo "🚀 Crypto Attention Lab - Web Frontend Setup"
echo "=============================================="
echo ""

# Check Node.js version
echo "📋 Checking prerequisites..."
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js >= 18.0.0"
    echo "   Visit: https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js version must be >= 18.0.0. Current: $(node -v)"
    exit 1
fi

echo "✅ Node.js $(node -v)"
echo "✅ npm $(npm -v)"
echo ""

# Navigate to web directory
cd "$(dirname "$0")/web" || exit

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
    echo ""
else
    echo "✅ Dependencies already installed"
    echo ""
fi

# Create .env.local if it doesn't exist
if [ ! -f ".env.local" ]; then
    echo "⚙️  Creating .env.local from example..."
    cp .env.example .env.local
    echo "✅ Created .env.local"
    echo ""
fi

echo "🎉 Setup complete!"
echo ""
echo "🚀 Starting development server (Turbopack)..."
echo "   Frontend will be available at: http://localhost:3000"
echo ""
echo "   Press Ctrl+C to stop the server"
echo ""
echo "=============================================="
echo ""

# Start dev server on fixed port 3000 (free if occupied)
# Note: npm run dev already includes --turbopack for faster startup
if lsof -ti tcp:3000 >/dev/null 2>&1; then
    echo "⚠ Port 3000 is in use. Freeing it..."
    lsof -ti tcp:3000 | xargs -r kill -9
    sleep 1
fi
npm run dev -- -p 3000

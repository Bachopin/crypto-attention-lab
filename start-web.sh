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
echo "🚀 Starting development server..."
echo "   Frontend will be available at: http://localhost:3000"
echo ""
echo "   Press Ctrl+C to stop the server"
echo ""
echo "=============================================="
echo ""

# Start dev server
npm run dev

#!/bin/bash

echo "🧹 Starting cleanup process..."

# Kill all processes on port 8000
echo "🔌 Killing processes on port 8000..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || echo "No processes found on port 8000"

# Kill all Chrome processes
echo "🌐 Killing Chrome processes..."
pkill -f "Google Chrome" 2>/dev/null || echo "No Chrome processes found"
pkill -f "chrome" 2>/dev/null || echo "No chrome processes found"
pkill -f "chromium" 2>/dev/null || echo "No chromium processes found"

# Kill Chrome helper processes
echo "🔧 Killing Chrome helper processes..."
pkill -f "Chrome Helper" 2>/dev/null || echo "No Chrome Helper processes found"
pkill -f "ChromeDriver" 2>/dev/null || echo "No ChromeDriver processes found"

# Kill any remaining browser processes that might be hanging
echo "🕷️ Killing any remaining browser processes..."
pkill -f "WebDriver" 2>/dev/null || echo "No WebDriver processes found"
pkill -f "selenium" 2>/dev/null || echo "No selenium processes found"

echo "✅ Cleanup complete!"

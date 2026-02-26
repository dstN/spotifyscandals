#!/bin/bash
echo "Starting Backend..."
cd backend
./venv/Scripts/python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
read -p "Backend stopped. Press enter to close..."

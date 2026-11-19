#!/bin/bash

echo "--- Building Project ---"
make clean
make

echo "--- Starting Server ---"
# Run the server in the background (&)
./server &
SERVER_PID=$!

echo "Server is running in the background (PID: $SERVER_PID)"
echo "You can now open new terminal tabs and run: ./client"
echo "Press [ENTER] to kill the server and exit."

# Wait for you to press Enter, then kill the background server cleanly
read -p ""
kill $SERVER_PID
echo "Server shut down."
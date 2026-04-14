#!/bin/bash
# Start encoder in the background (&)
python3 encoder.py & 

# Store its process ID so we can kill it later
ENCODER_PID=$!

# Start display in the foreground
python3 display.py

# Once you Ctrl+C the display, kill the encoder background task
kill $ENCODER_PID
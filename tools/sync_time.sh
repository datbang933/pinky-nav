#!/bin/bash
# Run this yourself in a terminal (needs the robot's sudo password). Sets the robot clock from the laptop.
source "$(dirname "$(readlink -f "$0")")/pinky_env.sh"
pgrep -f "tools/timeserver.py" >/dev/null || (setsid nohup python3 $PINKY_TOOLS/timeserver.py >/dev/null 2>&1 </dev/null &)
sleep 1
ssh -t $PINKY_HOST "sudo -v && sudo date -s @\$(curl -s http://$LAPTOP_IP:8765)"

# common settings (sourced by the other scripts)
export PINKY_TOOLS="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
# robot address: env PINKY_IP, else tools/robot_ip.txt (git-ignored, one line), else the robot AP default 192.168.4.1
export PINKY_IP=${PINKY_IP:-$(cat "$PINKY_TOOLS/robot_ip.txt" 2>/dev/null || echo 192.168.4.1)}
export PINKY_HOST=${PINKY_HOST:-pinky@$PINKY_IP}
export ROS_DOMAIN_ID=1
# Some Wi-Fi networks block DDS multicast discovery -> talk to the robot by unicast as well
export ROS_STATIC_PEERS=$PINKY_IP
source /opt/ros/jazzy/setup.bash
export PINKY_TOOLS="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
export PINKY_ROOT="$(dirname "$PINKY_TOOLS")"
source "$PINKY_ROOT/install/setup.bash"
export LAPTOP_IP=$(ip route get $PINKY_IP | sed -n 's/.* src \([0-9.]*\).*/\1/p' | head -n1)

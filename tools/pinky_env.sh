# common settings (sourced by the other scripts)
export PINKY_HOST=${PINKY_HOST:-pinky@192.168.4.1}
export ROS_DOMAIN_ID=1
source /opt/ros/jazzy/setup.bash
export PINKY_TOOLS="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
export PINKY_ROOT="$(dirname "$PINKY_TOOLS")"
source "$PINKY_ROOT/install/setup.bash"
export LAPTOP_IP=$(ip route get 192.168.4.1 | sed -n 's/.* src \([0-9.]*\).*/\1/p' | head -n1)

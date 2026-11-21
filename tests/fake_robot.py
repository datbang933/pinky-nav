"""Fake robot side for integration testing without hardware: /set_led service, navigate_to_pose action, /map.
Use a private ROS_DOMAIN_ID (e.g. 77):  python3 tests/fake_robot.py"""
import math, time, rclpy
from rclpy.node import Node
from rclpy.action import ActionServer
from rclpy.executors import MultiThreadedExecutor
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from nav_msgs.msg import OccupancyGrid
from nav2_msgs.action import NavigateToPose
from pinky_interfaces.srv import SetLed


class Fake(Node):
    def __init__(self):
        super().__init__('fake_robot')
        self.create_service(SetLed, 'set_led', self.led)
        ActionServer(self, NavigateToPose, 'navigate_to_pose', self.nav)
        self.pub = self.create_publisher(OccupancyGrid, 'map', QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        m = OccupancyGrid(); m.header.frame_id = 'map'
        m.info.resolution, m.info.width, m.info.height = 0.05, 60, 60       # 3 m x 3 m, all free
        m.info.origin.position.x = m.info.origin.position.y = -0.5
        m.data = [0] * (60 * 60); self.pub.publish(m)

    def led(self, req, res):
        print(f'LED {req.command} ({req.r},{req.g},{req.b})', flush=True); res.success = True; res.message = 'ok'; return res

    def nav(self, gh):
        p = gh.request.pose.pose.position
        print(f'NAV goal ({p.x:.2f},{p.y:.2f}) accepted', flush=True)
        time.sleep(2.0)
        gh.succeed(); print('NAV done', flush=True); return NavigateToPose.Result()


rclpy.init(); n = Fake(); ex = MultiThreadedExecutor(); ex.add_node(n)
try: ex.spin()
except KeyboardInterrupt: pass

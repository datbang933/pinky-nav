#!/usr/bin/env python3
"""Pinky navigation API.  Usage from your own Python code:

    from pinky_nav import PinkyNav
    nav = PinkyNav()
    nav.goto_place('A')            # named place from tools/places.yaml  (blocks until arrival)
    nav.goto(0.8, -0.5, yaw=0.0)   # map-frame x, y [m], yaw [rad]
    nav.goto_place('B', wait=False); ...; nav.cancel()

Event example (python3 tools/pinky_nav.py listen):  publish a String on /pinky/event, e.g.
    ros2 topic pub --once /pinky/event std_msgs/msg/String "{data: 'goto:A'}"
"""
import math, os, sys, time, threading, yaml
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from action_msgs.msg import GoalStatus
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener

PLACES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'places.yaml')

class PinkyNav(Node):
    def __init__(self, places_file=PLACES):
        if not rclpy.ok(): rclpy.init()
        super().__init__('pinky_nav_api')
        self.places = yaml.safe_load(open(places_file)) if os.path.exists(places_file) else {}
        self._ac = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self._tf = Buffer(); TransformListener(self._tf, self)
        self._goal = None
        self._ex = SingleThreadedExecutor(); self._ex.add_node(self)
        threading.Thread(target=self._ex.spin, daemon=True).start()   # background spin -> blocking calls are safe
        if not self._ac.wait_for_server(15): raise RuntimeError('Nav2 navigate_to_pose not available')

    def pose(self):
        """current (x, y, yaw) in map frame, or None"""
        try:
            t = self._tf.lookup_transform('map', 'base_footprint', rclpy.time.Time()); q = t.transform.rotation
            return (t.transform.translation.x, t.transform.translation.y,
                    math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z)))
        except Exception: return None

    def goto(self, x, y, yaw=0.0, wait=True, timeout=120.0):
        """returns True on arrival (wait=True), or True if the goal was accepted (wait=False)"""
        g = NavigateToPose.Goal(); g.pose.header.frame_id = 'map'; g.pose.header.stamp = self.get_clock().now().to_msg()
        g.pose.pose.position.x = float(x); g.pose.pose.position.y = float(y)
        g.pose.pose.orientation.z = math.sin(yaw/2); g.pose.pose.orientation.w = math.cos(yaw/2)
        fut = self._ac.send_goal_async(g)
        while not fut.done(): time.sleep(0.02)
        self._goal = fut.result()
        if not self._goal.accepted: self.get_logger().warn('goal rejected'); return False
        if not wait: return True
        res = self._goal.get_result_async(); t0 = time.time()
        while not res.done():
            if time.time()-t0 > timeout: self.cancel(); return False
            time.sleep(0.05)
        return res.result().status == GoalStatus.STATUS_SUCCEEDED

    def goto_place(self, name, **kw):
        if name not in self.places: raise KeyError(f'unknown place {name!r}; known: {list(self.places)}')
        p = self.places[name]; return self.goto(p['x'], p['y'], p.get('yaw', 0.0), **kw)

    def cancel(self):
        if self._goal: self._goal.cancel_goal_async()

    def listen(self, topic='/pinky/event'):
        """event loop: String 'goto:<place>' | 'goto:<x>,<y>[,<yaw>]' | 'cancel'"""
        def cb(m):
            cmd = m.data.strip(); self.get_logger().info(f'event: {cmd}')
            if cmd == 'cancel': self.cancel(); return
            if cmd.startswith('goto:'):
                arg = cmd[5:]
                def run():
                    try:
                        ok = self.goto_place(arg) if arg in self.places else self.goto(*[float(v) for v in arg.split(',')])
                        self.get_logger().info(f'{cmd} -> {"arrived" if ok else "FAILED"}')
                    except Exception as e: self.get_logger().error(str(e))
                threading.Thread(target=run, daemon=True).start()
        self.create_subscription(String, topic, cb, 10)
        self.get_logger().info(f'listening on {topic}; places: {list(self.places)}')
        try:
            while rclpy.ok(): time.sleep(0.5)
        except KeyboardInterrupt: self.cancel()

if __name__ == '__main__':
    nav = PinkyNav()
    if len(sys.argv) > 1 and sys.argv[1] == 'listen': nav.listen()
    elif len(sys.argv) > 2 and sys.argv[1] == 'go': print('arrived' if nav.goto_place(sys.argv[2]) else 'failed')
    else: print(__doc__)

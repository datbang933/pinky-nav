#!/usr/bin/env python3
"""usage: set_initial_pose.py X Y YAW_RAD  (map frame) ; waits until map->base TF exists"""
import sys,rclpy,math,time
from rclpy.qos import QoSProfile,ReliabilityPolicy,DurabilityPolicy
from geometry_msgs.msg import PoseWithCovarianceStamped
from tf2_ros import Buffer,TransformListener
x,y,th=map(float,sys.argv[1:4])
rclpy.init(); n=rclpy.create_node('ip'); b=Buffer(); TransformListener(b,n)
pub=n.create_publisher(PoseWithCovarianceStamped,'initialpose',QoSProfile(depth=1,reliability=ReliabilityPolicy.RELIABLE,durability=DurabilityPolicy.TRANSIENT_LOCAL))
t0=time.time()
while pub.get_subscription_count()==0 and time.time()-t0<10: rclpy.spin_once(n,timeout_sec=0.2)
m=PoseWithCovarianceStamped(); m.header.frame_id='map'; m.pose.pose.position.x=x; m.pose.pose.position.y=y
m.pose.pose.orientation.z=math.sin(th/2); m.pose.pose.orientation.w=math.cos(th/2); m.pose.covariance[0]=m.pose.covariance[7]=0.05; m.pose.covariance[35]=0.05
for _ in range(3): m.header.stamp=n.get_clock().now().to_msg(); pub.publish(m); rclpy.spin_once(n,timeout_sec=0.5)
for _ in range(150):
    rclpy.spin_once(n,timeout_sec=0.1)
    try:
        t=b.lookup_transform('map','base_footprint',rclpy.time.Time()); p=t.transform.translation; print('AMCL map->base: %.2f %.2f (set %.2f %.2f)'%(p.x,p.y,x,y)); break
    except Exception: pass
else: print('no tf yet')

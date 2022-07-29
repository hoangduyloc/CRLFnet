#include <ros/ros.h>
#include <geometry_msgs/Twist.h>
#include <nav_msgs/Odometry.h>
#include "sensor_msgs/LaserScan.h"
#include "ackermann_msgs/AckermannDriveStamped.h"
#include "pkg/status.h"
#include "tf/tf.h"

#define PI 3.1415926535

ros::Publisher slave_vel;
ackermann_msgs::AckermannDriveStamped vel_msg;
std::string leader_name;
std::string follower1;
std::string follower2;
std::string follower3;
std::string follower4;
int isformation;

nav_msgs::Odometry ldmsg,f1msg,msg1,msg2,msg3,msg4,msg5;
bool pose_flag = false;

int overtake_phase = 1;

double getmodule(geometry_msgs::Vector3 v);

//Function declerations to move
void avoid(void);
void rotate (double angular_speed, double relative_angle, bool clockwise);
void overtake (void);
void follow (void);


//Call back function decleration
void laserCallBack(const sensor_msgs::LaserScan::ConstPtr & laser_msg); 
void statusCallBack(const pkg::status::ConstPtr & status_msg);
void poseCallback1(const nav_msgs::Odometry::ConstPtr& msg);
void poseCallback2(const nav_msgs::Odometry::ConstPtr& msg);
void poseCallback3(const nav_msgs::Odometry::ConstPtr& msg);
void poseCallback4(const nav_msgs::Odometry::ConstPtr& msg);
void poseCallback5(const nav_msgs::Odometry::ConstPtr& msg);

int main(int argc, char** argv)
{
  ros::init(argc, argv, "follower1");

  ros::NodeHandle node;

  ros::Subscriber platoon_status = node.subscribe("/status", 1, statusCallBack);
  ros::Subscriber pose1 = node.subscribe("/deepracer1/base_pose_ground_truth", 10, poseCallback1);
  ros::Subscriber pose2 = node.subscribe("/deepracer2/base_pose_ground_truth", 10, poseCallback2);
  ros::Subscriber pose3 = node.subscribe("/deepracer3/base_pose_ground_truth", 10, poseCallback3);
  ros::Subscriber pose4 = node.subscribe("/deepracer4/base_pose_ground_truth", 10, poseCallback4);
  ros::Subscriber pose5 = node.subscribe("/deepracer5/base_pose_ground_truth", 10, poseCallback5);
  
  ros::Rate rate(100.0);
  while (ros::ok())
  {
    ros::spinOnce();
    if(follower1!="")
    {
      slave_vel =
      node.advertise<ackermann_msgs::AckermannDriveStamped>(follower1+"/ackermann_cmd_mux/output", 100);

      vel_msg.header.stamp = ros::Time::now();
      vel_msg.header.frame_id = follower1+"/base_link";
      
      if(isformation != 2)
      {
        if(pose_flag)
        {
          switch(follower1[9]-'0')
        {
          case 1:
            f1msg = msg1; break;
          case 2:
            f1msg = msg2; break;
          case 3:
            f1msg = msg3; break;
          case 4:
            f1msg = msg4; break;
          case 5:
            f1msg = msg5; break;
        }
          switch(leader_name[9]-'0')
        {
          case 1:
            ldmsg = msg1; break;
          case 2:
            ldmsg = msg2; break;
          case 3:
            ldmsg = msg3; break;
          case 4:
            ldmsg = msg4; break;
          case 5:
            ldmsg = msg5; break;
        }
          follow();
        }
      }
      if(isformation == 2)
      {
        if(pose_flag)
        {
          switch(follower1[9]-'0')
        {
          case 1:
            f1msg = msg1; break;
          case 2:
            f1msg = msg2; break;
          case 3:
            f1msg = msg3; break;
          case 4:
            f1msg = msg4; break;
          case 5:
            f1msg = msg5; break;
        }
          switch(leader_name[9]-'0')
        {
          case 1:
            ldmsg = msg1; break;
          case 2:
            ldmsg = msg2; break;
          case 3:
            ldmsg = msg3; break;
          case 4:
            ldmsg = msg4; break;
          case 5:
            ldmsg = msg5; break;
        }
          overtake();
        }
      }
    }
    rate.sleep();
  }
  return 0;
};


void follow (void)
{
  tf::Quaternion f1orientation,ldorientation;
  tf::quaternionMsgToTF(f1msg.pose.pose.orientation, f1orientation);
  tf::quaternionMsgToTF(ldmsg.pose.pose.orientation, ldorientation);
  double theta = atan2(ldmsg.pose.pose.position.y-f1msg.pose.pose.position.y,
                                 ldmsg.pose.pose.position.x-f1msg.pose.pose.position.x) - f1orientation.getAngle();
  double r = sqrt(pow(ldmsg.pose.pose.position.x-f1msg.pose.pose.position.x, 2) +
                                  pow(ldmsg.pose.pose.position.y-f1msg.pose.pose.position.y, 2));
  double alpha = PI/2 - f1orientation.getAngle();
  double e = f1msg.pose.pose.position.x - 1.87;
  double k = 0.5;
  if(r > 0.4)
  {
    vel_msg.drive.speed = 0.3 * r;
  }else
  {
    vel_msg.drive.speed = 0.05;
  }
  vel_msg.drive.steering_angle = k*theta;
  slave_vel.publish(vel_msg);
}

void overtake (void)
{
  
  tf::Quaternion f1orientation,ldorientation;
  tf::quaternionMsgToTF(f1msg.pose.pose.orientation, f1orientation);
  tf::quaternionMsgToTF(ldmsg.pose.pose.orientation, ldorientation);
  //get vertical distance between ld and f1
  double y_ld_f1 = ldmsg.pose.pose.position.y - f1msg.pose.pose.position.y;
  double x_ld_f1 = ldmsg.pose.pose.position.x - f1msg.pose.pose.position.x;
  double alpha = ldorientation.getAngle()-f1orientation.getAngle();
  
  if(overtake_phase == 1) 
  {
    overtake_phase = 1;
    double e = 0.25 - x_ld_f1;//left 25cm lane
    double k = 4;

    //f1's speed is a little faster than ld
    vel_msg.drive.speed = getmodule(ldmsg.twist.twist.linear)-0.05;

    //Stanley method
    vel_msg.drive.steering_angle = atan2(k*e,1) + alpha;
    
    if(abs(alpha) < 0.05)
    {
      overtake_phase = 2;
    }
  }else if(overtake_phase == 2)
  {
    double e = 0.25 - x_ld_f1;//original lane
    double k = 3;
    //f1's speed is a little faster than ld
    vel_msg.drive.speed = getmodule(ldmsg.twist.twist.linear) + 0.1;

    //Stanley method
    vel_msg.drive.steering_angle = atan2(k*e,1) + alpha;
    
    //overtake finish condition
    if(y_ld_f1 < -0.4)
    {
      overtake_phase = 3;
    }
  }else if(overtake_phase == 3)
  {
    //??
    double e = 0 - x_ld_f1;//original lane
    double k = 3;
    //f1's speed is a little faster than ld
    vel_msg.drive.speed = getmodule(ldmsg.twist.twist.linear);

    //Stanley method
    vel_msg.drive.steering_angle = atan2(k*e,1) + alpha;
  }


  slave_vel.publish(vel_msg);
}

double getmodule(geometry_msgs::Vector3 v)
{
  double rst = sqrt(pow(v.x,2)+pow(v.y,2)+pow(v.z,2));
  return rst;
}

void laserCallBack(const sensor_msgs::LaserScan::ConstPtr & laser_msg)
{
}

void statusCallBack(const pkg::status::ConstPtr & status_msg)
{
  leader_name = status_msg->leader;
  isformation = status_msg->formation;
  follower1 = status_msg->follower1;
  follower2 = status_msg->follower2;
  follower3 = status_msg->follower3;
  follower4 = status_msg->follower4;
}

void poseCallback1(const nav_msgs::Odometry::ConstPtr& msg)
{
  pose_flag = true;
  msg1.child_frame_id = msg->child_frame_id;
  msg1.header = msg->header;
  msg1.pose = msg->pose;
  msg1.twist = msg->twist;
}

void poseCallback2(const nav_msgs::Odometry::ConstPtr& msg)
{
  pose_flag = true;
  msg2.child_frame_id = msg->child_frame_id;
  msg2.header = msg->header;
  msg2.pose = msg->pose;
  msg2.twist = msg->twist;
}

void poseCallback3(const nav_msgs::Odometry::ConstPtr& msg)
{
  pose_flag = true;
  msg3.child_frame_id = msg->child_frame_id;
  msg3.header = msg->header;
  msg3.pose = msg->pose;
  msg3.twist = msg->twist;
}

void poseCallback4(const nav_msgs::Odometry::ConstPtr& msg)
{
  pose_flag = true;
  msg4.child_frame_id = msg->child_frame_id;
  msg4.header = msg->header;
  msg4.pose = msg->pose;
  msg4.twist = msg->twist;
}

void poseCallback5(const nav_msgs::Odometry::ConstPtr& msg)
{
  pose_flag = true;
  msg5.child_frame_id = msg->child_frame_id;
  msg5.header = msg->header;
  msg5.pose = msg->pose;
  msg5.twist = msg->twist;
}
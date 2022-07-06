#!/usr/bin/env python3

#############################################################
#   This py file get the lidar and camera info (time syncr  #
#   onize) and make fusion.                                 #
#############################################################


from pathlib import Path
import argparse
import yaml
import rospy
from termcolor import colored
import message_filters
import ros_numpy

from sensor_msgs.msg import Image               # image  type
from sensor_msgs.msg import PointCloud2         # pointcloud type
from msgs.msg._MsgCamera import *               # Image type: camera msgs class
from nav_msgs.msg import Odometry               # odometry type
from .OpenPCDet.tools.pred import *             # 3d Detection tool
from .pointcloud_roi import pointcloud_roi      # pointcloud detection
from ..utils.yolo.yolo import YOLO              # vision detection
from ..utils.image_roi import image_roi

# fusion message type
# from msgs.msg._MsgLidCam import *
# visualization
from ..utils.visualization import lidar_camera_match2visual
from ..utils.evaluation import eval3d


def fusion(pointcloud, msgcamera, odom=None):
    """
        pointcloud: [N,4]
        msgcamera: [1,8] -> eight Images
    """
    assert isinstance(pointcloud, PointCloud2)
    assert isinstance(msgcamera, MsgCamera)
    global counter, start_time, pred_counter

    # pointcloud roi
    points = convert_ros_pointcloud_to_numpy(pointcloud)
    pred_boxes3d, pred_labels, pred_scores = pointcloud_detector.get_pred_dicts(points, False)
    cameras, pixel_poses = pointcloud_roi(ROOT_DIR, config, pred_boxes3d)           # get cameras and pixel_poses of all vehicles
    if params.print2screen_lidar:                                                   # print pred results to screen
        print2screen_lidar(pred_boxes3d, pred_labels, pred_scores)

    # image roi
    pred_boxes2d = []
    for img in msgcamera.camera:
        pred_box2d = image_roi(img, yolo)
        pred_boxes2d.append(pred_box2d)

    # pred results eval: BEV (for one car)
    if odom is not None:
        # 3d-detection only: use 'pred_boxes3d' to eval
        global alpha_diff, pose_diff, iou3d, iou_bev, tp_fp_fn
        pred_counter, alpha_diff, pose_diff, iou3d, iou_bev, tp_fp_fn = eval3d(odom, pred_boxes3d, logger, pred_counter,
                                                                                alpha_diff, pose_diff, iou3d, iou_bev, tp_fp_fn)
        if counter % 1000 == 0:
            np.savetxt(str(ROOT_DIR / 'src/LidCamFusion/eval/3d_detection_only_%s.txt' % counter), tp_fp_fn)
        
    # object match
    iou_thresh = config['lid_cam_fusion']['iou_thresh']
    match, image, lidar = get_match(cameras, pixel_poses, pred_boxes2d, iou_thresh)
    if params.print2screen_match:
        print2screen_match(match, image, lidar)
    if params.save_match_result:                                                    # visualize match result
        output_dir = str(ROOT_DIR / config['output']['LidCamFusion_dir'])
        lidar_camera_match2visual(match, image, lidar, pred_boxes2d, pixel_poses, msgcamera, output_dir)

    # object fusion
    get_fusion(match, pred_boxes2d, pred_boxes3d, pixel_poses)

    # publish result
    # msglidcam = MsgLidCam()
    # msglidcam.header.stamp = rospy.Time.now()
    # pub = rospy.Publisher("/lidar_camera_fused", MsgLidCam)
    # pub.publish(msglidcam)

    # fps evalution (without results evalution and visualization)
    cur_time = time.time()
    time_span = cur_time - start_time
    start_time = cur_time
    counter += 1
    # fps = (counter-1) / time_span
    fps = 1 / time_span
    print('FPS: ', fps, 'cnt: ', counter)
    

def get_match(cameras, pixel_poses, boxes2d, iou_thresh):
    """
        cameras: (N,M)
        pixel_poses: (N,1) -> N: num of vehicles
        cameras, pixel_poses => pred_boxes3d
        boxes2d: (8,N,6) -> 8 cameras, num of vehicles, [left top right bottom score calss]
        For each vehicle detected by lidar, match the only one camera

        cameras, pixel_poses, boxes2d may be empty: []
    """
    # match
    match = []
    vehicles = []
    idxes = []
    # image
    image = []
    # lidar
    lidar = []

    # add labels for boxes2d: 0->mismatched, 1->matched
    for camera in range(len(boxes2d)):
        labels = [0] * len(boxes2d[camera]) # if len=0 then labels is []
        idxes.append(labels)

    for vehicle, pixel_pose in enumerate(pixel_poses):              # for each vehicle detected by lidar
        # get camera
        camera = cameras[vehicle][0]                                # consider the first camera, other camera(s) will not be considered
        # get all boxes2d of this camera
        box2d = boxes2d[camera-1]
        # get labels of all boxes2d
        labels = idxes[camera-1]
        bbox = get_bbox_from_box3d(pixel_pose[0])           
        if len(box2d) != 0:
            iou2ds = get_iou2d(bbox, box2d, labels, iou_thresh)     # ious of 1-lidar detected and N-camera detected
            if len(np.where(iou2ds != -1)) != 0:                    # matched box exist
                idx = np.where(iou2ds==np.max(iou2ds))              # idx: index of maximum iou2d: 2-d
                idxes[camera-1][idx[0][0]] = 1                      # label matched
                vehicles.append(vehicle)
                cur_match = [camera, vehicle, idx[0][0]]            # [camera num, vehcile num(lidar), box2d num(camera)]
                match.append(cur_match)
    
    # image only: add remaining detecteion results (midmatched) to the list according to idxes
    for camera in range(len(boxes2d)):
        cur_image = [camera+1]
        for box2d, label in zip(boxes2d[camera], idxes[camera]):
            if not label:
                cur_image.append(box2d)
        image.append(cur_image)
    # lidar only: add remaining detection results (mismatched) to the list according to vehicels
    for vehicle in range(len(pixel_poses)):
        if vehicle not in vehicles:
            lidar.append([cameras[vehicle][0], vehicle])

    # print(match, vehicles, idxes)
    # print(image, lidar, '\n')
    return match, image, lidar

def get_bbox_from_box3d(pixel_pose):
    xaxis = np.array(pixel_pose)[:,0]
    yaxis = np.array(pixel_pose)[:,1]
    x_max = np.max(xaxis)
    x_min = np.min(xaxis)
    y_max = np.max(yaxis)
    y_min = np.min(yaxis)
    return np.array([x_min, y_min, x_max, y_max])
    

def get_iou2d(boxa, boxesb, labels, iou_thresh):
    """
        boxa: (1,) -> lidar
        boxesb: (N,) -> camera
    """
    def get_single_iou2d(boxa, boxb):                       # for each vehicle detected by camera
        x1 = max(boxa[0], boxb[0])
        y1 = max(boxa[1], boxb[1])
        x2 = min(boxa[2], boxb[2])
        y2 = min(boxa[3], boxb[3])
        areaa = (boxa[2] - boxa[0]) * (boxa[3] - boxa[1])
        areab = (boxb[2] - boxb[0]) * (boxb[3] - boxb[1])
        overlap = (x2 - x1) * (y2 - y1)
        iou2d = overlap / (areaa + areab - overlap)
        return iou2d

    iou2ds = []
    for boxb, label in zip(boxesb, labels):
        if not label:
            iou2d = get_single_iou2d(boxa, boxb)
            if iou2d < iou_thresh:                          # if iou is too small, mismatch
                iou2d = -1
        else:                                               # if box2d is matched before, mismatch
            iou2d = -1
        iou2ds.append(iou2d)

    return np.array(iou2ds)


def get_fusion(match, boxes2d, boxes3d, pixels_poses):
    """
        match: [camera num, vehcile num(lidar), box2d num(camera)]
    """
    for obj in match:
        print(obj)
        camera_num, vehicle_num, box2d_num = obj[0], obj[1], obj[2]
        box2d = boxes2d[camera_num-1][box2d_num]
        box3d, pixel_pose = boxes3d[vehicle_num], pixels_poses[vehicle_num]



def convert_ros_pointcloud_to_numpy(pointcloud: PointCloud2):
    pc = ros_numpy.numpify(pointcloud)
    points = np.zeros((pc.shape[0],4))
    points[:,0] = pc['x']
    points[:,1] = pc['y']
    points[:,2] = pc['z']

    return points


def print2screen_lidar(pred_boxes3d, pred_labels, pred_scores):
    label2class = {1: 'Car', 2: 'Pedstrain', 3: 'Bicycle' }
    print("+-------------------------------------------------------------------------------------------+")
    print("num_car: ", len(pred_boxes3d))
    for i in range(len(pred_boxes3d)):
        print(i+1, " ==> ", label2class[int(pred_labels[i])], "  score: ", pred_scores[i])
        print("  ", pred_boxes3d[i][0:3], " ", pred_boxes3d[i][3:6], " ", pred_boxes3d[i][6])
    print("+-------------------------------------------------------------------------------------------+\n")


def print2screen_match(match, image, lidar):
    """
        match: [camera num, vehcile num(lidar), box2d num(camera)]
        image: [[1,],[2,],...,[8,]]
        lidar: [[camera num, vehicle num]]
    """
    print("+-------------------------------------------------------------------------------------------+")
    print("match: ", match)
    print("image: ", image)
    print("lidar: ", lidar)
    print("+-------------------------------------------------------------------------------------------+\n")


if __name__ == '__main__':
    # get ROOT DIR
    ROOT_DIR = Path(__file__).resolve().parents[2]
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="path to config file", metavar="FILE", required=False, default= str(ROOT_DIR / 'config/config.yaml'))
    parser.add_argument("--save_match_result", help="wehter to save match result", action='store_true', required=False)
    parser.add_argument("--print2screen_lidar", help="wehter to print to screen", action='store_true', required=False)
    parser.add_argument("--print2screen_match", help="wehter to print to screen", action='store_true', required=False)
    parser.add_argument("--eval", help="wehter to eval", action='store_true', required=False)
    params = parser.parse_args()

    with open(params.config, 'r') as f:
        try:
            config = yaml.load(f, Loader=yaml.FullLoader)
        except:
            print(colored('Config file could not be read.','red'))
            exit(1)

    rospy.init_node('lidar_camera_fusion', anonymous=True)

    # fps evaluation
    counter = 1
    fps = 0

    # Create an example of pointcloud detector
    pointcloud_detector = RT_Pred(str(ROOT_DIR), config)
    # Create YOLO detector
    yolo = YOLO(ROOT_DIR)

    sub_pointcloud = message_filters.Subscriber('/point_cloud_combined', PointCloud2)
    sub_camera = message_filters.Subscriber('/camera_msgs_combined', MsgCamera)

    if params.eval:
        # create tensorboard logger
        from tensorboard_logger import Logger
        import datetime
        import os
        log_dir = ROOT_DIR+'/src/LidCamFusion/eval/%s/' % datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        os.makedirs(log_dir, exist_ok=True)
        logger = Logger(logdir=log_dir, flush_secs=10)
        # pointcloud pred results evaluation
        pred_counter = 1
        alpha_diff = 0
        pose_diff = 0
        iou3d = 0
        iou_bev = 0
        # caculate tp, fp, fn
        N_SAMPLE_PTS = 41
        tp_fp_fn = np.array([np.zeros(N_SAMPLE_PTS), np.zeros(N_SAMPLE_PTS), np.zeros(N_SAMPLE_PTS)])
        
        sub_odom = message_filters.Subscriber('//base_pose_ground_truth', Odometry)
        sync = message_filters.ApproximateTimeSynchronizer([sub_pointcloud, sub_camera, sub_odom], 1, 1) # syncronize time stamps
        sync.registerCallback(fusion)
        print("Lidar Camera Fusion (with eval) Begin.")
        start_time = time.time()
        rospy.spin()
    else:
        sync = message_filters.ApproximateTimeSynchronizer([sub_pointcloud, sub_camera], 1, 1)
        sync.registerCallback(fusion)
        print("Lidar Camera Fusion Begin.")
        start_time = time.time()
        rospy.spin()

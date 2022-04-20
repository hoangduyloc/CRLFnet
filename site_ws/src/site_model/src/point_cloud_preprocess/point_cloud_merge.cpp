#include <pcl/io/pcd_io.h>

using namespace std;

typedef pcl::PointXYZI PointT; // 注意点云格式是：XYZ还是XYZRGB,XYZI
typedef pcl::PointCloud<PointT> PointCloudT;

/*int main()
{
	PointCloudT::Ptr cloud_1(new PointCloudT);
	PointCloudT::Ptr cloud_2(new PointCloudT);
	PointCloudT::Ptr cloud_3(new PointCloudT);
	PointCloudT::Ptr cloud(new PointCloudT);
	pcl::io::loadPCDFile("/home/zonlin/ROS/site_ws/src/site_model/point_cloud_data/point_cloud1.pcd", *cloud_1);
	pcl::io::loadPCDFile("/home/zonlin/ROS/site_ws/src/site_model/point_cloud_data/point_cloud2.pcd", *cloud_2);
	pcl::io::loadPCDFile("/home/zonlin/ROS/site_ws/src/site_model/point_cloud_data/point_cloud3.pcd", *cloud_3);

	*cloud = *cloud_1 + *cloud_2 + *cloud_3;

    if(pcl::io::savePCDFileASCII ("/home/zonlin/ROS/site_ws/src/site_model/point_cloud_data/point_cloud.pcd", *cloud)>=0)
    {std::cerr << "Saved point_cloud.pcd" << " " << cloud->points.size() << "points have been merged" << std::endl;}

	return 0;
}*/

int main()
{
	PointCloudT::Ptr cloud_1(new PointCloudT);
	PointCloudT::Ptr cloud_2(new PointCloudT);
	PointCloudT::Ptr cloud_3(new PointCloudT);
	PointCloudT::Ptr cloud(new PointCloudT);
	pcl::io::loadPCDFile("/home/zonlin/IPP_WorkSpace/ROS_WS/site_ws/src/site_model/point_cloud_data/point_cloud.pcd", *cloud_1);
	pcl::io::loadPCDFile("/home/zonlin/IPP_WorkSpace/ROS_WS/site_ws/src/site_model/point_cloud_data/bin2pcd/000000.pcd", *cloud_2);

	*cloud = *cloud_1 + *cloud_2;

    if(pcl::io::savePCDFileBinary ("/home/zonlin/IPP_WorkSpace/ROS_WS/site_ws/src/site_model/point_cloud_data/bin2pcd/integrated.pcd", *cloud)>=0)
    {std::cerr << "Saved point_cloud.pcd" << " " << cloud->points.size() << "points have been merged" << std::endl;}

	return 0;
}
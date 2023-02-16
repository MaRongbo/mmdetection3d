from collections import defaultdict
import cv2
import os
# img = cv2.imread('/mnt/intel/jupyterhub/mrb/datasets/L4E_wo_tele/L4E_origin_data/training/front_left_camera/007791.1618541811.398278.20210416T064550_j7-e0008_59_23to43.jpg')

# p=(100,10)
# cv2.circle(img, p, 1, (255,0,0), 2)
# print(img.shape)


# bp = [0,0,0]
# img[15:30, 100:115,1] = bp
# cv2.imwrite('aaa.png',img)

# pass


import pickle

def analysis_raw_label_number(data_root):
    lable_num_dict = defaultdict(int)
    for f in os.listdir(data_root):
        pkl_name = os.path.join(data_root, f)
        pkl_file = open(pkl_name, 'rb')
        data = pickle.load(pkl_file,  encoding='latin1')
        for d in data:
            lable_num_dict[d['name']]+=1
    print(data_root, len(os.listdir(data_root)), lable_num_dict)
        

def generate_mini_pkl(data_root, pkl_name):
    pkl_name=os.path.join(data_root, pkl_name)

    pkl_file = open(pkl_name, 'rb')
    data = pickle.load(pkl_file)
    
    #generate mini dataset pkl
    with open(os.path.join(data_root, pkl_name.split('.')[0]+"_mini"+'.pkl'), 'wb') as f:
        pickle.dump(data[0:10], f)
        

def analysis_pkl(data_root, pkl_name):
    lable_num_dict = defaultdict(int)
    pkl_name=os.path.join(data_root, pkl_name)

    pkl_file = open(pkl_name, 'rb')
    data = pickle.load(pkl_file)
    
    #generate mini dataset pkl
    with open(os.path.join(data_root, pkl_name.split('.')[0]+"_mini"+'.pkl'), 'wb') as f:
        pickle.dump(data[0:10], f)
    
    shape_dict = defaultdict(int)
    for d in data:
        # img_shape = d['image']['front_left_camera']['image_shape']
        # shape_dict[img_shape]+=1
        for c in d['annos']['name']:
            lable_num_dict[c]+=1
        # d['calib']['front_left_camera']['R0_rect'] ==d['calib']['front_right_camera']['R0_rect']
        # imgL = cv2.imread(root_path + d['image']['front_left_camera']['image_path'])
        # imgR = cv2.imread(root_path + d['image']['front_right_camera']['image_path'])
    # print(data_root+pkl_name, shape_dict)
    print('label',len(data), lable_num_dict)

#l3
# l3_benchmark_root = '/mnt/intel/jupyterhub/swc/datasets/L4E_extracted_data_1227/L4E_origin_benchmark/'
# analysis_pkl(l3_benchmark_root, 'Kitti_L4_lc_data_mm3d_infos_val_5314.pkl')

generate_mini_pkl('/mnt/intel/jupyterhub/mrb/datasets/L4E_origin_data/', 'L4_data_infos_train.pkl')
generate_mini_pkl('/mnt/jupyterhub/mrb/plus/pc_label_trainval/L4E_origin_data', 'L4_data_infos_val.pkl')
generate_mini_pkl('/mnt/jupyterhub/mrb/plus/pc_label_trainval/L4E_origin_benchmark', 'L4_data_infos_test.pkl')
generate_mini_pkl('/mnt/intel/jupyterhub/mrb/datasets/L4E_origin_data/', 'Kitti_L4_lc_data_mm3d_infos_train_12321.pkl')


analysis_raw_label_number('/mnt/intel/jupyterhub/mrb/mnt/pc_label_trainval/L4E_origin_data/training/label')
analysis_raw_label_number('/mnt/intel/jupyterhub/swc/datasets/L4E_extracted_data_1227/L4E_origin_data/training/label')

root_path= '/mnt/intel/jupyterhub/mrb/datasets/L4E_extracted_data_1227/L4E_origin_data/'
analysis_pkl(root_path, 'Kitti_L4_lc_data_mm3d_infos_train_12192.pkl')
analysis_pkl(root_path, 'Kitti_L4_lc_data_mm3d_infos_train_12297_0118.pkl')

root_path= '/mnt/intel/jupyterhub/mrb/datasets/L4E_extracted_data_1227/L4E_origin_benchmark/'
analysis_pkl(root_path, 'Kitti_L4_lc_data_mm3d_infos_val_5314.pkl')
analysis_pkl(root_path, 'Kitti_L4_lc_data_mm3d_infos_val_5585_0119.pkl')

analysis_pkl('/mnt/intel/jupyterhub/mrb/mnt/pc_label_trainval/L4E_origin_data', 'L4_data_infos_train.pkl')
analysis_pkl('/mnt/intel/jupyterhub/mrb/mnt/pc_label_trainval/L4E_origin_benchmark', 'L4_data_infos_train.pkl')
# analysis_pkl(root_path, 'L4_data_infos_train.pkl')




# # l4
# data_root = '/mnt/intel/jupyterhub/swc/datasets/L4_extracted_data/CN_L4_origin_data/'
# hard_case_data = '/mnt/intel/jupyterhub/swc/datasets/L4_extracted_data/hard_case_origin_data/'
# side_vehicle_data = '/mnt/intel/jupyterhub/swc/datasets/L4_extracted_data/side_vehicle_origin_data/'
# under_tree_data = '/mnt/intel/jupyterhub/swc/datasets/L4_extracted_data/under_tree_origin_data/'
# benchmark_root = '/mnt/intel/jupyterhub/swc/datasets/L4_extracted_data/CN_L4_origin_benchmark/'

# pkls = [
#     data_root, hard_case_data, side_vehicle_data, under_tree_data,
#     benchmark_root]
# for pkl in pkls:
#     if 'benchmark' in pkl:
#         analysis_pkl(pkl, 'Kitti_L4_data_mm3d_infos_val.pkl')
#     else:
#         analysis_pkl(pkl, 'Kitti_L4_data_mm3d_infos_train.pkl')
        




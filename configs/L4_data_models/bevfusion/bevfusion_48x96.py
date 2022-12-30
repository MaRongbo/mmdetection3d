_base_ = [
    '../../_base_/schedules/cyclic_40e.py', '../../_base_/default_runtime.py'
]
using_tele=False
# model settings
voxel_size = [0.4, 0.4, 8] # 120*240
point_cloud_range = [-24, -24, -2, 72, 24, 6]

# point_cloud_range = [-25.6, -64, -2, 102.4, 64, 6]
# voxel_size = [0.32, 0.32, 8] # 128x128  400*400

use_sync_bn=True # set Fasle when debug
used_cameras = 4
use_offline_img_feat=False
offline_feature_resize_shape=(72, 120)
used_sensors = {'use_lidar': True,
               'use_camera': True,
               'use_radar': False}
grid_config = {
    'x': [point_cloud_range[0], point_cloud_range[3], voxel_size[0]],
    'y': [point_cloud_range[1], point_cloud_range[4], voxel_size[1]],
    'z': [-10.0, 10.0, 20.0],
    'depth': [1.0, 72, 1],
}
bev_grid_map_size = [
    int((grid_config['y'][1] - grid_config['y'][0]) / voxel_size[1]),
    int((grid_config['x'][1] - grid_config['x'][0]) / voxel_size[0]),
    ]
feat_channel = 0
if used_sensors['use_lidar']: feat_channel+=64 
if used_sensors['use_camera']: feat_channel+=64 
data_config = {
    'cams': [
        'front_left_camera', 'front_right_camera', 'side_left_camera', 'side_right_camera'
    ],
    'Ncams':
    4,
    'input_size': (540, 960),
    'src_size': (540, 960),

    # Augmentation
    'resize': (-0.06, 0.11),
    'rot': (-5.4, 5.4),
    'flip': True,
    'crop_h': (0.0, 0.0),
    'resize_test': 0.00,
}
bda_aug_conf = dict(
    rot_lim=(-22.5, 22.5),
    scale_lim=(0.95, 1.05),
    flip_dx_ratio=0.5,
    flip_dy_ratio=0.5)
numC_Trans = 80

model = dict(
    type='BEVDet',
    used_sensors=used_sensors,
    use_offline_feature=use_offline_img_feat,
    img_backbone=dict(
        pretrained='torchvision://resnet50',
        type='ResNet',
        depth=50,
        num_stages=4,
        out_indices=(2, 3),
        frozen_stages=-1,
        norm_cfg=dict(type='BN', requires_grad=True),
        norm_eval=False,
        with_cp=True,
        style='pytorch'),
    img_neck=dict(
        type='CustomFPN',
        in_channels=[1024, 2048],
        out_channels=512,
        num_outs=1,
        start_level=0,
        out_ids=[0]),
    img_view_transformer=dict(
        type='LSSViewTransformer',
        grid_config=grid_config,
        input_size=(540,960),
        feature_size=offline_feature_resize_shape,
        in_channels=64,
        out_channels=numC_Trans,
        downsample=16),
    img_bev_encoder_backbone=dict(
        type='CustomResNet',
        numC_input=numC_Trans,
        num_channels=[numC_Trans * 2, numC_Trans * 4, numC_Trans * 8]),
    img_bev_encoder_neck=dict(
        type='FPN_LSS',
        in_channels=numC_Trans * 8 + numC_Trans * 2,
        out_channels=64),
    pts_voxel_layer=dict(
        max_num_points=24,  # max_points_per_voxel
        point_cloud_range=point_cloud_range,
        voxel_size=voxel_size,
        max_voxels=(32000, 32000)  # (training, testing) max_voxels
    ),
    pts_voxel_encoder=dict( #lss加到这里？
        type='PillarFeatureNet',
        in_channels=4,
        feat_channels=[64],
        with_distance=False,
        voxel_size=voxel_size,
        use_pcdet=True,
        point_cloud_range=point_cloud_range),
    pts_middle_encoder=dict(
        type='PointPillarsScatter', in_channels=64, output_shape=bev_grid_map_size),
    pts_backbone=dict(
        type='PcdetBackbone',
        in_channels=feat_channel,
        layer_nums=[3, 5, 5],
        layer_strides=[2, 2, 2],
        num_filters=[feat_channel, 128, 256],
        upsample_strides=[1, 2, 4],
        num_upsample_filters=[128, 128, 128],
        ),
    pts_bbox_head=dict(
        type='Anchor3DHead',
        num_classes=4,
        in_channels=384,
        feat_channels=384,
        use_direction_classifier=True,
        assign_per_class=True,
        anchor_generator=dict(
            type='AlignedAnchor3DRangeGenerator',
            ranges=[
                [point_cloud_range[0], point_cloud_range[1], -0.4, point_cloud_range[3], point_cloud_range[4], -0.4],
                [point_cloud_range[0], point_cloud_range[1], -0.4, point_cloud_range[3], point_cloud_range[4], -0.4],
                [point_cloud_range[0], point_cloud_range[1], -0.4, point_cloud_range[3], point_cloud_range[4], -0.4],
                [point_cloud_range[0], point_cloud_range[1], -0.6, point_cloud_range[3], point_cloud_range[4], -0.6],
            ],
            sizes=[[0.8, 0.6, 1.73], # ped
                   [1.76, 0.6, 1.73], # cyclist
                   [4.63, 1.97, 1.74], # car
                   [12.5, 2.94, 3.47],  # truck
                   ],
            rotations=[0, 1.57],
            reshape_out=False),
        diff_rad_by_sin=True,
        bbox_coder=dict(type='DeltaXYZWLHRBBoxCoder'),
        loss_cls=dict(
            type='FocalLoss',
            use_sigmoid=True,
            gamma=2.0,
            alpha=0.25,
            loss_weight=1.0),
        loss_bbox=dict(type='SmoothL1Loss', beta=1.0 / 9.0, loss_weight=2.0),
        loss_dir=dict(
            type='CrossEntropyLoss', use_sigmoid=False, loss_weight=0.2)),
    # model training and testing settings
    train_cfg=dict(
        pts=dict(
            assigner=[
                dict(  # for Pedestrian
                    type='MaxIoUAssigner',
                    iou_calculator=dict(type='BboxOverlapsNearest3D'),
                    pos_iou_thr=0.5,
                    neg_iou_thr=0.35,
                    min_pos_iou=0.2,
                    ignore_iof_thr=-1),
                dict(  # for Cyclist
                    type='MaxIoUAssigner',
                    iou_calculator=dict(type='BboxOverlapsNearest3D'),
                    pos_iou_thr=0.5,
                    neg_iou_thr=0.35,
                    min_pos_iou=0.2,
                    ignore_iof_thr=-1),
                dict(  # for Car
                    type='MaxIoUAssigner',
                    iou_calculator=dict(type='BboxOverlapsNearest3D'),
                    pos_iou_thr=0.6,
                    neg_iou_thr=0.45,
                    min_pos_iou=0.2,
                    ignore_iof_thr=-1),
                dict(  # for Truck
                    type='MaxIoUAssigner',
                    iou_calculator=dict(type='BboxOverlapsNearest3D'),
                    pos_iou_thr=0.55,
                    neg_iou_thr=0.4,
                    min_pos_iou=0.2,
                    ignore_iof_thr=-1),
            ],
        allowed_border=0,
        pos_weight=-1,
        debug=False)),
    test_cfg=dict(
        pts=dict(use_rotate_nms=True,
        nms_across_levels=False,
        nms_thr=0.01,
        score_thr=0.1,
        min_bbox_size=0,
        nms_pre=4096,
        max_num=500)))
# dataset settings
dataset_type = 'PlusKittiDataset'
data_root = '/mnt/intel/jupyterhub/swc/datasets/L4_extracted_data/CN_L4_origin_data/'
hard_case_data = '/mnt/intel/jupyterhub/swc/datasets/L4_extracted_data/hard_case_origin_data/'
side_vehicle_data = '/mnt/intel/jupyterhub/swc/datasets/L4_extracted_data/side_vehicle_origin_data/'
under_tree_data = '/mnt/intel/jupyterhub/swc/datasets/L4_extracted_data/under_tree_origin_data/'

benchmark_root = '/mnt/intel/jupyterhub/swc/datasets/L4_extracted_data/CN_L4_origin_benchmark/'

class_names = ['Pedestrian', 'Cyclist', 'Car', 'Truck']
input_modality = dict(use_lidar=True, use_camera=False)

file_client_args = dict(backend='disk')

db_sampler = dict(
    data_root=data_root,
    info_path=data_root + 'Kitti_L4_data_dbinfos_train.pkl',
    rate=1.0,
    prepare=dict(
        filter_by_difficulty=[-1],
        filter_by_min_points=dict(Car=5, Pedestrian=5, Cyclist=5, Truck=5)),
    classes=class_names,
    sample_groups=dict(Car=15, Pedestrian=15, Cyclist=15, Truck=5),
    points_loader=dict(
        type='LoadPointsFromFile',
        coord_type='LIDAR',
        load_dim=4,
        use_dim=4,
        point_type='float64',
        file_client_args=file_client_args),
    file_client_args=file_client_args)

# PointPillars uses different augmentation hyper parameters
train_pipeline = [
    dict(
        type='PrepareImageInputs',
        is_train=True, 
        data_config=data_config,
        is_plusdata=True,
        use_offline_feature=use_offline_img_feat,
        offline_feature_resize_shape=offline_feature_resize_shape),
    dict(
        type='LoadPointsFromFile',
        coord_type='LIDAR',
        load_dim=4,
        use_dim=4,
        point_type='float64',
        using_tele=using_tele,
        file_client_args=file_client_args),
    dict(
        type='LoadAnnotationsBEVDepth_Plus',
        bda_aug_conf=bda_aug_conf,
        classes=class_names),
    # dict(type='PointToMultiViewDepth_Plus', downsample=1, grid_config=grid_config),
    dict(type='PointsRangeFilter', point_cloud_range=point_cloud_range),
    dict(type='PointShuffle'),
    dict(type='ObjectRangeFilter', point_cloud_range=point_cloud_range),
    dict(type='ObjectNameFilter', classes=class_names),
    dict(type='DefaultFormatBundle3D', class_names=class_names),
    dict(
        type='Collect3D', keys=['img_inputs','points', 'gt_bboxes_3d', 'gt_labels_3d', 'raw_img', 'canvas'])
]

test_pipeline = [
    dict(type='PrepareImageInputs', data_config=data_config, is_plusdata=True, use_offline_feature=True,
         offline_feature_resize_shape=offline_feature_resize_shape),
    dict(
        type='LoadPointsFromFile',
        coord_type='LIDAR',
        load_dim=4,
        use_dim=4,
        point_type='float64',
        using_tele=False,
        file_client_args=file_client_args),
    dict(
        type='LoadAnnotationsBEVDepth_Plus',
        bda_aug_conf=bda_aug_conf,
        classes=class_names,
        is_train=False),
    # dict(
    #     type='LoadPointsFromFile',
    #     coord_type='LIDAR',
    #     load_dim=5,
    #     use_dim=5,
    #     file_client_args=file_client_args),
    dict(
        type='MultiScaleFlipAug3D',
        img_scale=(1333, 800),
        pts_scale_ratio=1,
        flip=False,
        transforms=[
            dict(
                type='DefaultFormatBundle3D',
                class_names=class_names,
                with_label=False),
            dict(type='Collect3D', keys=['img_inputs', 'points'])
        ])
]

eval_pipeline = [
    dict(type='PrepareImageInputs', data_config=data_config, is_plusdata=True, use_offline_feature=True),
    dict(
        type='LoadPointsFromFile',
        coord_type='LIDAR',
        load_dim=4,
        use_dim=4,
        point_type='float64',
        using_tele=False,
        file_client_args=file_client_args),
    dict(
        type='LoadAnnotationsBEVDepth_Plus',
        bda_aug_conf=bda_aug_conf,
        classes=class_names,
        is_train=True),
    # dict(type='LoadMultiCamImagesFromFile', to_float32=True),
    # dict(type='RandomFlipLidarOnly', flip_ratio_bev_horizontal=0.5),
    # dict(
    #     type='GlobalRotScaleTrans',
    #     rot_range=[-0.78539816, 0.78539816],
    #     scale_ratio_range=[0.95, 1.05]),
    dict(type='PointsRangeFilter', point_cloud_range=[-24, -24, -2, 72, 24, 6]),
    
    dict(type='Collect3D', keys=['points', 'img'])
]
concat_train_data = dict(
    type='ConcatDataset',
    datasets=[
        dict(
            type=dataset_type,
            data_root=data_root,
            ann_file=data_root + 'Kitti_L4_data_mm3d_infos_train.pkl',
            split='training',
            pts_prefix='pointcloud',
            pipeline=train_pipeline,
            modality=input_modality,
            classes=class_names,
            test_mode=False,
            pcd_limit_range=point_cloud_range,
            used_cameras=used_cameras,
            box_type_3d='LiDAR',
            file_client_args=file_client_args
        ),
        dict(
            type=dataset_type,
            data_root=hard_case_data,
            ann_file=hard_case_data + 'Kitti_L4_data_mm3d_infos_train.pkl',
            split='training',
            pts_prefix='pointcloud',
            pipeline=train_pipeline,
            modality=input_modality,
            classes=class_names,
            test_mode=False,
            pcd_limit_range=point_cloud_range,
            used_cameras=used_cameras,
            box_type_3d='LiDAR',
            file_client_args=file_client_args
        ),
        dict(
            type=dataset_type,
            data_root=side_vehicle_data,
            ann_file=side_vehicle_data + 'Kitti_L4_data_mm3d_infos_train.pkl',
            split='training',
            pts_prefix='pointcloud',
            pipeline=train_pipeline,
            modality=input_modality,
            classes=class_names,
            test_mode=False,
            pcd_limit_range=point_cloud_range,
            used_cameras=used_cameras,
            box_type_3d='LiDAR',
            file_client_args=file_client_args
        ),
        dict(
            type=dataset_type,
            data_root=under_tree_data,
            ann_file=under_tree_data + 'Kitti_L4_data_mm3d_infos_train.pkl',
            split='training',
            pts_prefix='pointcloud',
            pipeline=train_pipeline,
            modality=input_modality,
            classes=class_names,
            test_mode=False,
            pcd_limit_range=point_cloud_range,
            used_cameras=used_cameras,
            box_type_3d='LiDAR',
            file_client_args=file_client_args
        ),
    ]
)
data = dict(
    samples_per_gpu=8, # ?
    workers_per_gpu=4,
    train=dict(
        type='RepeatDataset',
        times=2,
        dataset=concat_train_data),
    val=dict(
        type=dataset_type,
        data_root=data_root,
        ann_file=data_root + 'Kitti_L4_data_mm3d_infos_val.pkl',
        split='training',
        pts_prefix='pointcloud',
        pipeline=test_pipeline,
        modality=input_modality,
        classes=class_names,
        test_mode=True,
        pcd_limit_range=point_cloud_range,
        used_cameras=used_cameras,
        box_type_3d='LiDAR',
        file_client_args=file_client_args),
    test=dict(
        type=dataset_type,
        data_root=benchmark_root,
        ann_file=benchmark_root + 'Kitti_L4_data_mm3d_infos_val.pkl',
        split='training',
        pts_prefix='pointcloud',
        samples_per_gpu=8,
        pipeline=test_pipeline,
        modality=input_modality,
        classes=class_names,
        pcd_limit_range=point_cloud_range,
        test_mode=True,
        used_cameras=used_cameras,
        box_type_3d='LiDAR',
        file_client_args=file_client_args))
# In practice PointPillars also uses a different schedule
# optimizer
lr = 0.0008
optimizer = dict(lr=lr)
# max_norm=35 is slightly better than 10 for PointPillars in the earlier
# development of the codebase thus we keep the setting. But we does not
# specifically tune this parameter.
optimizer_config = dict(grad_clip=dict(max_norm=35, norm_type=2))
runner = dict(max_epochs=40)

# Use evaluation interval=2 reduce the number of evaluation timese
evaluation = dict(interval=5)
checkpoint_config = dict(interval=10)
workflow = [('train', 2), ('val', 1)]
# resume_from ='work_dirs/L4_data_models/pcdet/lidar_only/pcdet_L4_bev_fusion_align_with_prefusion/2022-11-17T14-40-31/epoch_10.pth'
find_unused_parameters=True
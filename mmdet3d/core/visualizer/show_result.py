# Copyright (c) OpenMMLab. All rights reserved.
from os import path as osp

import mmcv
import numpy as np
import trimesh
import cv2
from mmcv.parallel import DataContainer
import torch

from .image_vis import (draw_camera_bbox3d_on_img, draw_depth_bbox3d_on_img,
                        draw_lidar_bbox3d_on_img, project_pts_on_img)


def _write_obj(points, out_filename):
    """Write points into ``obj`` format for meshlab visualization.

    Args:
        points (np.ndarray): Points in shape (N, dim).
        out_filename (str): Filename to be saved.
    """
    N = points.shape[0]
    fout = open(out_filename, 'w')
    for i in range(N):
        if points.shape[1] == 6:
            c = points[i, 3:].astype(int)
            fout.write(
                'v %f %f %f %d %d %d\n' %
                (points[i, 0], points[i, 1], points[i, 2], c[0], c[1], c[2]))

        else:
            fout.write('v %f %f %f\n' %
                       (points[i, 0], points[i, 1], points[i, 2]))
    fout.close()


def _write_oriented_bbox(scene_bbox, out_filename):
    """Export oriented (around Z axis) scene bbox to meshes.

    Args:
        scene_bbox(list[ndarray] or ndarray): xyz pos of center and
            3 lengths (x_size, y_size, z_size) and heading angle around Z axis.
            Y forward, X right, Z upward. heading angle of positive X is 0,
            heading angle of positive Y is 90 degrees.
        out_filename(str): Filename.
    """

    def heading2rotmat(heading_angle):
        rotmat = np.zeros((3, 3))
        rotmat[2, 2] = 1
        cosval = np.cos(heading_angle)
        sinval = np.sin(heading_angle)
        rotmat[0:2, 0:2] = np.array([[cosval, -sinval], [sinval, cosval]])
        return rotmat

    def convert_oriented_box_to_trimesh_fmt(box):
        ctr = box[:3]
        lengths = box[3:6]
        trns = np.eye(4)
        trns[0:3, 3] = ctr
        trns[3, 3] = 1.0
        trns[0:3, 0:3] = heading2rotmat(box[6])
        box_trimesh_fmt = trimesh.creation.box(lengths, trns)
        return box_trimesh_fmt

    if len(scene_bbox) == 0:
        scene_bbox = np.zeros((1, 7))
    scene = trimesh.scene.Scene()
    for box in scene_bbox:
        scene.add_geometry(convert_oriented_box_to_trimesh_fmt(box))

    mesh_list = trimesh.util.concatenate(scene.dump())
    # save to obj file
    trimesh.io.export.export_mesh(mesh_list, out_filename, file_type='obj')

    return


def show_result(points,
                gt_bboxes,
                pred_bboxes,
                out_dir,
                filename,
                show=False,
                snapshot=False,
                pred_labels=None):
    """Convert results into format that is directly readable for meshlab.

    Args:
        points (np.ndarray): Points.
        gt_bboxes (np.ndarray): Ground truth boxes.
        pred_bboxes (np.ndarray): Predicted boxes.
        out_dir (str): Path of output directory
        filename (str): Filename of the current frame.
        show (bool, optional): Visualize the results online. Defaults to False.
        snapshot (bool, optional): Whether to save the online results.
            Defaults to False.
        pred_labels (np.ndarray, optional): Predicted labels of boxes.
            Defaults to None.
    """
    result_path = osp.join(out_dir, filename)
    mmcv.mkdir_or_exist(result_path)

    if show:
        from .open3d_vis import Visualizer

        vis = Visualizer(points)
        if pred_bboxes is not None:
            if pred_labels is None:
                vis.add_bboxes(bbox3d=pred_bboxes)
            else:
                palette = np.random.randint(
                    0, 255, size=(pred_labels.max() + 1, 3)) / 256
                labelDict = {}
                for j in range(len(pred_labels)):
                    i = int(pred_labels[j].numpy())
                    if labelDict.get(i) is None:
                        labelDict[i] = []
                    labelDict[i].append(pred_bboxes[j])
                for i in labelDict:
                    vis.add_bboxes(
                        bbox3d=np.array(labelDict[i]),
                        bbox_color=palette[i],
                        points_in_box_color=palette[i])

        if gt_bboxes is not None:
            vis.add_bboxes(bbox3d=gt_bboxes, bbox_color=(0, 0, 1))
        show_path = osp.join(result_path,
                             f'{filename}_online.png') if snapshot else None
        vis.show(show_path)

    if points is not None:
        _write_obj(points, osp.join(result_path, f'{filename}_points.obj'))

    if gt_bboxes is not None:
        # bottom center to gravity center
        gt_bboxes[..., 2] += gt_bboxes[..., 5] / 2

        _write_oriented_bbox(gt_bboxes,
                             osp.join(result_path, f'{filename}_gt.obj'))

    if pred_bboxes is not None:
        # bottom center to gravity center
        pred_bboxes[..., 2] += pred_bboxes[..., 5] / 2

        _write_oriented_bbox(pred_bboxes,
                             osp.join(result_path, f'{filename}_pred.obj'))


def show_seg_result(points,
                    gt_seg,
                    pred_seg,
                    out_dir,
                    filename,
                    palette,
                    ignore_index=None,
                    show=False,
                    snapshot=False):
    """Convert results into format that is directly readable for meshlab.

    Args:
        points (np.ndarray): Points.
        gt_seg (np.ndarray): Ground truth segmentation mask.
        pred_seg (np.ndarray): Predicted segmentation mask.
        out_dir (str): Path of output directory
        filename (str): Filename of the current frame.
        palette (np.ndarray): Mapping between class labels and colors.
        ignore_index (int, optional): The label index to be ignored, e.g.
            unannotated points. Defaults to None.
        show (bool, optional): Visualize the results online. Defaults to False.
        snapshot (bool, optional): Whether to save the online results.
            Defaults to False.
    """
    # we need 3D coordinates to visualize segmentation mask
    if gt_seg is not None or pred_seg is not None:
        assert points is not None, \
            '3D coordinates are required for segmentation visualization'

    # filter out ignored points
    if gt_seg is not None and ignore_index is not None:
        if points is not None:
            points = points[gt_seg != ignore_index]
        if pred_seg is not None:
            pred_seg = pred_seg[gt_seg != ignore_index]
        gt_seg = gt_seg[gt_seg != ignore_index]

    if gt_seg is not None:
        gt_seg_color = palette[gt_seg]
        gt_seg_color = np.concatenate([points[:, :3], gt_seg_color], axis=1)
    if pred_seg is not None:
        pred_seg_color = palette[pred_seg]
        pred_seg_color = np.concatenate([points[:, :3], pred_seg_color],
                                        axis=1)

    result_path = osp.join(out_dir, filename)
    mmcv.mkdir_or_exist(result_path)

    # online visualization of segmentation mask
    # we show three masks in a row, scene_points, gt_mask, pred_mask
    if show:
        from .open3d_vis import Visualizer
        mode = 'xyzrgb' if points.shape[1] == 6 else 'xyz'
        vis = Visualizer(points, mode=mode)
        if gt_seg is not None:
            vis.add_seg_mask(gt_seg_color)
        if pred_seg is not None:
            vis.add_seg_mask(pred_seg_color)
        show_path = osp.join(result_path,
                             f'{filename}_online.png') if snapshot else None
        vis.show(show_path)

    if points is not None:
        _write_obj(points, osp.join(result_path, f'{filename}_points.obj'))

    if gt_seg is not None:
        _write_obj(gt_seg_color, osp.join(result_path, f'{filename}_gt.obj'))

    if pred_seg is not None:
        _write_obj(pred_seg_color, osp.join(result_path,
                                            f'{filename}_pred.obj'))


def show_multi_modality_result(img,
                               gt_bboxes,
                               pred_bboxes,
                               proj_mat,
                               out_dir,
                               filename,
                               box_mode='lidar',
                               img_metas=None,
                               show=False,
                               gt_bbox_color=(61, 102, 255),
                               pred_bbox_color=(241, 101, 72)):
    """Convert multi-modality detection results into 2D results.

    Project the predicted 3D bbox to 2D image plane and visualize them.

    Args:
        img (np.ndarray): The numpy array of image in cv2 fashion.
        gt_bboxes (:obj:`BaseInstance3DBoxes`): Ground truth boxes.
        pred_bboxes (:obj:`BaseInstance3DBoxes`): Predicted boxes.
        proj_mat (numpy.array, shape=[4, 4]): The projection matrix
            according to the camera intrinsic parameters.
        out_dir (str): Path of output directory.
        filename (str): Filename of the current frame.
        box_mode (str, optional): Coordinate system the boxes are in.
            Should be one of 'depth', 'lidar' and 'camera'.
            Defaults to 'lidar'.
        img_metas (dict, optional): Used in projecting depth bbox.
            Defaults to None.
        show (bool, optional): Visualize the results online. Defaults to False.
        gt_bbox_color (str or tuple(int), optional): Color of bbox lines.
           The tuple of color should be in BGR order. Default: (255, 102, 61).
        pred_bbox_color (str or tuple(int), optional): Color of bbox lines.
           The tuple of color should be in BGR order. Default: (72, 101, 241).
    """
    if box_mode == 'depth':
        draw_bbox = draw_depth_bbox3d_on_img
    elif box_mode == 'lidar':
        draw_bbox = draw_lidar_bbox3d_on_img
    elif box_mode == 'camera':
        draw_bbox = draw_camera_bbox3d_on_img
    else:
        raise NotImplementedError(f'unsupported box mode {box_mode}')

    result_path = osp.join(out_dir, filename)
    mmcv.mkdir_or_exist(result_path)

    if show:
        show_img = img.copy()
        if gt_bboxes is not None:
            show_img = draw_bbox(
                gt_bboxes, show_img, proj_mat, img_metas, color=gt_bbox_color)
        if pred_bboxes is not None:
            show_img = draw_bbox(
                pred_bboxes,
                show_img,
                proj_mat,
                img_metas,
                color=pred_bbox_color)
        mmcv.imshow(show_img, win_name='project_bbox3d_img', wait_time=0)

    if img is not None:
        mmcv.imwrite(img, osp.join(result_path, f'{filename}_img.png'))

    if gt_bboxes is not None:
        gt_img = draw_bbox(
            gt_bboxes, img, proj_mat, img_metas, color=gt_bbox_color)
        mmcv.imwrite(gt_img, osp.join(result_path, f'{filename}_gt.png'))

    if pred_bboxes is not None:
        pred_img = draw_bbox(
            pred_bboxes, img, proj_mat, img_metas, color=pred_bbox_color)
        mmcv.imwrite(pred_img, osp.join(result_path, f'{filename}_pred.png'))


def show_plus_multi_cams_result(input, img,
                                    gt_bboxes,
                                    pred_bboxes,
                                    proj_mat,
                                    out_dir,
                                    filename,
                                    img_metas=None,
                                    show=False,
                                    gt_bbox_color=(61, 102, 255),
                                    pred_bbox_color=(241, 101, 72)):
    if isinstance(input['points'], DataContainer):
        points = input['points'].data.numpy()
        
    else:  
        points = input['points'].tensor.numpy()
    
    
    draw_bbox = draw_lidar_bbox3d_on_img
    cam_nums = len(filename)
    camera_names = ['front_left_camera', 'front_right_camera',
                    'side_left_camera', 'side_right_camera',
                    'rear_left_camera', 'rear_right_camera']
    front_image_size = (960, 540)
    side_image_size = (960, 540)
    new_size = (front_image_size[0]+side_image_size[0], 
                front_image_size[1]+side_image_size[1])
    new_img = np.zeros((new_size[1], new_size[0], 3), np.uint8)
    
    show_img_list = []
    for idx in range(cam_nums):
        this_img = img[idx]
        this_mat = proj_mat[idx]
        this_filename = filename[idx]
        camera_name = camera_names[idx]

        result_path = osp.join(out_dir, this_filename)
        mmcv.mkdir_or_exist(result_path)

        if show:
            show_img = this_img.copy()
            if gt_bboxes is not None:
                # TODO(swc): box next [done]
                show_img = draw_bbox(
                    gt_bboxes, show_img, this_mat, img_metas, color=gt_bbox_color)
            if pred_bboxes is not None:
                show_img = draw_bbox(
                    pred_bboxes,
                    show_img,
                    this_mat,
                    img_metas,
                    color=pred_bbox_color)
                
            show_img = project_pts_on_img(points, show_img, input['lidar2img'][idx])
            
            cv2.putText(show_img, f"{camera_name}", (15, 40), fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                        fontScale=1.0, color=(0, 0, 255), thickness=2)
            # mmcv.imshow(show_img, win_name='project_bbox3d_img', wait_time=0)
            show_img_list.append(show_img)
 
        if this_img is not None:
            mmcv.imwrite(this_img, osp.join(result_path, f'{this_filename}_img.png'))

        if gt_bboxes is not None:
            gt_img = draw_bbox(
                gt_bboxes, this_img, this_mat, img_metas, color=gt_bbox_color)
            mmcv.imwrite(gt_img, osp.join(result_path, f'{this_filename}_gt.png'))

        if pred_bboxes is not None:
            pred_img = draw_bbox(
                pred_bboxes, this_img, this_mat, img_metas, color=pred_bbox_color)
            mmcv.imwrite(pred_img, osp.join(result_path, f'{this_filename}_pred.png'))
            
    new_img[0:540, 0:960] = show_img_list[0]
    new_img[0:540, 960:1920] = show_img_list[0]
    
    new_img[540:1080,0:960] = show_img_list[2]
    new_img[540:1080,960:1920] = show_img_list[3]
    # img[front_image_size[1]:new_size[1], side_left_offset_x+side_image_size[0]:side_left_offset_x+side_image_size[0]*2] = img_side_right
    mmcv.imshow(new_img, win_name='project_bbox3d_img', wait_time=0)    
    

def show_plus_bevdet20_format_project_bbox_mutlicam(input,
                      gt_bbox_color=(61, 102, 255),
                      pred_bbox_color=(241, 101, 72)):
    if isinstance(input['points'], DataContainer):
        points = input['points'].data.numpy()
    else:  
        points = input['points'].tensor.numpy()
    
    if isinstance(input['gt_bboxes_3d'], DataContainer):
        gt_bboxes = input['gt_bboxes_3d'].data
    else:   
        gt_bboxes = input['gt_bboxes_3d']
     
    raw_imgs = input['raw_img']
    canvas = input['canvas']
    # show_imgs = raw_imgs
    show_imgs = canvas
    
    if len(input['img_inputs']) > 7:
        (imgs, rots, trans, intrins, post_rots,
            post_trans, bda_rot, img_feature) = input['img_inputs']
    else:
        (imgs, rots, trans, intrins, post_rots,
        post_trans, bda_rot) = input['img_inputs']
    
    draw_bbox = draw_lidar_bbox3d_on_img
    cam_nums = len(show_imgs)
    camera_names = ['front_left_camera', 'front_right_camera',
                    'side_left_camera', 'side_right_camera',
                    'rear_left_camera', 'rear_right_camera']
    front_image_size = (canvas[0].shape[1], canvas[0].shape[0]) # width * height: 960*540
    side_image_size = (canvas[2].shape[1], canvas[2].shape[0])
    new_size = (front_image_size[0]+side_image_size[0],  # 1920*1080
                front_image_size[1]+side_image_size[1])
    new_img = np.zeros((new_size[1], new_size[0], 3), np.uint8)
    
    show_img_list = []
    sample_idx = input['img_metas'].data['sample_idx'].split('.')[0]
    for idx in range(cam_nums):
        show_img = show_imgs[idx]
        if type(show_img) == torch.Tensor: # raw_img, not canvas
            show_img = show_img.permute(1, 2, 0).contiguous().numpy()
        
        bda_M = torch.from_numpy(np.eye(4, dtype=np.float32))
        bda_M[:3,:3] = bda_rot
        
        # 图像增强矩阵
        post_M = torch.from_numpy(np.eye(4, dtype=np.float32))
        post_M[:3,:3] = post_rots[idx]
        post_M[:3,3] = post_trans[idx]
        
        cam2img = np.eye(4, dtype=np.float32)
        cam2img = torch.from_numpy(cam2img)
        cam2img = intrins[idx]
        lidar2cam = torch.from_numpy(np.eye(4, dtype=np.float32))
        lidar2cam[:3,:3]=rots[idx]
        lidar2cam[:3,3]=trans[idx]
        lidar2img = cam2img.matmul(lidar2cam.matmul(bda_M.inverse()))
        # lidar2img = post_M.inverse().matmul(cam2img)
        # result_path = osp.join(out_dir, this_filename)
        # mmcv.mkdir_or_exist(result_path)

        camera_name = camera_names[idx]
        
        show_img = draw_lidar_bbox3d_on_img(
                gt_bboxes, show_img, lidar2img.numpy(), post_M, color=gt_bbox_color)
        
        if idx == 0:
            show_img = project_pts_on_img(points, show_img, lidar2img.numpy(), post_M)
        
        cv2.putText(show_img, f"{camera_name+'_'+sample_idx}", (15, 40), fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                    fontScale=1.0, color=(0, 0, 255), thickness=2)
        # mmcv.imshow(show_img, win_name='project_bbox3d_img', wait_time=0)
        show_img_list.append(show_img)
 
        # if this_img is not None:
        #     mmcv.imwrite(this_img, osp.join(result_path, f'{this_filename}_img.png'))

        # if gt_bboxes is not None:
        #     gt_img = draw_bbox(
        #         gt_bboxes, this_img, this_mat, img_metas, color=gt_bbox_color)
        #     mmcv.imwrite(gt_img, osp.join(result_path, f'{this_filename}_gt.png'))

        # if pred_bboxes is not None:
        #     pred_img = draw_bbox(
        #         pred_bboxes, this_img, this_mat, img_metas, color=pred_bbox_color)
        #     mmcv.imwrite(pred_img, osp.join(result_path, f'{this_filename}_pred.png'))
            
    new_img[0:front_image_size[1], 0:front_image_size[0]] = show_img_list[0]
    new_img[0:front_image_size[1], front_image_size[0]:new_size[0]] = show_img_list[1]
    
    new_img[front_image_size[1]:new_size[1],0:front_image_size[0]] = show_img_list[2]
    new_img[front_image_size[1]:new_size[1],front_image_size[0]:new_size[0]] = show_img_list[3]
    # img[front_image_size[1]:new_size[1], side_left_offset_x+side_image_size[0]:side_left_offset_x+side_image_size[0]*2] = img_side_right
    mmcv.imshow(new_img, win_name='project_bbox3d_img', wait_time=0)
    
    
    
    
    
    
    
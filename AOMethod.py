from skimage.transform import resize
import keras
from keras.models import Model
from keras.layers import Input, add, concatenate, Conv2D, MaxPooling2D, Conv2DTranspose, BatchNormalization, Dropout
from keras.layers.advanced_activations import LeakyReLU
from keras import backend as K
import tensorflow as tf
from skimage.transform import resize
import os
import numpy as np
import SimpleITK as sitk
import numbers
# import matplotlib.pyplot as plt
import scipy.cluster.hierarchy as hcluster
from pathlib import Path
from AONetwork import UNet
from AOColoredGraph import buildRules, buildLookup, Rule, display, getFitness
import itk
import math
import datetime
import AOGenetic
import multiprocessing

from AOUtil import datadir, timing

import multiprocessing as mp
core_num = mp.cpu_count()
config = tf.ConfigProto(
    inter_op_parallelism_threads=core_num,
    intra_op_parallelism_threads=core_num)
config.gpu_options.allow_growth = True
sess = tf.Session(config=config)

training_img_rows = 256
training_img_cols = 256
training_img_mean = 125.03862
training_img_std = 31.707973
scanning_img_rows = 333
scanning_img_cols = 333

# here itk image with itk_
# numpy image with np_
# def display_images(*images):
#     num_of_imgs = len(images)
#     f, axarr = plt.subplots(1, num_of_imgs)
#     for i in range(num_of_imgs):
#         axarr[0][i].imshow(images[i], cmap='gray')
#     plt.show()

def display_images(image):
    plt.imshow(image, cmap='gray')
    plt.show()


class ao_method():
    def __init__(self):
        self._model_weights = None

    def create_unet_model(self, training_size, output_class):
        if isinstance(training_size, numbers.Number):
            training_size = (int(training_size), int(training_size))

        model = UNet(input_shape=(training_size[0], training_size[1], 1), output_class=output_class)
        model.summary()
        return model

    @datadir
    def create_segmentation_models(self, model_weight_dir):
        abs_mwd = os.path.abspath(model_weight_dir)
        # extract a list of model weights to create detection models
        all_model_dirs = [f for f in os.listdir(model_weight_dir) if not f.startswith('.')]
        model_dictionary = {}
        if len(all_model_dirs) == 0:
            return model_dictionary #return an empty dictionary, no detection model available

        for model_dir in all_model_dirs:
            model_files = [f for f in os.listdir(os.path.join(model_weight_dir, model_dir))
                           if not f.startswith('.') and f.endswith('.h5')]
            
            if len(model_files) != 3:
                continue

            tmp_directory = {'contours': None, 'regions': None, 'centroids': None}
            for model_file in model_files:
                if 'contours' in model_file:
                    tmp_directory['contours'] = os.path.join(abs_mwd, model_dir, model_file)
                elif 'regions' in model_file:
                    tmp_directory['regions'] = os.path.join(abs_mwd, model_dir, model_file)
                elif 'centroids' in model_file:
                    tmp_directory['centroids'] = os.path.join(abs_mwd, model_dir, model_file)

            model_dictionary[model_dir] = tmp_directory

        return model_dictionary

    def create_segmentation_model(self, model_weights):


        self._model_weights = model_weights

        self._cone_centroid_model = self.create_unet_model(training_size=(training_img_rows, training_img_cols),
                                                           output_class=1)
        self._cone_centroid_model.load_weights(model_weights['centroids'])

        self._cone_contour_model = self.create_unet_model(training_size=(training_img_rows, training_img_cols),
                                                          output_class=1)
        self._cone_contour_model.load_weights(model_weights['contours'])

        self._cone_region_model = self.create_unet_model(training_size=(training_img_rows, training_img_cols),
                                                         output_class=1)
        self._cone_region_model.load_weights(model_weights['regions'])


    def preprocess_images(self, img):
        input_img_size = img.GetSize()
        img_arr = sitk.GetArrayFromImage(img)

        np_normalized_imgs = None
        if input_img_size[1] > scanning_img_rows and input_img_size[0] > scanning_img_cols:
            row_subdivision = input_img_size[1] // scanning_img_rows
            col_subdivision = input_img_size[0] // scanning_img_cols
            num_of_sub_imgs = (row_subdivision + 1) * (col_subdivision + 1)
            np_normalized_imgs = np.zeros((num_of_sub_imgs, training_img_rows, training_img_cols), dtype=np.float32)

            row_indices = np.zeros((2,), dtype=np.int32)
            col_indices = np.zeros((2,), dtype=np.int32)
            for i in range(row_subdivision + 1):
                if i == row_subdivision and i * scanning_img_rows < input_img_size[1]:
                    row_indices[0] = input_img_size[1] - scanning_img_rows
                    row_indices[1] = input_img_size[1]
                else:
                    row_indices[0] = i * scanning_img_rows
                    row_indices[1] = (i + 1) * scanning_img_rows

                for j in range(col_subdivision + 1):
                    if j == col_subdivision and j * training_img_cols < input_img_size[0]:
                        col_indices[0] = input_img_size[0] - scanning_img_cols
                        col_indices[1] = input_img_size[0]
                    else:
                        col_indices[0] = j * scanning_img_cols
                        col_indices[1] = (j + 1) * scanning_img_cols

                    sub_img = img_arr[row_indices[0]:row_indices[1], col_indices[0]:col_indices[1]]
                    sub_img = resize(sub_img, (training_img_rows, training_img_cols), preserve_range=True)
                    # sub_img = sub_img[np.newaxis, ..., np.newaxis]
                    sub_img = sub_img.astype('float32')
                    sub_img -= training_img_mean
                    sub_img /= training_img_std

                    np_normalized_imgs[j+i*(col_subdivision + 1)] = sub_img
        else:
            np_normalized_imgs = np.zeros((1, training_img_rows, training_img_cols), dtype=np.float32)
            sub_img = resize(img_arr, (training_img_rows, training_img_cols), preserve_range=True)
            sub_img = sub_img.astype('float32')
            sub_img -= training_img_mean
            sub_img /= training_img_std
            np_normalized_imgs[0] = sub_img

        np_normalized_imgs = np_normalized_imgs[..., np.newaxis]
        return np_normalized_imgs

    def _compute_probablity_map(self, model_weights, itk_img, np_normalized_imgs, model_type):
        input_img_size = itk_img.GetSize()
        prediction_model = self.create_unet_model(training_size=(training_img_rows, training_img_cols), output_class=1)
        prediction_model.load_weights(model_weights[model_type])

        res_imgs = prediction_model.predict(np_normalized_imgs, verbose=1)

        if res_imgs.shape[-1] == 1:
            res_imgs = np.squeeze(res_imgs, axis=-1)
        else:
            res_imgs = res_imgs[...,0]

        if res_imgs.shape[0] == 1:
            res_imgs = np.squeeze(res_imgs, axis=0)
            np_prob_img = resize(res_imgs, (input_img_size[1], input_img_size[0]), preserve_range=True)
        else:
            np_prob_img = np.zeros((input_img_size[1], input_img_size[0]), dtype=np.float32)
            row_subdivision = input_img_size[1] // scanning_img_rows
            col_subdivision = input_img_size[0] // scanning_img_cols

            row_indices = np.zeros((2,), dtype=np.int32)
            col_indices = np.zeros((2,), dtype=np.int32)
            for i in range(row_subdivision + 1):
                if i == row_subdivision and i * scanning_img_rows < input_img_size[1]:
                    row_indices[0] = input_img_size[1] - scanning_img_rows
                    row_indices[1] = input_img_size[1]
                else:
                    row_indices[0] = i * scanning_img_rows
                    row_indices[1] = (i + 1) * scanning_img_rows

                for j in range(col_subdivision + 1):
                    if j == col_subdivision and j * training_img_cols < input_img_size[0]:
                        col_indices[0] = input_img_size[0] - scanning_img_cols
                        col_indices[1] = input_img_size[0]
                    else:
                        col_indices[0] = j * scanning_img_cols
                        col_indices[1] = (j + 1) * scanning_img_cols

                    sub_res_img = res_imgs[j+i*(col_subdivision + 1)]
                    sub_res_img = resize(sub_res_img, (scanning_img_rows, scanning_img_cols), preserve_range=True)
                    np_prob_img[row_indices[0]:row_indices[1], col_indices[0]:col_indices[1]] = sub_res_img

        return np_prob_img

    def postprocess_probability_map(self, img_origin, fov_ratio, prob_img, prob_value, distance_value):
        res_img = np.zeros(prob_img.shape, dtype=np.uint8)
        res_img[prob_img > prob_value] = 1

        dist_img = sitk.SignedMaurerDistanceMap(sitk.GetImageFromArray(res_img), insideIsPositive=True,
                                                squaredDistance=False, useImageSpacing=False)

        dist_s_img = sitk.SmoothingRecursiveGaussian(dist_img, 1.0, True)
        # sitk.WriteImage(dist_s_img, 'dist_img1.hdr')
        dist_s_arr = sitk.GetArrayFromImage(dist_s_img)
        dist_s_arr[dist_s_arr < 0] = 0
        dist_s_img = sitk.GetImageFromArray(dist_s_arr)
        # sitk.WriteImage(dist_s_img, 'dist_img2.hdr')

        peak_filter = sitk.RegionalMaximaImageFilter()
        peak_filter.SetForegroundValue(1)
        peak_filter.FullyConnectedOn()
        peaks = peak_filter.Execute(dist_s_img)
        # sitk.WriteImage(peaks, 'peaks.hdr')

        stats = sitk.LabelShapeStatisticsImageFilter()
        stats.Execute(sitk.ConnectedComponent(peaks))
        detection_centriods = [stats.GetCentroid(l) for l in stats.GetLabels()]

        # clustering
        detection_res = []

        if len(detection_centriods) > 10:
            clusters = hcluster.fclusterdata(detection_centriods, distance_value, criterion="distance")
            min_label = np.amin(clusters)
            max_label = np.amax(clusters)
            np_detection_centroids = np.asarray(detection_centriods)
            for i in range(min_label, max_label + 1, 1):
                pts = np_detection_centroids[np.where(clusters == i)]
                xpos = 0
                ypos = 0

                for pt in pts:
                    xpos += pt[0]
                    ypos += pt[1]
                xpos /= len(pts)
                ypos /= len(pts)

                xpos = img_origin[0] + (xpos - img_origin[0]) / fov_ratio
                ypos = img_origin[1] + (ypos - img_origin[1]) / fov_ratio
                pt = (xpos, ypos)
                detection_res.append(pt)
        return detection_res

    def _otsu_extract_regions(self, itk_img):
        otsu_filter = sitk.OtsuMultipleThresholdsImageFilter()
        otsu_filter.SetNumberOfThresholds(1)
        seg_img = otsu_filter.Execute(itk_img)
        return seg_img

    def _median_filter_regions(self, itk_img, radius):
        median_filter = sitk.MedianImageFilter()
        median_filter.SetRadius(radius)
        return median_filter.Execute(itk_img)

    def _threshold_extract_region(self, itk_img, low, high):
        threshold_filter = sitk.BinaryThresholdImageFilter()
        threshold_filter.SetLowerThreshold(low)
        threshold_filter.SetUpperThreshold(high)
        threshold_filter.SetInsideValue(1)
        threshold_filter.SetOutsideValue(0)
        return threshold_filter.Execute(itk_img)

    def _erase_small_objects(self, itk_img, threshold):
        connected_img = sitk.ConnectedComponent(itk_img)
        res_img = sitk.RelabelComponent(connected_img, minimumObjectSize=threshold)
        return res_img

    def _extract_cell_centroids(self, itk_img):
        stats = sitk.LabelShapeStatisticsImageFilter()
        stats.Execute(sitk.ConnectedComponent(itk_img))
        connected_img = sitk.ConnectedComponent(itk_img)
        cell_centroids = [ stats.GetCentroid(l) for l in stats.GetLabels() if l!= 0]
        return cell_centroids

    def _erase_cell_regions_without_centroids(self, cell_region_img, cell_centroids):
        intensity_range_filter = sitk.MinimumMaximumImageFilter()
        intensity_range_filter.Execute(cell_region_img)
        min = intensity_range_filter.GetMinimum()
        max = intensity_range_filter.GetMaximum()

        # build connection between centroids and regions
        centroid_label_dict = {}
        erase_indices = []
        # initialize dict
        for i in range(int(min)+1, int(max)+1):
            centroid_label_dict[i] = []
        for i, centroid in enumerate(cell_centroids):
            x = int(centroid[0])
            y = int(centroid[1])
            val = cell_region_img.GetPixel(x, y)

            if val != min:
                centroid_label_dict[val].append(centroid)
            else:
                erase_indices.append(i)

        # erase cell regions without corresponding centroids
        np_cell_region_img = sitk.GetArrayFromImage(cell_region_img)
        for key in centroid_label_dict.keys():
            if len(centroid_label_dict[key]) == 0:
                np_cell_region_img[np_cell_region_img == key] = 0

        np_cell_region_img[np_cell_region_img>0] = 1

        # create seeds image for watersheed segmentation
        np_cell_centroid_img = np.zeros(np_cell_region_img.shape, dtype=np.uint8)
        for key in centroid_label_dict.keys():
            for centroid in centroid_label_dict[key]:
                x = int(centroid[0])
                y = int(centroid[1])
                np_cell_centroid_img[y,x] = 1

        return sitk.GetImageFromArray(np_cell_centroid_img), sitk.GetImageFromArray(np_cell_region_img)

    def _watershed_segmentation(self, cell_centroid_img, cell_region_img):
        dist_img = sitk.SignedMaurerDistanceMap(cell_region_img, insideIsPositive=False, squaredDistance=False,
                                                useImageSpacing=False)
        seeds = sitk.ConnectedComponent(cell_centroid_img)
        ws = sitk.MorphologicalWatershedFromMarkers(dist_img, seeds, markWatershedLine=True)
        ws = sitk.Mask(ws, sitk.Cast(cell_region_img, ws.GetPixelID()))
        return ws

    def _extract_watershed_cell_regions(self, ws):
        stats = sitk.LabelShapeStatisticsImageFilter()
        stats.Execute(ws)
        # Adding list of labels for translating between labels and indexes,
        # which is needed for building the connection graph (C++ style)
        cell_labels = [l for l in stats.GetLabels() if l != 0]
        cell_centroids = [stats.GetCentroid(l) for l in stats.GetLabels() if l != 0]
        cell_radius = [stats.GetEquivalentEllipsoidDiameter(l)[1]/2 for l in stats.GetLabels() if l!=0]
        return {'centroid': cell_centroids, 'radius': cell_radius, 'labels': cell_labels}
    
    @timing
    def _build_connection_graph(self, ws, cell_info):
        # Derived from C++ code with a few Python-esque optimizations
        ymax = ws.GetHeight() - 1
        xmax = ws.GetWidth() - 1
        conn_map = dict([(l, set()) for l in cell_info['labels']])
        
        row0 = [ws.GetPixel(x,0) for x in range(ws.GetWidth())]
        for y in range(ymax):
            y1 = y + 1
            row1 = [ws.GetPixel(x, y1) for x in range(ws.GetWidth())]
            for x in range(xmax):
                c00 = row0[x]
                c01 = row0[x+1]             
                c10 = row1[x]               
                c11 = row1[x+1]             
                if c00 != 0:
                    if c10 != 0 and c10 != c00:     # Up-Down
                        conn_map[c00].add(c10)
                        conn_map[c10].add(c00)
                    if c11 != 0 and c11 != c00:     # LeftUp-RightDown
                        conn_map[c00].add(c11)
                        conn_map[c11].add(c00)
                if c01 != 0:
                    if c00 != 0 and c00 != c01:     # Left-Right
                        conn_map[c00].add(c01)
                        conn_map[c01].add(c00)
                    if c10 != 0 and c10 != c01:     # RightUp-LeftDown
                        conn_map[c01].add(c10)
                        conn_map[c10].add(c01)
            row0 = row1
        #
        # Translate labels->indexes and convert them to str (for four-color coding)
        lkup = dict([(l, i) for i, l in enumerate(cell_info['labels'])])
        res = {}
        for lab, id in lkup.items():
            conns = sorted([lkup[l] for l in conn_map[lab]])
            res[str(id)] = [str(i) for i in conns]
        #
        return res

    @timing
    def _build_connection_graph_old(self, cell_info):
        # the connection groph is slight inaccurater than c++ version
        threshod = 5
        # return a connectiong graph rerpesented as an dictionary
        connection_dict = {}
        # convert dictionary key and items to string to fit for four-color coding
        for i in range(len(cell_info['centroid'])):
            connection_dict[str(i)] = []

        for i in range(len(cell_info['centroid'])-1):
            cur_centroid = cell_info['centroid'][i]
            cur_radius = cell_info['radius'][i]
            for j in range(i+1, len(cell_info['centroid'])):
                comp_centroid = cell_info['centroid'][j]
                comp_radius = cell_info['radius'][j]

                dist = math.sqrt((cur_centroid[0]-comp_centroid[0])**2 + (cur_centroid[1]-comp_centroid[1])**2)
                if dist < cur_radius + comp_radius + threshod:
                    connection_dict[str(i)].append(str(j))
                    connection_dict[str(j)].append(str(i))
        return connection_dict

    def _color_map(self, connection_dict):
        rules = buildRules(connection_dict, len(connection_dict)+100)
        colors = ["1", "2", "3", "4", "5"]
        colorLookup = {}
        for color in colors:
            colorLookup[color[0]] = color
        geneset = list(colorLookup.keys())
        optimalValue = len(rules)

        startTime = datetime.datetime.now()
        fnDisplay = lambda candidate: display(candidate, startTime)
        fnGetFitness = lambda candidate: getFitness(candidate, rules)

        best = AOGenetic.getBest(fnGetFitness, fnDisplay, len(connection_dict), optimalValue, geneset)
        # self.assertEqual(best.Fitness, optimalValue)

        keys = sorted(connection_dict.keys())
        return keys, best.Genes, colorLookup

    def _create_four_color_image(self, color_keys, color_res, color_lut, cell_info, ws_img):
        np_ws_img = sitk.GetArrayFromImage(ws_img)
        np_four_color_img = np.zeros(np_ws_img.shape, dtype=np.uint8)
        for i in range(len(color_keys)):
            key = color_keys[i]
            cell_id = int(key)
            cell_centroid = cell_info['centroid'][cell_id]
            x = int(cell_centroid[0])
            y = int(cell_centroid[1])
            cell_val = ws_img.GetPixel(x, y)

            indices = np_ws_img == cell_val
            np_four_color_img[indices] = int(color_lut[color_res[i]])

        return sitk.GetImageFromArray(np_four_color_img)

    def _create_initial_binary_masks(self, four_color_img, region_img):
        np_four_color_img = sitk.GetArrayFromImage(four_color_img)
        np_region_img = sitk.GetArrayFromImage(region_img)
        max_label = np.amax(np_four_color_img)
        min_label = np.amin(np_four_color_img)

        binary_masks = []
        if max_label == 0:
            return binary_masks

        background_label = 0
        background_indices = np.where(np_region_img == 0)
        background_label = np_four_color_img[background_indices[0][0], background_indices[1][0]]

        for i in range(min_label, max_label+1):
            if i == background_label:
                continue

            mask = np.zeros(np_four_color_img.shape, dtype=np.uint8)
            mask[np_four_color_img==i] = 1
            binary_masks.append(mask)

        return binary_masks

    def _extract_current_color_cell_centroids(self, color_mask, cell_centroids):
        color_centroids = []
        for centroid in cell_centroids:
            x = int(centroid[0])
            y = int(centroid[1])

            if color_mask[y, x] != 0:
                color_centroids.append(centroid)

        return color_centroids

    def _GAC_levelset_segmentation(self, initial_region_img, predicted_contour_img, iteration_num, contour_length):
        # try to implement this function in itk version
        StructuringElementType = itk.FlatStructuringElement[2]
        structuringElement = StructuringElementType.Ball(2)

        ErodeFilterType = itk.BinaryErodeImageFilter[itk.Image[itk.UC,2], itk.Image[itk.UC,2],
                                                     StructuringElementType]
        erode_filter = ErodeFilterType.New()
        erode_filter.SetInput(itk.GetImageFromArray(sitk.GetArrayFromImage(initial_region_img)))
        erode_filter.SetKernel(structuringElement)
        erode_filter.SetForegroundValue(1)

        # compute distance transform
        DistanceMapFilterType = itk.SignedMaurerDistanceMapImageFilter[itk.Image[itk.UC,2], itk.Image[itk.F,2]]
        distance_filter = DistanceMapFilterType.New()
        distance_filter.SetInsideIsPositive(False)
        distance_filter.SetInput(erode_filter.GetOutput())
        # display_images(itk.GetArrayFromImage(distance_filter.GetOutput()))

        # create sigmoid image from contour image
        np_contour_img = sitk.GetArrayFromImage(predicted_contour_img)
        sigmoid_img = np.absolute(1.0-np_contour_img)
        sigmoid_img = itk.GetImageFromArray(sigmoid_img)

        LevelsetType = itk.GeodesicActiveContourLevelSetImageFilter[itk.Image[itk.F,2], itk.Image[itk.F,2], itk.F]
        levelset_filter = LevelsetType.New()
        levelset_filter.SetPropagationScaling(1.0)
        levelset_filter.SetCurvatureScaling(5.0)
        levelset_filter.SetAdvectionScaling(1.0)
        levelset_filter.SetMaximumRMSError(0.01)
        levelset_filter.SetNumberOfIterations(iteration_num)
        levelset_filter.SetInput(distance_filter.GetOutput())
        levelset_filter.SetFeatureImage(sigmoid_img)

        # Extract 2d contours
        contour_extractor = itk.ContourExtractor2DImageFilter[itk.Image[itk.F,2]].New()
        contour_extractor.SetInput(levelset_filter.GetOutput())
        contour_extractor.SetContourValue(0)
        contour_extractor.Update()

        res_contours = []
        for i in range(contour_extractor.GetNumberOfOutputs()):
            vertexs = contour_extractor.GetOutput(i).GetVertexList()
            pts_num = vertexs.Size()
            if pts_num < contour_length:
                continue

            contour_pts = []
            for id in range(vertexs.Size()):
                pt = []
                pt.append(vertexs.GetElement(id)[0])
                pt.append(vertexs.GetElement(id)[1])
                contour_pts.append(pt)
            res_contours.append(contour_pts)

        return res_contours

    def _angle_2d(self, p1, p2):
        theta1 = math.atan2(p1[1], p1[0])
        theta2 = math.atan2(p2[1], p2[0])
        dtheta = theta2 - theta1
        while dtheta > math.pi:
            dtheta = dtheta - 2 * math.pi

        while dtheta < -math.pi:
            dtheta = dtheta + 2 * math.pi

        return dtheta


    def _is_point_inside_polygon(self, pt, contour):
        angle = 0.0
        p1 = [0.0, 0.0]
        p2 = [0.0, 0.0]
        for i in range(len(contour)):
            for j in range(2):
                p1[j] = contour[i][j] - pt[j]
                p2[j] = contour[(i+1)%len(contour)][j] - pt[j]
            angle += self._angle_2d(p1, p2)

        if math.fabs(angle) < math.pi:
            return False
        else:
            return True

    def _extract_connected_markers(self, res_contours, cur_color_centroids):
        contour_num = len(res_contours)
        connected_markers = {}
        for i in reversed(range(contour_num)):
            tmp_pts = []
            for pt in cur_color_centroids:
                if self._is_point_inside_polygon(pt, res_contours[i]):
                    tmp_pts.append(pt)

            if len(tmp_pts) > 1:
                connected_markers[i] = tmp_pts

        return connected_markers

    def _split_overlap_segmentation(self, connected_markers, labeled_region_img, contour_img,
                                    iteration_num, contour_length):
        region_labels = []
        for key in connected_markers.keys():
            for pt in connected_markers[key]:
                x = int(pt[0])
                y = int(pt[1])
                region_labels.append(labeled_region_img.GetPixel(x, y))

        init_img = np.zeros(sitk.GetArrayFromImage(labeled_region_img).shape, dtype=np.uint8)
        res_contours = []
        for label in region_labels:
            indices = labeled_region_img == label
            init_img[indices] = 1
            tmp_contours = self._GAC_levelset_segmentation(sitk.GetImageFromArray(init_img),
                                                           contour_img, iteration_num, contour_length)

            for contour in tmp_contours:
                if len(contour) < contour_length:
                    continue
                res_contours.append(contour)

        return res_contours

    def _extract_cell_contours(self, color_masks, predicted_contour_img, cell_centroids,
                               iteration_num, contour_length):
        res_contours = []
        for color_mask in color_masks:
            color_centroids = self._extract_current_color_cell_centroids(color_mask, cell_centroids)
            itk_color_mask = sitk.GetImageFromArray(color_mask)
            cur_res_contours = self._GAC_levelset_segmentation(itk_color_mask, predicted_contour_img, iteration_num,
                                            contour_length)
            connected_markers = self._extract_connected_markers(cur_res_contours, color_centroids)
            for key in connected_markers.keys():
                labeled_img = sitk.RelabelComponent(itk_color_mask)
                tmp_res_contours = self._split_overlap_segmentation(connected_markers, labeled_img,
                                                                    predicted_contour_img, iteration_num,
                                                                    contour_length)
                cur_res_contours.pop(key)
                cur_res_contours[key:key] = tmp_res_contours

            res_contours += cur_res_contours

        return res_contours

    def segment_cones(self, model_weights, itk_img, fov, iteration_num, contour_length):
        if not os.path.isfile(model_weights['contours']) \
                or not os.path.isfile(model_weights['regions']) \
                or not os.path.isfile(model_weights['centroids']):
            raise ValueError('could not load centroid, contour, and region weights')

        # training fov is 0.75, we need to compute fov ratio difference first
        fov_ratio = fov / 0.75

        # reample image
        euler2d = sitk.Euler2DTransform()
        # Why do we set the center?
        euler2d.SetCenter(itk_img.TransformContinuousIndexToPhysicalPoint(np.array(itk_img.GetSize()) / 2.0))
        euler2d.SetTranslation((0, 0))
        output_spacing = (itk_img.GetSpacing()[0] / fov_ratio, itk_img.GetSpacing()[1] / fov_ratio)
        output_origin = itk_img.GetOrigin()
        output_direction = itk_img.GetDirection()
        output_size = [int(itk_img.GetSize()[0]*fov_ratio + 0.5),
                       int(itk_img.GetSize()[1]*fov_ratio + 0.5)]
        itk_img = sitk.Resample(itk_img, output_size, euler2d, sitk.sitkLinear, output_origin,
                            output_spacing, output_direction)

        # normalize input image
        np_normalized_imgs = self.preprocess_images(itk_img)

        # extract binary cell regions
        np_region_prob_img = self._compute_probablity_map(model_weights, itk_img, np_normalized_imgs, 'regions')
        itk_region_prob_img = sitk.GetImageFromArray(np_region_prob_img)
        itk_region_binary_img = self._otsu_extract_regions(itk_region_prob_img)
        itk_region_binary_img = self._median_filter_regions(itk_region_binary_img, 2)
        np_region_binary_img = sitk.GetArrayFromImage(itk_region_binary_img)
        # display_images(sitk.GetArrayFromImage(itk_region_binary_img))

        # extract binary contour images
        np_contour_prob_img = self._compute_probablity_map(model_weights, itk_img, np_normalized_imgs, 'contours')
        itk_contour_prob_img = sitk.GetImageFromArray(np_contour_prob_img)
        itk_contour_binary_img = self._threshold_extract_region(itk_contour_prob_img, 0.5, 1.0)
        np_contour_binary_img = sitk.GetArrayFromImage(itk_contour_binary_img)

        # refine binary region image
        np_region_binary_img[(np_contour_binary_img == 1) & (np_region_prob_img<0.5)] = 0
        # display_images(np_region_binary_img)
        itk_region_label_img = self._erase_small_objects(sitk.GetImageFromArray(np_region_binary_img), 50)

        # extract cell centroids
        np_centroid_prob_img = self._compute_probablity_map(model_weights, itk_img, np_normalized_imgs, 'centroids')
        itk_centroid_prob_img = sitk.GetImageFromArray(np_centroid_prob_img)
        itk_centroid_binary_img = self._otsu_extract_regions(itk_centroid_prob_img)
        itk_centroid_binary_img = self._median_filter_regions(itk_centroid_binary_img, 1)
        cell_centroids = self._extract_cell_centroids(itk_centroid_binary_img)

        # watershed segmentation
        itk_centroid_binary_img, itk_region_binary_img = self._erase_cell_regions_without_centroids(
            itk_region_label_img, cell_centroids)
        watershed_seg = self._watershed_segmentation(itk_centroid_binary_img, itk_region_binary_img)
        
        cell_info = self._extract_watershed_cell_regions(watershed_seg)

        # four-color labeling
        # connection_dict = self._build_connection_graph_old(cell_info)
        connection_dict = self._build_connection_graph(watershed_seg, cell_info)
        color_keys, color_res, color_lut = self._color_map(connection_dict)
        itk_four_color_img = self._create_four_color_image(color_keys, color_res, color_lut, cell_info, watershed_seg)
        binary_masks = self._create_initial_binary_masks(itk_four_color_img, itk_region_binary_img)

        # level-set segmentation
        res_contours = self._extract_cell_contours(binary_masks, itk_contour_prob_img, cell_info['centroid'],
                                    iteration_num, contour_length)

        # scale res_contours based on the fov_ratio
        for contour_pts in res_contours:
            for pt in contour_pts:
                pt[0] = pt[0] / fov_ratio
                pt[1] = pt[1] / fov_ratio

        # image_origin = itk_img.GetOrigin()
        # image_spacing = itk_img.GetSpacing()
        # for contour_pts in res_contours:
        #     for pt in contour_pts:
        #         pt[0] = image_origin[0] + image_spacing[0] * pt[0]
        #         pt[1] = image_origin[1] + image_spacing[1] * pt[1]

        return res_contours


import os
import csv
import json
import SimpleITK as sitk
import math
import numpy as np

def write_points(file_name, pts, img_origin, img_spacing):
    with open(file_name, 'w') as annotation_file:
        annotation_writer = csv.writer(annotation_file, delimiter=',')
        for pt in pts:
            annotation_writer.writerow([(pt[0] - img_origin[0]) / img_spacing[0],
                                        (pt[1] - img_origin[1]) / img_spacing[1]])

class ao_fileIO():
    def __init__(self):
        pass

    def read_image(self, img_name):
        itk_img = sitk.ReadImage(img_name)
        #return sitk.GetArrayFromImage(itk_img), itk_img.GetSpacing(), itk_img.GetOrigin()
        return itk_img

    def read_contours(self, file_name, ignore_errors=True):
        try:
            contours = []
            wrong = 0
            with open(file_name, 'rt') as fi:
                for _line in fi:
                    line = _line.strip()
                    if len(line) == 0 or line.startswith('#'): continue
                    parts = line.replace('[', '').replace(']', '').replace('"', '').split(',')
                    contour_pts = [[float(parts[i]), float(parts[i+1])] for i in range(0, len(parts), 2)]
                    if len(contour_pts) >= 3:
                        contours.append(contour_pts)
                    else:
                        wrong += 1
            if len(contours) == 0 and wrong > 0:
                raise RuntimeError('Wrong CSV format')  
            return contours
        except Exception as ex:
            pass
        try:
            # Old ConeSegmentation had a bug in generated *_contours.csv,
            # let's try *.json instead
            fdir, fn = os.path.split(file_name)
            jpath = os.path.join(fdir, fn.split('_contours.csv')[0]+'.json')
            with open(jpath, 'r') as fi:
                data = json.load(fi)
                contours = [marker['contours'] for marker in data['markers']]
                return contours
        except Exception:
            pass    
        if ignore_errors:
            return []
        raise ex

    def write_contour(self, file_name, contours, img_origin, img_spacing):
        #file_name = file_name.replace(' ', '')
        with open(file_name, 'w') as contour_file:
            contour_writer = csv.writer(contour_file, delimiter=',')

            for contour_pts in contours:
                if len(contour_pts) == 0:
                    continue
                contour = []
                for pt in contour_pts:
                    contour.extend(pt)

                # contour_pts = []
                # for pt in contour:
                #     pt[0] = (pt[0]-img_origin[0])/img_spacing[0]
                #     pt[1] = (pt[1]-img_origin[1])/img_spacing[1]
                #     contour_pts.append(pt[0])
                #     contour_pts.append(pt[1])
                # contour_writer.writerow(contour_pts)
                contour_writer.writerow(contour)

    def write_contours(self, dir_name, input_data, suffix='.csv'):
        cnt = 0
        for (img_name, img, contours) in zip(input_data['image names'], input_data['images'],
                                        input_data['contours']):
            if len(contours) == 0: continue
            fn = img_name + suffix
            contour_path = os.path.join(dir_name, fn)
            self.write_contour(contour_path, contours, img.GetOrigin(), img.GetSpacing())
            cnt += 1
        return cnt




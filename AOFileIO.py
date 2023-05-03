import os
import csv
import json
import math
import io, codecs

import numpy as np
import imageio
import SimpleITK as sitk

from AOMetaList import *

# def write_points(file_name, pts, img_origin, img_spacing):
#     with open(file_name, 'w') as annotation_file:
#         annotation_writer = csv.writer(annotation_file, delimiter=',')
#         for pt in pts:
#             annotation_writer.writerow([(pt[0] - img_origin[0]) / img_spacing[0],
#                                         (pt[1] - img_origin[1]) / img_spacing[1]])

class ao_fileIO():
    def __init__(self):
        pass

    def read_image(self, img_name):
        if isinstance(img_name, str):
            itk_img = sitk.ReadImage(img_name)
            #return sitk.GetArrayFromImage(itk_img), itk_img.GetSpacing(), itk_img.GetOrigin()
            return itk_img
        numpy_img = image.imread(img_name)
        itk_img = sitk.GetImageFromArray(numpy_img)
        return itk_img

    def read_contours(self, file_name, ignore_errors=True):
        try:
            contours = MetaList(meta=MetaMap(MetaRecord(user='=Diskfile=')))
            wrong = 0
            nextmetaid = 1
            metareg = {}
            with open(file_name, 'rt') as fi:
                for _line in fi:
                    if _line.startswith('#meta'):
                        try:
                            rdr = csv.reader(io.StringIO(_line))
                            for ln in rdr:
                                kwarg = json.loads(ln[1])
                                break
                            mrec = contours.meta.addmeta(MetaRecord(**kwarg), setdefault=True, newid=True)
                            metareg[nextmetaid] = mrec
                            nextmetaid += 1
                        except Exception:
                            pass
                        continue
                    line = _line.strip()
                    if line.startswith('#del'):
                        try:
                            parts = line.split(',')
                            cremeta = metareg[int(parts[1])]
                            delmeta = metareg[int(parts[2])]
                            obj = ContourGeom(float(parts[3]), float(parts[4]), float(parts[5]))
                            contours.meta.addobj(obj, cremeta)
                            contours.meta.delobj(obj, delmeta)
                        except Exception:
                            pass
                        continue
                    if len(line) == 0 or line.startswith('#'): continue
                    parts = line.replace('[', '').replace(']', '').replace('"', '').split(',')
                    contour_pts = [[float(parts[i]), float(parts[i+1])] for i in range(0, len(parts), 2)]
                    if len(contour_pts) >= 3:
                        contours.append(contour_pts)
                    else:
                        wrong += 1
            if len(contours) == 0 and wrong > 0:
                raise RuntimeError('Wrong CSV format')  
        except Exception as ex:
            contours = None
        if contours is None:
            try:
                # Old ConeSegmentation had a bug in generated *_contours.csv,
                # let's try *.json instead
                fdir, fn = os.path.split(file_name)
                jpath = os.path.join(fdir, fn.split('_contours.csv')[0]+'.json')
                with open(jpath, 'r') as fi:
                    data = json.load(fi)
                    contours = MetaList([marker['contours'] for marker in data['markers']])
                    return contours
            except Exception:
                #pass    
                if ignore_errors:
                    contours = MetaList([])
                else:
                    raise ex
        contours.meta.addmeta(MetaRecord(), setdefault=True)
        return contours
    #
    def _write_contour_to_fileobj(self, contour_file, contours, img_origin, img_spacing):
        contour_writer = csv.writer(contour_file, delimiter=',')
        #
        def flatten_contours(contour_pts):
            contour = []
            for pt in contour_pts:
                contour.append(f'{pt[0]:.3f}')
                contour.append(f'{pt[1]:.3f}')
            return contour
        #
        if hasattr(contours, 'iteroutput'):
            for row in contours.iteroutput():
                contour_writer.writerow(row)
            return
        #
        if hasattr(contours, 'itermapping'):
            for meta, contour_list in contours.itermapping():
                mstr = json.dumps(meta.as_jsonable())
                contour_writer.writerow(['#meta', mstr])
                for contour_pts in contour_list:
                    contour = flatten_contours(contour_pts)
                    contour_writer.writerow(contour)
            return
        #
        for contour_pts in contours:
            if len(contour_pts) == 0:
                continue
            contour = flatten_contours(contour_pts)
            contour_writer.writerow(contour)
    #
    def write_contour(self, file_name, contours, img_origin, img_spacing):
        if isinstance(file_name, str):
            #file_name = file_name.replace(' ', '')
            with open(file_name, 'w', newline='', encoding='utf-8') as contour_file:
                self._write_contour_to_fileobj(contour_file, contours, img_origin, img_spacing)
        elif isinstance(file_name, io.BytesIO):
            StreamWriter = codecs.getwriter('utf-8')
            self._write_contour_to_fileobj(StreamWriter(file_name), contours, img_origin, img_spacing)
        else:
            self._write_contour_to_fileobj(file_name, contours, img_origin, img_spacing)

    def write_contours(self, dir_name, input_data, suffix='.csv'):
        cnt = 0
        for (img_name, img, contours) in zip(input_data['image names'], input_data['images'],
                                        input_data['contours']):
            if hasattr(contours, 'contours'): contours = contours.contours
            if len(contours) == 0: continue
            fn = img_name + suffix
            contour_path = os.path.join(dir_name, fn)
            self.write_contour(contour_path, contours, img.GetOrigin(), img.GetSpacing())
            cnt += 1
        return cnt
    
    def write_annotation_stats(self, dir_name, input_data, suffix='_stats.csv'):
        cnt = 0
        for (img_name, contours) in zip(input_data['image names'], input_data['contours']):
            if hasattr(contours, 'contours'): contours = contours.contours
            if len(contours) == 0 or not hasattr(contours, 'gettracker'): continue
            tracker = contours.gettracker()
            fn = img_name + suffix
            stats_file_path = os.path.join(dir_name, fn)
            with open(stats_file_path, 'w', newline='', encoding='utf-8') as stats_file:
                wr = csv.writer(stats_file, delimiter=',')
                wr.writerow(['ID', 'Date', 'Origin', 'User',
                            'Active', 'Created', 'Deleted', 'Modified', 'Comment'])
                nextid = 1
                for mrec, stat in tracker.getstats():
                    wr.writerow([nextid, mrec.when, mrec.who, mrec.realWho,
                            stat.active, stat.created, stat.deleted, stat.modified, mrec.description])
                    nextid += 1
            cnt += 1
        return cnt

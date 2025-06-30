import os
import csv
import json
import math
import io, codecs

import numpy as np
import imageio
import SimpleITK as sitk

from AOMetaList import *
from AOUtil import contourCenter, shoelaceArea

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
        else:
            numpy_img = imageio.imread(img_name)
            itk_img = sitk.GetImageFromArray(numpy_img)
        ndim = len(itk_img.GetSize())
        itk_img.SetOrigin([0]*ndim)
        itk_img.SetSpacing([1]*ndim)
        return itk_img

    def read_contours(self, file_name, ignore_errors=True):
        try:
            acount = 0
            contours = MetaList(meta=MetaMap(MetaRecord(user='=Diskfile=')))
            wrong = 0
            nextmetaid = 1
            metareg = {}
            cframe = 0
            aa = {cframe: contours}
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
                    if line.startswith('#frame'):
                        nextmetaid = 1
                        metareg = {}
                        cframe = int(line.split(',')[1])
                        acount += len(contours)
                        contours = MetaList(meta=MetaMap(MetaRecord(user='=Diskfile=')))
                        aa[cframe] = contours
                        continue
                    if line.startswith('#unchecked'):
                        aa['unchecked'] = [int(fr) for fr in line.split(',')[1:]]
                        continue
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
            acount += len(contours)
            if acount == 0 and wrong > 0:
                raise RuntimeError('Wrong CSV format')  
        except Exception as ex:
            aa = None
        if aa is None:
            try:
                # Old ConeSegmentation had a bug in generated *_contours.csv,
                # let's try *.json instead
                fdir, fn = os.path.split(file_name)
                jpath = os.path.join(fdir, fn.split('_contours.csv')[0]+'.json')
                with open(jpath, 'rt') as fi:
                    data = json.load(fi)
                    contours = MetaList([marker['contours'] for marker in data['markers']])
                    contours.meta.addmeta(MetaRecord(), setdefault=True)
                    return {0:contours}
            except Exception:
                #pass    
                if ignore_errors:
                    aa = {0:MetaList([])}
                else:
                    raise ex
        for fr, contours in aa.items():
            if hasattr(contours, 'meta'):
                contours.meta.addmeta(MetaRecord(), setdefault=True)
        return aa
    #
    def _write_contour_to_fileobj(self, contour_file, all_pts, img_origin, img_spacing):
        contour_writer = csv.writer(contour_file, delimiter=',')
        #
        def flatten_contours(contour_pts):
            contour = []
            for pt in contour_pts:
                contour.append(f'{pt[0]:.3f}')
                contour.append(f'{pt[1]:.3f}')
            return contour
        #
        if not isinstance(all_pts, dict):
            all_pts = {0:all_pts}
        unchecked = None
        if 'unchecked' in all_pts:
            unchecked = all_pts.pop('unchecked')
        #
        for fr in sorted(all_pts.keys()):
            contours = all_pts[fr]
            contour_writer.writerow(['#frame', fr])
            #
            if hasattr(contours, 'iteroutput'):
                for row in contours.iteroutput():
                    contour_writer.writerow(row)
                continue
            #
            if hasattr(contours, 'itermapping'):
                for meta, contour_list in contours.itermapping():
                    mstr = json.dumps(meta.as_jsonable())
                    contour_writer.writerow(['#meta', mstr])
                    for contour_pts in contour_list:
                        contour = flatten_contours(contour_pts)
                        contour_writer.writerow(contour)
                continue
            #
            for contour_pts in contours:
                if len(contour_pts) == 0:
                    continue
                contour = flatten_contours(contour_pts)
                contour_writer.writerow(contour)
        #
        if unchecked:
            contour_writer.writerow(['#unchecked']+unchecked)

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

    # def write_contours(self, dir_name, input_data, suffix='.csv'):
    #     cnt = 0
    #     for (img_name, img, contours) in zip(input_data['image names'], input_data['images'],
    #                                     input_data['contours']):
    #         if hasattr(contours, 'contours'): contours = contours.contours
    #         if len(contours) == 0: continue
    #         fn = img_name + suffix
    #         contour_path = os.path.join(dir_name, fn)
    #         self.write_contour(contour_path, contours, img.GetOrigin(), img.GetSpacing())
    #         cnt += 1
    #     return cnt
    
    # def write_contour_extras(self, dir_name, input_data, xoptions):
    #     for (img_name, img, contours) in zip(input_data['image names'], input_data['images'],
    #                                     input_data['contours']):
    #         if hasattr(contours, 'contours'): contours = contours.contours
    #         if len(contours) == 0: continue
    #         write_contour_extra(self, dir_name, img_name, contours, xoptions)
    #
    def write_contour_extra(self, dir_name, img_name, all_pts, xoptions):
        if not isinstance(all_pts, dict):
            all_pts = {0:all_pts}
        if xoptions.get('detections', False):
            fn = img_name + '_detections.csv'
            contour_path = os.path.join(dir_name, fn)
            print(contour_path)
            with open(contour_path, 'w', newline='', encoding='utf-8') as contour_file:
                contour_writer = csv.writer(contour_file, delimiter=',')
                contour_writer.writerow(['# Contour center point coordinates: XCenter YCenter'])
                for fr in sorted(all_pts.keys()):
                    contours = all_pts[fr]
                    contour_writer.writerow(['#frame', fr])
                    #
                    for contour_pts in contours:
                        if len(contour_pts) == 0:
                            continue
                        x, y = contourCenter(contour_pts)
                        contour_writer.writerow(['%0.4f' % (x,), '%0.4f' % (y,)])
        #
        if xoptions.get('measurements', False):
            fn = img_name + '_measurements.csv'
            contour_path = os.path.join(dir_name, fn)
            print(contour_path)
            with open(contour_path, 'w', newline='', encoding='utf-8') as contour_file:
                contour_writer = csv.writer(contour_file, delimiter=',')
                contour_writer.writerow(['# Contour measurements: Area Diameter'])
                for fr in sorted(all_pts.keys()):
                    contours = all_pts[fr]
                    contour_writer.writerow(['#frame', fr])
                    #
                    for contour_pts in contours:
                        if len(contour_pts) == 0:
                            continue
                        area = shoelaceArea(contour_pts)
                        diam = math.sqrt(area / math.pi) * 2.
                        contour_writer.writerow(['%0.4f' % (area,), '%0.4f' % (diam,)])
    #
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

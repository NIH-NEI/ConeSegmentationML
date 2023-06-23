__all__ = ('datadir', 'UndoOp', 'UndoEntry', 'SegmentClipper', 'isPointInside', 'isIntersected', 'contourCenter',
           'findContour', 'optimizeContour', 'contourChanged', 'smoothContour',)

import sys, os, datetime
import enum
from collections import namedtuple
import math

import numpy as np
from scipy import interpolate

# Decorator for functions accessing data via relative paths
if hasattr(sys, '_MEIPASS'):
    # When distributed as single exe, temporarily switch to the _MEIPASS prefix,
    #    call decorated function, then switch back. This allows functions accessing data
    #    via paths relative to '.' work the same way
    def datadir(func):
        def wrapper(*args, **kwarg):
            cwd = os.getcwd()
            try:
                os.chdir(sys._MEIPASS)
                rc = func(*args, **kwarg)
            finally:
                os.chdir(cwd)
            return rc
        return wrapper
    #
    def timing(func):
        return func
else:
    # Decorator for functions accessing data via relative paths
    # If distributed as single dir (or while in dev sandbox), do nothing.
    def datadir(func):
        return func
    #
    # Profiling decorator for non-single-exe env only
    def timing(func):
        def wrapper(*args, **kwarg):
            start_ts = datetime.datetime.now()
            rc = func(*args, **kwarg)
            print(func.__name__+'() done in:', str(datetime.datetime.now()-start_ts))
            return rc
        return wrapper

@enum.unique
class UndoOp(enum.IntEnum):
    Added = 0
    Removed = 1
    Image = 2

UndoEntry = namedtuple('UndoEntry', ['op', 'last', 'data'])

# Clip a segment into a rectangular area
class SegmentClipper(object):
    Inside = 0
    Left = 1
    Right = 2
    Bottom = 4
    Top = 8
    def __init__(self, rect_dim):
        self.w = rect_dim[0]
        self.h = rect_dim[1]
        self.x0 = 0.001
        self.y0 = 0.001
        self.x1 = self.w - 0.001
        self.y1 = self.h - 0.001
    #
    def bnd_points(self):
        pts = []
        for y in (-self.h*10, self.h*0.5, self.h*11):
            for x in (-self.w*10, self.w*0.5, self.w*11):
                pt = (x, y)
                if self.outCode(pt) != self.Inside:
                    pts.append(pt)
        return pts
    #
    def clip(self, pt0, pt1):
        #return (pt0, pt1)
        oc0 = self.outCode(pt0)
        oc1 = self.outCode(pt1)
        if oc0 != self.Inside and oc1 != self.Inside:
            return None
        #while oc0 != self.Inside or oc1 != self.Inside:
        if oc0 != self.Inside:
            pt0 = self.intersect(pt1, pt0, oc0)
            if pt0 is None: return None
            oc0 = self.outCode(pt0)
        elif oc1 != self.Inside:
            pt1 = self.intersect(pt0, pt1, oc1)
            if pt1 is None: return None
            oc1 = self.outCode(pt1)
        return [pt0, pt1]
    #
    def intersect(self, pt0, pt1, oc):
        dx = pt1[0] - pt0[0]
        dy = pt1[1] - pt0[1]
        if oc & self.Left:
            y = pt0[1] + dy * (self.x0 - pt0[0]) / dx;
            if y>=self.y0 and y<=self.y1:
                return (self.x0, y)
        if oc & self.Right:
            y = pt0[1] + dy * (self.x1 - pt0[0]) / dx;
            if y>=self.y0 and y<=self.y1:
                return (self.x1, y)
        if oc & self.Top:
            x = pt0[0] + dx * (self.y0 - pt0[1]) / dy;
            if x>=self.x0 and x<=self.x1:
                return (x, self.y0)
        if oc & self.Bottom:
            x = pt0[0] + dx * (self.y1 - pt0[1]) / dy;
            if x>=self.x0 and x<=self.x1:
                return (x, self.y1)
        return None
    #
    def outCode(self, pt):
        oc = 0
        if pt[0] < self.x0:
            oc |= self.Left
        if pt[0] > self.x1:
            oc |= self.Right
        if pt[1] < self.y0:
            oc |= self.Top
        if pt[1] > self.y1:
            oc |= self.Bottom
        return oc
    #


# Winding number test for a point in a polygon
# Adapted from: http://geomalgorithms.com/a03-_inclusion.html

# isLeft(): tests if a point is Left|On|Right of an infinite line.
#    Input:  three points P0, P1, and P2
#    Return: >0 for P2 left of the line through P0 and P1
#            =0 for P2  on the line
#            <0 for P2  right of the line
#
# P1, P2, P3 are lists [x,y] or tuples (x,y)
def isLeft(P0, P1, P2):
    return (P1[0]-P0[0])*(P2[1]-P0[1]) - (P2[0]-P0[0])*(P1[1]-P0[1])

# wn_PnPoly(): winding number test for a point in a polygon
#      Input:   pt = a point, list or tuple (x,y)
#               contour = vertex points of a polygon, a collection of points
#      Return:  wn = the winding number (=0 only when pt is outside)
def wn_PnPoly(pt, contour):
    poly = list(contour)
    n = len(poly)
    poly.append(poly[0])    # make poly[0] == poly[n+1]
    wn = 0
    for i in range(n):
        if poly[i][1] < pt[1]:          # start y <= pt.y
            if poly[i+1][1] > pt[1]:    # an upward crossing
                if isLeft(poly[i], poly[i+1], pt) > 0:  # pt left of edge
                    wn += 1             # have a valid up intersect
        else:                           # start y > P.y (no test needed)
            if poly[i+1][1] <= pt[1]:   # a downward crossing
                if isLeft(poly[i], poly[i+1], pt) < 0:  # pt right of edge
                    wn -= 1             # have a valid down intersect
    return wn

def isPointInside(pt, contour):
    return wn_PnPoly(pt, contour) != 0

# Simplified -- looks for the edges of one polygon inside another
def isIntersected(contour1, contour2):
    for pt in contour1:
        if wn_PnPoly(pt, contour2) != 0:
            return True
#     for pt in contour2:
#         if wn_PnPoly(pt, contour1) != 0:
#             return True
    return False

# Simplified -- "center mass" of the vertex points
def contourCenter(contour):
    n = len(contour)
    x = y = 0.
    for pt in contour:
        x += pt[0]
        y += pt[1]
    if n > 0:
        x /= n
        y /= n
    return (x, y)

# Find contour containing point pt
def findContour(pt, contours):
    for i, contour in enumerate(contours):
        if wn_PnPoly(pt, contour) != 0:
            return i
    return -1

def dist(pt1, pt2):
    return math.sqrt((pt1[0]-pt2[0])**2 + (pt1[1]-pt2[1])**2)

# Optimize a contour by removing vertices too close to each other
def optimizeContour(contour, min_dist=1.5):
    n = len(contour)
    if n < 5:
        return contour
    pt1 = contour[0]
    res = [pt1]
    for i in range(1, n):
        pt2 = contour[i]
        cur_dist = dist(pt1, pt2)
        if cur_dist >= min_dist:
            res.append(pt2)
            pt1 = pt2
    if len(res) < 5: return contour
    if dist(res[0], res[-1]) < min_dist:
        res.pop()
    return res

# Test if a contour is sufficiently changed (after an edit operation)
def contourChanged(oldc, newc, tolerance=0.005):
    if len(oldc) != len(newc):
        return True
    for pt1, pt2 in zip(oldc, newc):
        if math.fabs(pt1[0] - pt2[0]) > tolerance:
            return True
        if math.fabs(pt1[1] - pt2[1]) > tolerance:
            return True
    return False

# Parameterize contour on angle [(x, y), ...] -> [(x, y, a), ...]
def _parameterizeContour(contour):
    res = []
    xc, yc = contourCenter(contour)
    assert not math.isnan(xc)
    assert not math.isnan(yc)
    rad = 0.
    for pt in contour:
        x = pt[0]
        y = pt[1]
        dx = x - xc
        dy = y - yc
        a = math.atan2(dy, dx)
        res.append((x, y, a))
        rad += dx*dx + dy*dy
    midr = []
    for i in range(1,len(res)-2):
        d1 = res[i][2] - res[i-1][2]
        d2 = res[i+1][2] - res[i][2]
        if (d1<0 and d2>0) or (d1>0 and d2<0) or (d1==0.):
            continue
        midr.append(res[i])
    res[1:-1] = midr
    if len(contour) > 0:
        rad = math.sqrt(rad/len(contour))
    res.sort(key=lambda x: x[2])
    return res, rad, xc, yc
        
# Smooth contour using Smoothing Splines
# https://docs.scipy.org/doc/scipy/tutorial/interpolate/smoothing_splines.html
def smoothContour(contour, min_dist=1.5, factor=0.5, clip=None):
    try:
        pi2 = np.pi*2.
        _pcont, rad, xc, yc = _parameterizeContour(contour)
        pcont = [(x, y, a-pi2) for x,y,a in _pcont[-5:]] + _pcont + \
            [(x, y, a+pi2) for x,y,a in _pcont[0:5]]
        
        xx = [p[0]-xc for p in pcont]
        yy = [p[1]-yc for p in pcont]
        t = [p[2] for p in pcont]
        
        npnew = int(4.*np.pi*rad)
        tnew = [j*pi2/npnew - np.pi for j in range(npnew)]
        
        tck = interpolate.splrep(t, xx, s=1)
        xx = interpolate.splev(tnew, tck, der=0)
        tck = interpolate.splrep(t, yy, s=1)
        yy = interpolate.splev(tnew, tck, der=0)
        
        _, rad1, dxc, dyc = _parameterizeContour([(x,y) for x,y in zip(xx,yy)])
        xc += dxc
        yc += dyc
        xx = [x-dxc for x in xx]
        yy = [y-dyc for y in yy]
        
        t = [a-pi2 for a in tnew[-10:]] + tnew + [a+pi2 for a in tnew[0:10]]
        xx = xx[-10:] + xx + xx[0:10]
        yy = yy[-10:] + yy + yy[0:10]
        
        tck = interpolate.splrep(t, xx, s=math.sqrt(npnew)*factor)
        xnew = interpolate.splev(tnew, tck, der=0)
        tck = interpolate.splrep(t, yy, s=math.sqrt(npnew)*factor)
        ynew = interpolate.splev(tnew, tck, der=0)
        
        _cont = [(x,y) for x,y in zip(xnew,ynew)]
        rsq = rad1*rad1*9.
        pt0 = None
        for pt1 in _cont:
            x, y = pt1
            assert x*x+y*y < rsq, 'distance to the center too big'
            if not pt0 is None:
                assert dist(pt0, pt1) < 9., f'distance between vertices too big {pt0} {pt1}'
            pt0 = pt1
        _, rad2, dxc, dyc = _parameterizeContour(_cont)
        xc += 0.275
        sc = (rad1 + 0.075) / rad2
        
        res = []
        res.append((xnew[0]*sc + xc, ynew[0]*sc + yc))
        for x, y in zip(xnew, ynew):
            pt = (x*sc+xc, y*sc+yc)
            cur_dist = dist(res[-1], pt)
            if cur_dist >= min_dist:
                res.append(pt)
        if clip:
            xmax = clip[0] - 1.001
            ymax = clip[1] - 1.001
            res = [(x, y) for x, y in res if x>0. and x<xmax and y>0. and y<ymax]
            assert len(res) > 5
        return res
    except Exception as ex:
        #print(ex)
        return contour
#



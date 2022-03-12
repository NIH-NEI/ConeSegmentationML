__all__ = ('UndoOp', 'UndoEntry', 'SegmentClipper', 'isPointInside', 'isIntersected', 'contourCenter',
           'findContour', 'optimizeContour', 'contourChanged', 'datadir')

import sys, os, datetime
import enum
from collections import namedtuple
import math

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


import os
import sys
import platform
import enum
import vtk
from vtk.util import numpy_support
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from PyQt5 import QtCore, QtWidgets, QtGui
import numpy as np
import math
import SimpleITK as sitk
from scipy.spatial import Voronoi
from AOUtil import SegmentClipper, contourCenter
#from AOFileIO import write_points

# Patch for QVTKRenderWindowInteractor crashing on some key events, such as Shift+;
try:
    import vtk.qt.QVTKRenderWindowInteractor as qtvtk
    # The original _qt_key_to_key_sym() function in the module may return None,
    # which causes uncaught exception in keyPressEvent(). Let's replace it
    # with a patched version, which converts None to empty string ''.
    def _qt_key_to_key_sym_patch(func):
        def wrapper(*args, **kwarg):
            return func(*args, **kwarg) or ''
        return wrapper
    qtvtk._qt_key_to_key_sym = _qt_key_to_key_sym_patch(qtvtk._qt_key_to_key_sym)
except Exception as ex:
    pass

@enum.unique
class MouseOp(enum.IntEnum):
    Normal = 0
    DrawContour = 1
    EditContour = 2
    EraseSingle = 3
    EraseMulti = 4

class AnnotationInteractor(vtk.vtkInteractorStyleImage):
    def __init__(self, mouse_mode = MouseOp.Normal, parent=None):
        self._win = platform.system().lower() == 'windows'
        self._mouse_mode = mouse_mode
        self.parent = parent
        self.mainWin = None if self.parent is None else self.parent.parent
        #
        self.AddObserver("LeftButtonPressEvent", self.leftButtonPressEvent)
        self.AddObserver("LeftButtonReleaseEvent", self.leftButtonReleaseEvent)
        self.AddObserver("MiddleButtonPressEvent", self.middleButtonPressEvent)
        self.AddObserver("MiddleButtonReleaseEvent", self.middleButtonReleaseEvent)
        self.AddObserver("RightButtonPressEvent", self.rightButtonPressEvent)
        self.AddObserver("MouseMoveEvent", self.mouseMoveEvent)
        self.AddObserver("EnterEvent", self.enterEvent)
        self.AddObserver("LeaveEvent", self.leaveEvent)
        self.AddObserver("KeyPressEvent", self.keyPressEvent)
        self.AddObserver("KeyReleaseEvent", self.keyReleaseEvent)
        self._tolerance = 0.
        #
        self._mouse_down = False
        self._ctrl_down = False
        self._shift_down = False
        self._alt_down = False
        self._mouse_scroll = False
        self._mouse_in = False
        self._contour_pts = []
        #
        self.ci = (127.5, 255.)
    #
    @property
    def tolerance(self):
        return self._tolerance
    @tolerance.setter
    def tolerance(self, val):
        self._tolerance = val
    #   
    @property
    def mouse_mode(self):
        return self._mouse_mode
    @mouse_mode.setter
    def mouse_mode(self, val):
        self._mouse_mode = val
    #
    @property
    def contour_pts(self):
        if self.parent is None:
            o = (0., 0.)
            s = (1., 1.)
        else:
            o = self.parent._image_data.GetOrigin()
            s = self.parent._image_data.GetSpacing()
        return[[pt[0]/s[0]-o[0], pt[1]/s[1]-o[1]] for pt in self._contour_pts]
    #
    def _GetControlKey(self):
        # Check for either Ctrl or Alt (Ctrl+mouse does not work on Mac)
        if self.GetInteractor().GetControlKey():
            return True
        return not self._win and self._alt_down
    def leftButtonPressEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        if not self._mouse_in:
            self._ctrl_down = self._shift_down = False
            obj.OnLeftButtonDown()
            return
        inter = self.GetInteractor()
        self._mouse_scroll = False
        if inter.GetShiftKey():
            self._shift_down = self._mouse_scroll = True
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.SizeAllCursor)
            obj.OnLeftButtonDown()
            return
        #
        self.ci = self.parent.color_info
        self._mouse_down = True
        op = self.mouse_mode
        if self._GetControlKey() and op in (MouseOp.DrawContour, MouseOp.EditContour):
            op = MouseOp.EraseSingle
            self._ctrl_down = True
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CrossCursor)
        if op in (MouseOp.DrawContour, MouseOp.EraseMulti, MouseOp.EraseSingle, MouseOp.EditContour):
            if op == MouseOp.EditContour:
                self._mouse_down = False
            mx, my = inter.GetEventPosition()
            pick_value = inter.GetPicker().Pick(mx, my, 0, self.GetDefaultRenderer())
            if pick_value == 0: return
            self._contour_pts = [inter.GetPicker().GetPickPosition()]
            if op == MouseOp.EraseSingle:
                if not self.mainWin is None:
                    self.mainWin.RemoveContourAt(self.contour_pts[0])
            elif op == MouseOp.EditContour:
                if not self.mainWin is None:
                    self.mainWin.EditContourAt(self.contour_pts[0])
            else:
                self.parent.set_interactive_contour(self._contour_pts)
                self.parent.reset_view(False)
            return
        obj.OnLeftButtonDown()
    def leftButtonReleaseEvent(self, obj, event):
        self._mouse_down = False
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        if self._mouse_scroll:
            self._mouse_scroll = False
            if self._shift_down:
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.OpenHandCursor)
            obj.OnLeftButtonUp()
            return
        inter = self.GetInteractor()
        op = self.mouse_mode
        if self._GetControlKey() and op in (MouseOp.DrawContour, MouseOp.EditContour):
            op = MouseOp.EraseSingle
            self._ctrl_down = True
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CrossCursor)
        if op == MouseOp.EraseSingle:
            return
        if op in (MouseOp.DrawContour, MouseOp.EraseMulti):
            mx, my = inter.GetEventPosition()
            pick_value = inter.GetPicker().Pick(mx, my, 0, self.GetDefaultRenderer())
            self._contour_pts.append(inter.GetPicker().GetPickPosition())
            self.parent.set_interactive_contour(None)
            self.parent.reset_view(False)
            if pick_value == 0: return
            if self.mainWin is None: return
            if op == MouseOp.DrawContour:
                self.mainWin.AddContour(self.contour_pts)
            elif op == MouseOp.EraseMulti:
                self.mainWin.RemoveContoursInside(self.contour_pts)
            return
        _ci = self.parent.color_info
        if math.fabs(_ci[0] - self.ci[0]) > 0.01 or math.fabs(_ci[1] - self.ci[1]) > 0.01:
            self.mainWin.push_color_undo(self.ci)
        obj.OnLeftButtonUp()
    def _update_mouse_pos(self, event):
        if self.mainWin is None or not hasattr(self.mainWin, 'trackMousePos'):
            return
        inter = self.GetInteractor()
        mx, my = inter.GetEventPosition()
        pick_value = inter.GetPicker().Pick(mx, my, 0, self.GetDefaultRenderer())
        if pick_value == 0:
            x = y = -1
        else:
            x, y, z = inter.GetPicker().GetPickPosition()
            o = self.parent._image_data.GetOrigin()
            s = self.parent._image_data.GetSpacing()
            x = x/s[0] - o[0]
            y = y/s[1] - o[1]
        self.mainWin.trackMousePos(x, y)
    def mouseMoveEvent(self, obj, event):
        self._update_mouse_pos(event)
        if self._shift_down:
            obj.OnMouseMove()
            return
        if self._mouse_down:
            inter = self.GetInteractor()
            op = self.mouse_mode
            if self._GetControlKey() and op in (MouseOp.DrawContour, MouseOp.EditContour):
                op = MouseOp.EraseSingle
            if op in (MouseOp.DrawContour, MouseOp.EraseMulti, MouseOp.EraseSingle):
                mx, my = inter.GetEventPosition()
                pick_value = inter.GetPicker().Pick(mx, my, 0, self.GetDefaultRenderer())
                if pick_value == 0: return
                if op == MouseOp.EraseSingle:
                    self._contour_pts = [inter.GetPicker().GetPickPosition()]
                    if not self.mainWin is None:
                        self.mainWin.RemoveContourAt(self.contour_pts[0])
                else:
                    self._contour_pts.append(inter.GetPicker().GetPickPosition())
                    self.parent.set_interactive_contour(self._contour_pts)
                    self.parent.reset_view(False)
                return
        obj.OnMouseMove()
    def middleButtonPressEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        if self._mouse_in:
            self._mouse_scroll = True
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.SizeAllCursor)
        obj.OnMiddleButtonDown()
    def middleButtonReleaseEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        self._mouse_scroll = False
        if self._shift_down:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.OpenHandCursor)
        obj.OnMiddleButtonUp()
    def rightButtonPressEvent(self, obj, event):
        inter = self.GetInteractor()
        if inter.GetAltKey():
            mx, my = inter.GetEventPosition()
            pick_value = inter.GetPicker().Pick(mx, my, 0, self.GetDefaultRenderer())
            if pick_value == 0: return
            self._contour_pts = [inter.GetPicker().GetPickPosition()]
            if not self.mainWin is None:
                self.mainWin.RemoveContourAt(self.contour_pts[0])
            return
        obj.OnRightButtonDown()
    def enterEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        if not self._mouse_in:
            self._mouse_in = True
            if self._shift_down:
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.OpenHandCursor)
            elif self._ctrl_down and self.mouse_mode in (MouseOp.DrawContour, MouseOp.EditContour):
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CrossCursor)
        else:
            # If a second OnEnter() received without a matching OnLeave(),
            # the QVTKWidget does not have keyboard focus and it won't receive OnKeyUp() for Shift either.
            # Like the user tried to drag the mouse from another widget while holding Shift down.
            self._shift_down = self._ctrl_down = False
        obj.OnEnter()
    def leaveEvent(self, obj, event):
        self._mouse_in = False
        self._alt_down = False
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        obj.OnLeave()
    def keyPressEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        key = self.GetInteractor().GetKeySym()
        if key == 'Alt_L':
            self._alt_down = True
            if not self._win: key = 'Control_L'
        if not self._mouse_in:
            obj.OnKeyPress()
            return
        if key == 'Up':
            if not self.mainWin is None:
                self.mainWin.previous_image()
            return
        elif key == 'Down':
            if not self.mainWin is None:
                self.mainWin.next_image()
            return
        elif key == 'Shift_L':
            self._shift_down = True
            if not self._mouse_scroll:
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.OpenHandCursor)
        elif key == 'Control_L':
            if self.mouse_mode == MouseOp.EditContour:
                self.parent.cancel_editing()
            if self.mouse_mode in (MouseOp.DrawContour, MouseOp.EditContour):
                self._ctrl_down = True
                QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CrossCursor)
                return
        if not self._alt_down:
            obj.OnKeyPress()
    def keyReleaseEvent(self, obj, event):
        while QtWidgets.QApplication.overrideCursor():
            QtWidgets.QApplication.restoreOverrideCursor()
        key = self.GetInteractor().GetKeySym()
        if key == 'Alt_L':
            self._alt_down = False
            if not self._win: key = 'Control_L'
        if (key == 'Up' or key == 'Down'):
            return
        if self._ctrl_down:
            if key == 'Control_L':
                self._ctrl_down = False
                return
        if key == 'Shift_L':
            self._shift_down = False
        obj.OnKeyRelease()
    #
    
class ao_visualization():
    def __init__(self, vtk_widget, parent=None):
        self._vtk_widget = vtk_widget
        self.parent = parent
        self._draw_image()
        #
        self.edit_idx = None
        self._saved_contours = None
        self._contour_centers = []
        #
        self._contour_width = 2
        self._glyph_size = 6.
        self._interactive_contour_width = 3
        self._edited_contour_width = 3
        self._voronoi_contour_width = 1.5
        
        self._draw_contours()
        self._draw_interactive_contours()
        self._draw_edited_contours()
        self._draw_voronoi_contours()
        self._draw_background_region()
        #
        self._render = vtk.vtkRenderer()
        self._render.AddActor(self._bkg_actor)
        self._render.AddActor(self._image_actor)
        self._render.AddActor(self._gray_actor)
        self._render.AddActor(self._contour_actor)
        self._render.AddActor(self._annotated_actor)
        self._render.AddActor(self._interactive_contour_actor)
        self._render.AddActor(self._voronoi_contour_actor)
        self._render.ResetCamera()

        self._vtk_widget.GetRenderWindow().AddRenderer(self._render)
        
        self._style = AnnotationInteractor(parent=self)
        self._style.SetDefaultRenderer(self._render)
        self._vtk_widget.SetInteractorStyle(self._style)

        iren = self._vtk_widget.GetRenderWindow().GetInteractor()
        
        self._edited_contour_widget.SetInteractor(iren)
        self._edited_contour_widget.On()
        self._edited_contour_widget.Initialize()
        self._edited_contour_widget.Off()
        self._edited_contour_widget.AddObserver(vtk.vtkCommand.DisableEvent, self._on_edited_contour)
        
        iren.Initialize()
        iren.Start()
        
        self._visibility = True
        self._contour_visibility = True
        self._glyph_visibility = False
        self._interpolation = True
        self._voronoi = False
        self._image_visibility = True
    #
    def _on_edited_contour(self, obj, event):
        # print('_on_edited_contour:', obj, '->', event)
        if self.edit_idx is None or self.parent is None:
            return
        o = self._image_data.GetOrigin()
        s = self._image_data.GetSpacing()
        polyData = obj.GetRepresentation().GetContourRepresentationAsPolyData()
        contour_pts = [[polyData.GetPoint(i)[0]/s[0]-o[0], polyData.GetPoint(i)[1]/s[1]-o[1]] \
            for i in range(polyData.GetNumberOfPoints())]
        self.parent.UpdateContour(self.edit_idx, contour_pts)
    #
    def _draw_image(self):
        self._image_data = vtk.vtkImageData()
        self._image_data.SetDimensions(1, 1, 1)
        if vtk.VTK_MAJOR_VERSION <= 5:
            self._image_data.SetNumberOfScalarComponents(1)
            self._image_data.SetScalarTypeToUnsignedChar()
        else:
            self._image_data.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)

        self._image_actor = vtk.vtkImageActor()
        self._image_actor.GetMapper().SetInputData(self._image_data)

    def _draw_contours(self):
        self._contour_points = vtk.vtkPoints()
        self._contour_points.SetDataTypeToFloat()
        self._contour_lines = vtk.vtkCellArray()
        self._contour_poly = vtk.vtkPolyData()
        self._contour_poly.SetPoints(self._contour_points)
        self._contour_poly.SetLines(self._contour_lines)

        self._contour_mapper = vtk.vtkPolyDataMapper()
        self._contour_mapper.SetInputData(self._contour_poly)
        self._contour_mapper.ScalarVisibilityOff()

        self._contour_actor = vtk.vtkActor()
        self._contour_actor.SetMapper(self._contour_mapper)
        self._contour_actor.GetProperty().SetColor(0, 1., 0)
        self._contour_actor.GetProperty().SetLineWidth(self._contour_width)

        self._gray_points = vtk.vtkPoints()
        self._gray_points.SetDataTypeToFloat()
        self._gray_lines = vtk.vtkCellArray()
        self._gray_poly = vtk.vtkPolyData()
        self._gray_poly.SetPoints(self._gray_points)
        self._gray_poly.SetLines(self._gray_lines)

        self._gray_mapper = vtk.vtkPolyDataMapper()
        self._gray_mapper.SetInputData(self._gray_poly)
        self._gray_mapper.ScalarVisibilityOff()

        self._gray_actor = vtk.vtkActor()
        self._gray_actor.SetMapper(self._gray_mapper)
        self._gray_actor.GetProperty().SetColor(0.25, 0.25, 0.25)
        self._gray_actor.GetProperty().SetOpacity(0.75)
        self._gray_actor.GetProperty().SetLineWidth(self._contour_width)
        
        self._annotated_points = vtk.vtkPoints()
        self._annotated_points.SetDataTypeToFloat()
        self._annotated_poly = vtk.vtkPolyData()
        self._annotated_poly.SetPoints(self._annotated_points)

        self._annotated_glyph_source = vtk.vtkGlyphSource2D()
        self._annotated_glyph_source.SetGlyphTypeToCross()
        self._annotated_glyph_source.SetScale(self._glyph_size*0.5)

        self._annotated_glyph = vtk.vtkGlyph3D()
        self._annotated_glyph.SetSourceConnection(self._annotated_glyph_source.GetOutputPort())
        self._annotated_glyph.SetInputData(self._annotated_poly)

        self._annotated_mapper = vtk.vtkDataSetMapper()
        self._annotated_mapper.SetInputConnection(self._annotated_glyph.GetOutputPort())
        self._annotated_mapper.ScalarVisibilityOff()

        self._annotated_actor = vtk.vtkActor()
        self._annotated_actor.SetMapper(self._annotated_mapper)
        self._annotated_actor.GetProperty().SetColor(0, 1, 0)
        
    def _draw_interactive_contours(self):
        self._interactive_contour_points = vtk.vtkPoints()
        self._interactive_contour_points.SetDataTypeToFloat()
        self._interactive_contour_lines = vtk.vtkCellArray()
        self._interactive_contour_poly = vtk.vtkPolyData()
        self._interactive_contour_poly.SetPoints(self._interactive_contour_points)
        self._interactive_contour_poly.SetLines(self._interactive_contour_lines)

        self._interactive_contour_mapper = vtk.vtkPolyDataMapper()
        self._interactive_contour_mapper.SetInputData(self._interactive_contour_poly)
        self._interactive_contour_mapper.ScalarVisibilityOff()

        self._interactive_contour_actor = vtk.vtkActor()
        self._interactive_contour_actor.SetMapper(self._interactive_contour_mapper)
        self._interactive_contour_actor.GetProperty().SetColor(217/255.0, 95.0/255.0, 14.0/255.0)
        self._interactive_contour_actor.GetProperty().SetLineWidth(self._interactive_contour_width)
        
    def _draw_edited_contours(self):
        self._edited_contour_points = vtk.vtkPoints()
        self._edited_contour_points.SetDataTypeToFloat()
        self._edited_contour_lines = vtk.vtkCellArray()
        self._edited_contour_poly = vtk.vtkPolyData()
        self._edited_contour_poly.SetPoints(self._edited_contour_points)
        self._edited_contour_poly.SetLines(self._edited_contour_lines)
        
        self._edited_contour_rep = rep = vtk.vtkOrientedGlyphContourRepresentation()
        rep.GetLinesProperty().SetColor(1., 1., 0.)
        rep.GetLinesProperty().SetLineWidth(self._edited_contour_width)
        rep.GetActiveProperty().SetColor(1., 0.5, 0.5)
        rep.GetActiveProperty().SetLineWidth(self._edited_contour_width)
        rep.GetActiveProperty().SetPointSize(20)
        rep.GetProperty().SetColor(1., 0.5, 0.5)
        rep.SetLineInterpolator(vtk.vtkLinearContourLineInterpolator())
        rep.SetAlwaysOnTop(True)
        
        self._edited_contour_widget = wid = vtk.vtkContourWidget()
        wid.SetRepresentation(rep)
    #
    def _draw_voronoi_contours(self):
        self._voronoi_contour_points = vtk.vtkPoints()
        self._voronoi_contour_points.SetDataTypeToFloat()
        self._voronoi_contour_lines = vtk.vtkCellArray()
        self._voronoi_contour_poly = vtk.vtkPolyData()
        self._voronoi_contour_poly.SetPoints(self._voronoi_contour_points)
        self._voronoi_contour_poly.SetLines(self._voronoi_contour_lines)

        self._voronoi_contour_mapper = vtk.vtkPolyDataMapper()
        self._voronoi_contour_mapper.SetInputData(self._voronoi_contour_poly)
        self._voronoi_contour_mapper.ScalarVisibilityOff()

        self._voronoi_contour_actor = vtk.vtkActor()
        self._voronoi_contour_actor.SetMapper(self._voronoi_contour_mapper)
        self._voronoi_contour_actor.GetProperty().SetColor(5./255.0, 196.0/255.0, 196.0/255.0)
        self._voronoi_contour_actor.GetProperty().SetLineWidth(self._voronoi_contour_width)
    #
    def _draw_background_region(self):
        self._bkg_points = vtk.vtkPoints()
        self._bkg_points.SetDataTypeToFloat()
        self._bkg_cells = vtk.vtkCellArray()
        self._bkg_poly = vtk.vtkPolyData()
        self._bkg_poly.SetPoints(self._bkg_points)
        self._bkg_poly.SetPolys(self._bkg_cells)
        self._bkg_tri_filter = vtk.vtkTriangleFilter()
        self._bkg_tri_filter.SetInputData(self._bkg_poly)
        self._bkg_mapper = vtk.vtkPolyDataMapper()
        self._bkg_mapper.SetInputConnection(self._bkg_tri_filter.GetOutputPort())
        self._bkg_mapper.ScalarVisibilityOff()
        self._bkg_actor = vtk.vtkActor()
        self._bkg_actor.SetMapper(self._bkg_mapper)
        self._bkg_actor.GetProperty().SetColor(0., 0., 0.)
        self._bkg_actor.SetVisibility(False)
    #
    def initialization(self):
        self._image_data.Initialize()
        self._image_data.Modified()

        self._contour_points.Initialize()
        self._contour_lines.Initialize()
        self._contour_poly.Modified()

        self._gray_points.Initialize()
        self._gray_lines.Initialize()
        self._gray_poly.Modified()

        self._annotated_points.Initialize()
        self._annotated_poly.Modified()

        self._interactive_contour_points.Initialize()
        self._interactive_contour_lines.Initialize()
        self._interactive_contour_poly.Modified()

        self._edited_contour_points.Initialize()
        self._edited_contour_lines.Initialize()
        self._edited_contour_poly.Modified()
        self._edited_contour_widget.Off()

        self._voronoi_contour_points.Initialize()
        self._voronoi_contour_lines.Initialize()
        self._voronoi_contour_poly.Modified()
        
        self._bkg_points.Initialize()
        self._bkg_cells.Initialize()
        self._bkg_poly.Modified()
    #
    def _change_camera_orientation(self):
        self._render.ResetCamera()
        camera = self._render.GetActiveCamera()
        fp = camera.GetFocalPoint()
        p = camera.GetPosition()
        dist = (fp[0]-p[0])*(fp[0]-p[0])+(fp[1]-p[1])*(fp[1]-p[1])+(fp[2]-p[2])*(fp[2]-p[2])
        dist = math.sqrt(dist)
        camera.SetPosition(fp[0], fp[1], fp[2]-dist)
        camera.SetViewUp(0.0, -1.0, 0.0)
        camera.SetParallelProjection(True)
        #camera.SetParallelScale(camera.GetParallelScale() * 0.66667)

    def reset_view(self, camera_flag=False):
        if camera_flag:
            self._change_camera_orientation()
        self._vtk_widget.GetRenderWindow().Render()

    def _convert_nparray_to_vtk_image(self, itk_img, vtk_img):
        img_size = itk_img.GetSize()
        img_orig = itk_img.GetOrigin()
        img_spacing = itk_img.GetSpacing()
        n_array = sitk.GetArrayFromImage(itk_img)
        v_image = numpy_support.numpy_to_vtk(n_array.flat)
        vtk_img.SetOrigin(img_orig[0], img_orig[1], 0)
        vtk_img.SetSpacing(img_spacing[0], img_spacing[1], 1.0)
        vtk_img.SetDimensions(img_size[0], img_size[1], 1)
        vtk_img.AllocateScalars(numpy_support.get_vtk_array_type(n_array.dtype), 1)
        vtk_img.GetPointData().SetScalars(v_image)

    def set_image(self, itk_img):
        self._image_data.Initialize()
        self._convert_nparray_to_vtk_image(itk_img, self._image_data)
        self._image_data.Modified()
        #
        img_origin = self._image_data.GetOrigin()
        img_spacing = self._image_data.GetSpacing()
        img_dim = self._image_data.GetDimensions()
        x0 = img_origin[0]
        x1 = img_origin[0] + (img_dim[0] - 0.999) * img_spacing[0]
        y0 = img_origin[1]
        y1 = img_origin[1] + (img_dim[1] - 0.999) * img_spacing[1]
        self._bkg_points.Initialize()
        self._bkg_cells.Initialize()
        self._bkg_cells.InsertNextCell(4)
        self._bkg_points.InsertNextPoint(x0, y0, -0.0001)
        self._bkg_cells.InsertCellPoint(0)
        self._bkg_points.InsertNextPoint(x1, y0, -0.0001)
        self._bkg_cells.InsertCellPoint(1)
        self._bkg_points.InsertNextPoint(x1, y1, -0.0001)
        self._bkg_cells.InsertCellPoint(2)
        self._bkg_points.InsertNextPoint(x0, y1, -0.0001)
        self._bkg_cells.InsertCellPoint(3)
        self._bkg_points.Modified()
        self._bkg_cells.Modified()
        self._bkg_poly.Modified()

    def set_contours(self, contour_pts, edit_idx=None):
        if not self.edit_idx is None:
            self._edited_contour_widget.Off()
        self._contour_points.Initialize()
        self._contour_lines.Initialize()
        self._gray_points.Initialize()
        self._gray_lines.Initialize()
        self._annotated_points.Initialize()
        img_origin = self._image_data.GetOrigin()
        img_spacing = self._image_data.GetSpacing()
        
        gray_contours = []

        self._contour_centers = []
        edited_pts = None
        for i, _pts in enumerate(contour_pts):
            pts = [(img_origin[0] + img_spacing[0] * pt[0], img_origin[1] + img_spacing[1] * pt[1]) for pt in _pts]
            x, y = contourCenter(pts)
            self._contour_centers.append((x, y))
            if not edit_idx is None and edit_idx == i:
                edited_pts = _pts
                continue
            if len(pts) == 0:
                continue
            
            if hasattr(contour_pts, 'isGray') and contour_pts.isGray(_pts):
                gray_contours.append(pts)
            else:
                self._annotated_points.InsertNextPoint(x, y, -0.001)
            self._contour_lines.InsertNextCell(len(pts)+1)
            start_index = self._contour_points.GetNumberOfPoints()
            for id, pt in enumerate(pts):
                self._contour_points.InsertNextPoint(pt[0], pt[1], -0.001)
                self._contour_lines.InsertCellPoint(id+start_index)
            self._contour_lines.InsertCellPoint(start_index)
            
        for i, pts in enumerate(gray_contours):
            self._gray_lines.InsertNextCell(len(pts)+1)
            start_index = self._gray_points.GetNumberOfPoints()
            for id, pt in enumerate(pts):
                self._gray_points.InsertNextPoint(pt[0], pt[1], -0.002)
                self._gray_lines.InsertCellPoint(id+start_index)
            self._gray_lines.InsertCellPoint(start_index)

        self._contour_points.Modified()
        self._contour_lines.Modified()
        self._contour_poly.Modified()
        self._gray_points.Modified()
        self._gray_lines.Modified()
        self._gray_poly.Modified()
        self._annotated_points.Modified()
        self._annotated_poly.Modified()
        if not edited_pts is None:
            self.enable_edited_contour(edited_pts)
            self._saved_contours = contour_pts
        elif not self.edit_idx is None:
            # self.disable_edited_contour()
            edit_idx = None
            self._saved_contours = None
        self.edit_idx = edit_idx
        self.updateVoronoiContours()
        #self.reset_view()
    #
    def set_interactive_contour(self, pts=None):
        self._interactive_contour_points.Initialize()
        self._interactive_contour_lines.Initialize()

        if not pts is None:
            self._interactive_contour_points.SetNumberOfPoints(len(pts))
            self._interactive_contour_lines.InsertNextCell(len(pts))
            for i, pt in enumerate(pts):
                self._interactive_contour_points.SetPoint(i, pt[0], pt[1], -0.001)
                self._interactive_contour_lines.InsertCellPoint(i)

        self._interactive_contour_points.Modified()
        self._interactive_contour_lines.Modified()
        self._interactive_contour_poly.Modified()
    #
    def set_voronoi_contours(self, contour_pts):
        self._voronoi_contour_points.Initialize()
        self._voronoi_contour_lines.Initialize()
        img_origin = self._image_data.GetOrigin()
        img_spacing = self._image_data.GetSpacing()

        for i, pts in enumerate(contour_pts):
            if len(pts) == 0:
                continue

            self._voronoi_contour_lines.InsertNextCell(len(pts)+1)
            start_index = self._voronoi_contour_points.GetNumberOfPoints()
            for id, pt in enumerate(pts):
                self._voronoi_contour_points.InsertNextPoint(pt[0], pt[1], -0.001)
                self._voronoi_contour_lines.InsertCellPoint(id+start_index)
            self._voronoi_contour_lines.InsertCellPoint(start_index)

        self._voronoi_contour_points.Modified()
        self._voronoi_contour_lines.Modified()
        self._voronoi_contour_poly.Modified()
        self.reset_view()
    #
    def enable_edited_contour(self, pts):
        o = self._image_data.GetOrigin()
        s = self._image_data.GetSpacing()
        
        n = len(pts)
        self._edited_contour_points.Initialize()
        self._edited_contour_lines.Initialize()
        self._edited_contour_points.SetNumberOfPoints(n)
        self._edited_contour_lines.InsertNextCell(n+1)
        for i, pt in enumerate(pts):
            self._edited_contour_points.SetPoint(i, o[0] + s[0]*pt[0], o[1] + s[1]*pt[1], -0.001)
            self._edited_contour_lines.InsertCellPoint(i)
        self._edited_contour_lines.InsertCellPoint(0)
        #
        self._edited_contour_points.Modified()
        self._edited_contour_lines.Modified()
        self._edited_contour_poly.Modified()
        self._edited_contour_widget.On()
        self._edited_contour_widget.Initialize(self._edited_contour_poly, 1)
        self.reset_view()
    def disable_edited_contour(self):
        self._edited_contour_points.Initialize()
        self._edited_contour_lines.Initialize()
        self._edited_contour_poly.Modified()
        self._edited_contour_widget.Off()
        self.reset_view()
    #
    def cancel_editing(self):
        if not self._saved_contours is None:
            self.set_contours(self._saved_contours)
            self.reset_view()
    def abort_editing(self):
        self.edit_idx = None
        self.cancel_editing()
    #
    @property
    def contour_visibility(self):
        return self._contour_visibility
    @contour_visibility.setter
    def contour_visibility(self, st):
        self._contour_visibility = st
        self._contour_actor.SetVisibility(self._contour_visibility and self._visibility)
        self._gray_actor.SetVisibility(self._contour_visibility and self._visibility)
    #
    @property
    def contour_width(self):
        return self._contour_width
    @contour_width.setter
    def contour_width(self, width):
        self._contour_width = width
        self._contour_actor.GetProperty().SetLineWidth(self._contour_width)
        self._gray_actor.GetProperty().SetLineWidth(self._contour_width)
    #
    @property
    def contour_color(self):
        r, g, b = self._contour_actor.GetProperty().GetColor()
        c = QtGui.QColor(int(r*255.), int(g*255.), int(b*255.))
        return c.name()
    @contour_color.setter
    def contour_color(self, v):
        c = QtGui.QColor(v)
        if c.isValid():
            self._contour_actor.GetProperty().SetColor(c.red()/255., c.green()/255., c.blue()/255.)
    #
    @property
    def glyph_visibility(self):
        return self._glyph_visibility
    @glyph_visibility.setter
    def glyph_visibility(self, st):
        self._glyph_visibility = st
        self._annotated_actor.SetVisibility(self._glyph_visibility and self._visibility)
    #
    @property
    def glyph_size(self):
        return self._glyph_size
    @glyph_size.setter
    def glyph_size(self, sz):
        self._glyph_size = sz
        self._annotated_glyph_source.SetScale(self._glyph_size*0.5)
    #
    @property
    def glyph_color(self):
        r, g, b = self._annotated_actor.GetProperty().GetColor()
        c = QtGui.QColor(int(r*255.), int(g*255.), int(b*255.))
        return c.name()
    @glyph_color.setter
    def glyph_color(self, v):
        c = QtGui.QColor(v)
        if c.isValid():
            self._annotated_actor.GetProperty().SetColor(c.red()/255., c.green()/255., c.blue()/255.)
    #
    @property
    def voronoi(self):
        return self._voronoi
    @voronoi.setter
    def voronoi(self, st):
        self._voronoi = st
        self.updateVoronoiContours()
    #
    @property
    def voronoi_width(self):
        return self._voronoi_contour_width
    @voronoi_width.setter
    def voronoi_width(self, sz):
        self._voronoi_contour_width = sz
        self._voronoi_contour_actor.GetProperty().SetLineWidth(self._voronoi_contour_width)
    #
    @property
    def voronoi_color(self):
        r, g, b = self._voronoi_contour_actor.GetProperty().GetColor()
        c = QtGui.QColor(int(r*255.), int(g*255.), int(b*255.))
        return c.name()
    @voronoi_color.setter
    def voronoi_color(self, v):
        c = QtGui.QColor(v)
        if c.isValid():
            self._voronoi_contour_actor.GetProperty().SetColor(c.red()/255., c.green()/255., c.blue()/255.)
    #
    @property
    def interpolation(self):
        return self._interpolation
    @interpolation.setter
    def interpolation(self, st):
        self._interpolation = bool(st)
        if self._interpolation:
            self._image_actor.InterpolateOn()
        else:
            self._image_actor.InterpolateOff()
    #
    @property
    def image_visibility(self):
        return self._image_actor.GetVisibility()
    @image_visibility.setter
    def image_visibility(self, st):
        self._image_actor.SetVisibility(st)
        self._bkg_actor.SetVisibility(not st)
    #
    @property
    def background_color(self):
        r, g, b = self._bkg_actor.GetProperty().GetColor()
        c = QtGui.QColor(int(r*255.), int(g*255.), int(b*255.))
        return c.name()
    @background_color.setter
    def background_color(self, v):
        c = QtGui.QColor(v)
        if c.isValid():
            self._bkg_actor.GetProperty().SetColor(c.red()/255., c.green()/255., c.blue()/255.)
    #
    DISPLAY_ATTRIBUTES = ('contour_visibility', 'contour_width', 'contour_color',
            'glyph_visibility', 'glyph_size', 'glyph_color',
            'voronoi', 'voronoi_width', 'voronoi_color',
            'interpolation', 'image_visibility', 'background_color',)
    @property
    def displaySettings(self):
        return dict([(a, getattr(self,a)) for a in self.DISPLAY_ATTRIBUTES])
    @displaySettings.setter
    def displaySettings(self, o):
        try:
            for a, v in o.items():
                setattr(self, a, v)
        except Exception:
            pass
    #
    @property
    def visibility(self):
        return self._visibility
    @visibility.setter
    def visibility(self, st):
        self._visibility = st
        self._contour_actor.SetVisibility(self._contour_visibility and self._visibility)
        self._gray_actor.SetVisibility(self._contour_visibility and self._visibility)
        self._annotated_actor.SetVisibility(self._glyph_visibility and self._visibility)
        self.updateVoronoiContours()
        self.reset_view()
    #
    def reset_color(self):
        self._image_actor.GetProperty().SetColorLevel(127.5)
        self._image_actor.GetProperty().SetColorWindow(255.)
        self._vtk_widget.GetRenderWindow().Render()
    #    
    @property
    def color_info(self):
        p = self._image_actor.GetProperty()
        return (p.GetColorLevel(), p.GetColorWindow())
    @color_info.setter
    def color_info(self, v):
        try:
            cval, cwin = v
        except Exception:
            cval = 127.5
            cwin = 255.
        self._image_actor.GetProperty().SetColorLevel(cval)
        self._image_actor.GetProperty().SetColorWindow(cwin)
        self._vtk_widget.GetRenderWindow().Render()
    #
    def get_image_dimensions(self):
        s = self._image_data.GetSpacing()
        d = self._image_data.GetDimensions()
        return (s[0]*d[0], s[1]*d[1], 1.)
    #
    def updateVoronoiContours(self):
        _vor_contours = []
        if self._visibility and self._voronoi and len(self._contour_centers) > 2:
            clip = SegmentClipper(self.get_image_dimensions())
            annos = self._contour_centers + clip.bnd_points()
            vor = Voronoi(np.array(annos))
            vertices = [(v[0], v[1]) for v in vor.vertices]
            ptis = set()
            for rg in vor.regions:
                if len(rg) < 2: continue
                idx0 = -1
                for idx in rg:
                    if idx >=0 and idx0 >= 0:
                        pti = (idx, idx0) if idx < idx0 else (idx0, idx)
                        ptis.add(pti)
                    idx0 = idx
                idx = rg[0]
                if idx >=0 and idx0 >= 0:
                    pti = (idx, idx0) if idx < idx0 else (idx0, idx)
                    ptis.add(pti)
            #
            for (i0, i1) in ptis:
                pts = clip.clip(vertices[i0], vertices[i1])
                if pts:
                    _vor_contours.append(pts)
        self.set_voronoi_contours(_vor_contours)
    #

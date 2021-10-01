import os
import sys
import time
import math

import numpy as np
from skimage.io import imread
import SimpleITK as sitk
from PyQt5 import QtCore, QtWidgets, QtGui

class ao_snap_dialog(QtWidgets.QDialog):
    IMG_SCALES = [0.5, 0.75, 1., 2., 3., 4., 5., 6., 8., 10., 12., 16.]
    save_geom = None
    save_scale = 2.
    def __init__(self, parent=None):
        super(ao_snap_dialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setSizeGripEnabled(True)
        #
        self.qImg = self.emptyImage()
        self.pixmap = None
        self.img_path = None
        self.interpolation = True
        #
        self.contours = []
        self.contour_width = 2
        self.contour_color = (0, 0xFF, 0)
        #
        self._setup_layout()
    #
    def _setup_layout(self):
        view_layout = QtWidgets.QGridLayout()
        view_layout.setRowStretch(0, 1)
        view_layout.setRowStretch(1, 0)
        view_layout.setColumnStretch(0, 0)
        view_layout.setColumnStretch(1, 5)
        view_layout.setColumnStretch(2, 0)
        view_layout.setColumnStretch(3, 1)
        view_layout.setColumnStretch(4, 0)
        view_layout.setColumnStretch(5, 0)
        self.setLayout(view_layout)
        #
        self.img_lab = QtWidgets.QLabel()
        self.img_lab.setBackgroundRole(QtGui.QPalette.Base)
        self.img_lab.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        self.scrl = QtWidgets.QScrollArea()
        self.scrl.setBackgroundRole(QtGui.QPalette.Dark)
        self.scrl.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
        self.scrl.setWidget(self.img_lab)
        #
        self.sc_lab = QtWidgets.QLabel('Scale:')
        self.sc_slider = sl = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        sl.setRange(0, len(self.IMG_SCALES)-1)
        sl.setPageStep(1)
        sl.setTickInterval(1)
        sl.setTickPosition(QtWidgets.QSlider.TicksBelow)
        sl.setMinimumWidth(100)
        sl.valueChanged.connect(self.onScaleSlider)
        self.sc_text = QtWidgets.QLabel('')
        self.sc_text.setMinimumWidth(50)
        self.saveBtn = QtWidgets.QPushButton('Save', clicked=self.onSaveBtn)
        self.closeBtn = QtWidgets.QPushButton('Close', clicked=self.close)
        #
        view_layout.addWidget(self.scrl, 0, 0, 1, 6)
        #
        view_layout.addWidget(self.sc_lab, 1, 0)
        view_layout.addWidget(self.sc_slider, 1, 1)
        view_layout.addWidget(self.sc_text, 1, 2)
        view_layout.addWidget(self.saveBtn, 1, 4)
        view_layout.addWidget(self.closeBtn, 1, 5)
        #
    #
    def closeEvent(self, e):
        ao_snap_dialog.save_geom = self.geometry()
        ao_snap_dialog.save_scale = self.scale
        QtWidgets.QDialog.closeEvent(self, e)
    def showEvent(self, e):
        QtWidgets.QDialog.showEvent(self, e)
        if not self.save_geom is None:
            self.setGeometry(self.save_geom)
        else:
            geom = QtWidgets.QApplication.primaryScreen().geometry()
            self.resize(geom.width() * 56 // 100, geom.height() * 56 // 100)
            self.move(geom.width() * 18 // 100, geom.height() * 18 // 100)
            ao_snap_dialog.save_geom = self.geometry()
        self.scale = self.save_scale
        self.renderImage()
    #
    def emptyImage(self):
        rgb_data = np.empty(shape=(16, 16, 3), dtype=np.uint8)
        rgb_data[:,:,:] = 0x80
        self.qImg = QtGui.QImage(rgb_data.data, 16, 16, 16*3, QtGui.QImage.Format_RGB888)
    #
    def setImageData(self, img_path, img_data=None, interpolation=True):
        self.img_path = img_path
        self.interpolation = interpolation
        if not img_path:
            self.qImg = self.emptyImage()
            return
        if isinstance(img_data, sitk.SimpleITK.Image):
            img_data = sitk.GetArrayFromImage(img_data)
        elif not isinstance(img_data, np.ndarray):
            img_data = None
        if img_data is None:
            try:
                img_data = imread(img_path)
            except Exception:
                pass
        if img_data is None or len(img_data.shape) < 2:
            self.qImg = self.emptyImage()
            return
        while len(img_data.shape) > 3:
            img_data = img_data[0]
        nc = 1
        w = img_data.shape[1]
        h = img_data.shape[0]
        if len(img_data.shape) == 3:
            nc = img_data.shape[2]
            if nc == 2 or nc > 4:
                img_data = img_data[:,:,0]
                nc = 1
            elif nc == 4:
                img_data = img_data[:,:,0:3]
                nc = 3
        if img_data.dtype != np.uint8:
            lmin = np.min(img_data)
            lmax = np.max(img_data)
            if lmax < lmin + 0.001:
                lmax = lmin + 0.001
            sc = 255. / (lmax - lmin)
            img_data = ((img_data.astype(np.float32) - lmin) * sc).astype(np.uint8)
        if nc != 3:
            rgb_img = np.empty(shape=(h, w, 3), dtype=np.uint8)
            rgb_img[:,:,0] = img_data
            rgb_img[:,:,1] = img_data
            rgb_img[:,:,2] = img_data
        else:
            rgb_img = img_data
        self.qImg = QtGui.QImage(rgb_img.data, w, h, w*3, QtGui.QImage.Format_RGB888)
    #
    def setContours(self, contours, contour_width=2, contour_color=None):
        self.contour_width = contour_width if contour_width >= 1 and contour_width < 20 else 2
        self.contour_color = tuple(contour_color) if contour_color else (0, 0xFF, 0)
        self.contours = []
        if contours:
            for contour in contours:
                self.contours.append([(p[0], p[1]) for p in contour])
    #
    @property
    def scale(self):
        return self.IMG_SCALES[self.sc_slider.value()]
    @scale.setter
    def scale(self, v):
        newi = 3
        dist = 1000000.
        for i, _v in enumerate(self.IMG_SCALES):
            _dist = math.fabs(_v - v)
            if _dist < dist:
                dist = _dist
                newi = i
        self.sc_slider.setValue(newi)
        self.onScaleSlider(newi)
    #
    def scaleText(self):
        txt = f'x{self.scale}'
        if txt.endswith('.0'):
            txt = txt[:-2]
        return txt
    #
    def renderImage(self):
        sc = self.scale
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        pixmap = QtGui.QPixmap.fromImage(self.qImg)
        self.pixmap = pixmap.scaled(
            pixmap.width()*sc,
            pixmap.height()*sc,
            transformMode=QtCore.Qt.SmoothTransformation if self.interpolation else QtCore.Qt.FastTransformation
        )
        # Draw annotations
        painter = QtGui.QPainter(self.pixmap)
        # Contours
        color = QtGui.QColor.fromRgb(*self.contour_color)
        painter.setPen(QtGui.QPen(color, self.contour_width, QtCore.Qt.SolidLine))
        for contour in self.contours:
            poly = QtGui.QPolygon([QtCore.QPoint(x*sc, y*sc) for x, y in contour])
            painter.drawPolygon(poly)
        painter.end()

        self.img_lab.setPixmap(self.pixmap)
        self.img_lab.resize(self.pixmap.width(), self.pixmap.height())
        self.update()
        self.centerImage()
        QtWidgets.QApplication.restoreOverrideCursor()
    #
    def centerImage(self):
        wsz = self.scrl.widget().size()
        vsz = self.scrl.viewport().size()
        if wsz.width() >= vsz.width():
            self.scrl.horizontalScrollBar().setValue((wsz.width() - vsz.width()) // 2)
        if wsz.height() >= vsz.height():
            self.scrl.verticalScrollBar().setValue((wsz.height() - vsz.height()) // 2)
    #
    def onScaleSlider(self, v):
        self.sc_text.setText(self.scaleText())
        self.renderImage()
    def onSaveBtn(self):
        if not self.img_path:
            return
        cdir, infn = os.path.split(self.img_path)
        bn, ext = os.path.splitext(infn)
        outfn = bn + self.scaleText().replace('.', 'p') + '.png'
        
        fpath = os.path.join(cdir, outfn)
        file_dialog = QtWidgets.QFileDialog(self)
        file_dialog.setNameFilters(["PNG Images (*.png)", "All files (*.*)"])
        file_dialog.selectNameFilter('')
        file_dialog.setWindowTitle('Save Annotated Image Snapshot')
        file_dialog.setFileMode(QtWidgets.QFileDialog.AnyFile)
        file_dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        file_dialog.setWindowFilePath(fpath)
        file_dialog.setDirectory(cdir)
        file_dialog.selectFile(outfn)
        
        if not file_dialog.exec_():
            return
        pkl_filenames = file_dialog.selectedFiles()
        if len(pkl_filenames) < 1:
            return
        
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        try:
            self.pixmap.save(pkl_filenames[0], 'PNG')
        except Exception as ex:
            print(ex)
        QtWidgets.QApplication.restoreOverrideCursor()
    #  
        




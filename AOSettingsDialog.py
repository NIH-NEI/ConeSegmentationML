__all__ = ('BASE_DIR', 'ICONS_DIR', 'HELP_DIR', 'qt_icon', 'display_error', 'display_warning',
        'askYesNo', 'ao_progress_dialog', 'ao_open_dialog', 'ao_loc_dialog', 'ao_parameter_dialog',
        'ao_source_window', 'ao_brightness_contrast', )

import os
import sys
import time
import datetime
import math
import traceback

import numpy as np
from PyQt5 import QtCore, QtWidgets, QtGui

from AOMetaList import MetaRecord

if hasattr(sys, '_MEIPASS'):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ICONS_DIR = os.path.join(BASE_DIR, 'Icons')
HELP_DIR = os.path.join(BASE_DIR, 'Help')

MODEL_WEIGHTS_DIR = os.path.join(BASE_DIR, 'model_weights')

def qt_icon(name):
    return QtGui.QIcon(os.path.join(ICONS_DIR, name))

def display_error(err, ex):
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Critical)
    if isinstance(ex, Exception):
        msg.setWindowTitle('Exception')
    else:
        msg.setWindowTitle('Error')
    msg.setText(err)
    msg.setInformativeText(str(ex))
    #
    msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
    #
    geom = QtWidgets.QApplication.primaryScreen().geometry()
    spacer = QtWidgets.QSpacerItem(geom.width()*25//100, 1,
            QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
    l = msg.layout()
    l.addItem(spacer, l.rowCount(), 0, 1, l.columnCount())
    #
    msg.exec_()

def display_warning(msg, msg2):
    b = QtWidgets.QMessageBox()
    b.setIcon(QtWidgets.QMessageBox.Warning)

    b.setText(msg)
    b.setInformativeText(msg2)
    b.setWindowTitle("Warning")
    #b.setDetailedText(traceback.format_exc())
    b.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
    #
    geom = QtWidgets.QApplication.primaryScreen().geometry()
    spacer = QtWidgets.QSpacerItem(geom.width()*20//100, 1,
            QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
    l = b.layout()
    l.addItem(spacer, l.rowCount(), 0, 1, l.columnCount())
    #
    return b.exec_()

def askYesNo(title, text, detail=None):
    b = QtWidgets.QMessageBox()
    b.setIcon(QtWidgets.QMessageBox.Question)
    b.setWindowTitle(title)
    b.setText(text)
    if detail:
         b.setInformativeText(detail)
    #
    b.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
    b.setDefaultButton(QtWidgets.QMessageBox.Yes)
    #
    geom = QtWidgets.QApplication.primaryScreen().geometry()
    spacer = QtWidgets.QSpacerItem(geom.width()*20//100, 1,
            QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
    l = b.layout()
    l.addItem(spacer, l.rowCount(), 0, 1, l.columnCount())
    #
    return b.exec_() == QtWidgets.QMessageBox.Yes
#

class ao_progress_dialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(ao_progress_dialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self._progressbar = None
        self._setup_layout()
        self.setWindowTitle('Show progress')

    def _setup_layout(self):
        self.setModal(True)
        hbox = QtWidgets.QHBoxLayout()
        self._progressbar = QtWidgets.QProgressBar()
        hbox.addWidget(self._progressbar)
        self.setLayout(hbox)

    def set_progress(self, val):
        self._progressbar.setValue(val)
        QtWidgets.QApplication.processEvents()
#
        
def _createSmallButton(txt, on_clicked=None):
    btn = QtWidgets.QPushButton(txt)
    btn.setStyleSheet('margin: 0; padding: 4 10 4 10;')
    if not on_clicked is None:
        btn.clicked.connect(on_clicked)
    return btn
#

class ao_open_dialog(QtWidgets.QDialog):
    def __init__(self, parent, hist):
        super(ao_open_dialog, self).__init__(parent)
        self.hist = hist
        #
        self._loadDir = QtCore.QDir.home()
        self._annDir = self._loadDir
        self.img_list = []
        self.ann_list = []
        #
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setSizeGripEnabled(True)
        self.save_geom = None
        #
        geom = QtWidgets.QApplication.primaryScreen().geometry()
        self.gw = geom.width()
        self.gh = geom.height()
        self.resize(self.gw * 64 // 100, self.gh * 50 // 100)
        #
        self._setup_layout()
    #
    def _setup_layout(self):
        self.setWindowTitle('Open Images and Annotations')
        view_layout = QtWidgets.QGridLayout()
        view_layout.setHorizontalSpacing(8)
        view_layout.setVerticalSpacing(8)
        self.setLayout(view_layout)
        #
        self.img_lab = QtWidgets.QLabel('Browse Images:')
        view_layout.addWidget(self.img_lab, 0, 0)
        self.img_dir = QtWidgets.QLineEdit('')
        self.img_dir.setReadOnly(True)
        view_layout.addWidget(self.img_dir, 0, 1)
        self.img_btn = _createSmallButton('...',
                on_clicked=self._on_img_btn)
        self.img_btn.setToolTip('Open File Dialog to select source images')
        view_layout.addWidget(self.img_btn, 0, 2)
        #
        self.ann_lab = QtWidgets.QLabel('Annotations Directory:')
        view_layout.addWidget(self.ann_lab, 1, 0)
        self.ann_dir = QtWidgets.QLineEdit('')
        self.ann_dir.setReadOnly(True)
        view_layout.addWidget(self.ann_dir, 1, 1)
        self.ann_btn = _createSmallButton('...',
                on_clicked=self._on_ann_btn)
        self.ann_btn.setToolTip('Open File Dialog to select different directory containing annotations')
        view_layout.addWidget(self.ann_btn, 1, 2)
        #
        self.no_ann_cb = QtWidgets.QCheckBox('Images Only (no Annotations)',
                stateChanged=self.onNoAnnCb)
        view_layout.addWidget(self.no_ann_cb, 2, 1)
        #
        self.imageTable = QtWidgets.QTableWidget(0, 3)
        self.imageTable.setColumnWidth(0, 8)
        self.imageTable.setColumnWidth(1, self.gw * 30 // 100)
        self.imageTable.setHorizontalHeaderLabels([u'\u221A', u'Image File', u'Annotations File']);
        self.imageTable.horizontalHeader().setStretchLastSection(True)
        self.imageTable.verticalHeader().setVisible(False)
        self.imageTable.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers);
        self.imageTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows);
        self.imageTable.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection);
        self.imageTable.setShowGrid(False);
        self.imageTable.horizontalHeader().sectionClicked.connect(self.OnHeaderClicked)

        view_layout.addWidget(self.imageTable, 3, 0, 1, 3)

        #
        self.buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok |
                                          QtWidgets.QDialogButtonBox.Cancel)
        okBtn = self.buttonbox.button(QtWidgets.QDialogButtonBox.Ok)
        okBtn.setText('  Open Checked  ')
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)
        #
        view_layout.addWidget(self.buttonbox, 4, 0, 1, 3)
    #
    def hideEvent(self, e):
        self.save_geom = self.geometry()
        QtWidgets.QDialog.hideEvent(self, e)
    def showEvent(self, e):
        QtWidgets.QDialog.showEvent(self, e)
        if not self.save_geom is None:
            self.setGeometry(self.save_geom)
    #
    def onNoAnnCb(self, st):
        if st:
            for row in range(self.imageTable.rowCount()):
                self.imageTable.item(row, 2).setText('')
            self.ann_dir.setEnabled(False)
            self.ann_btn.setEnabled(False)
        else:
            for row, anm in enumerate(self.ann_list):
                self.imageTable.item(row, 2).setText(anm)
            self.ann_dir.setEnabled(True)
            self.ann_btn.setEnabled(True)
    #
    def OnHeaderClicked(self, col):
        if col != 0: return
        ck = True
        for row in range(self.imageTable.rowCount()):
            if self.imageTable.cellWidget(row, 0).isChecked():
                ck = False
                break
        for row in range(self.imageTable.rowCount()):
            self.imageTable.cellWidget(row, 0).setChecked(ck)
    #
    @property
    def annDir(self):
        try:
            adir = self._annDir.canonicalPath()
        except Exception:
            adir = QtCore.QDir.homePath()
        return adir
    @annDir.setter
    def annDir(self, dir_name):
        try:
            self._annDir = QtCore.QDir(dir_name)
        except Exception:
            self._annDir = QtCore.QDir.home()
        no_ann = self.isNoAnnotations()
        adir = self._annDir.canonicalPath()
        self.ann_dir.setText(adir)
        for row, fn in enumerate(self.img_list):
            nm, ext = os.path.splitext(fn)
            anm = nm + self.hist.suffix
            apath = os.path.join(adir, anm)
            if os.path.isfile(apath):
                self.ann_list[row] = anm
            else:
                self.ann_list[row] = anm = ''
            if no_ann:
                anm = ''
            self.imageTable.item(row, 2).setText(anm)
    #
    @property
    def loadDir(self):
        try:
            idir = self._loadDir.canonicalPath()
        except Exception:
            idir = QtCore.QDir.homePath()
        return idir
    @loadDir.setter
    def loadDir(self, dir_name):
        try:
            self._loadDir = QtCore.QDir(dir_name)
        except Exception:
            self._loadDir = QtCore.QDir.home()
        ldir = self._loadDir.canonicalPath()
        self.img_dir.setText(ldir)
        return
    #
    def setImageList(self, img_filenames):
        img_dir = None
        self.img_list = []
        self.ann_list = []
        for fpath in img_filenames:
            if not os.path.isfile(fpath): continue
            fdir, fn = os.path.split(fpath)
            if img_dir is None:
                img_dir = os.path.abspath(fdir)
            self.img_list.append(fn)
            self.ann_list.append('')
        self.img_list.sort()
        self.imageTable.setRowCount(len(self.img_list))
        for row, nm in enumerate(self.img_list):
            cb = QtWidgets.QCheckBox()
            cb.setChecked(True)
            cb.setContentsMargins(8, 2, 2, 0)
            self.imageTable.setCellWidget(row, 0, cb)
            self.imageTable.setItem(row, 1, QtWidgets.QTableWidgetItem(self.img_list[row]))
            self.imageTable.setItem(row, 2, QtWidgets.QTableWidgetItem(''))
        if img_dir:
            self.loadDir = img_dir
        return self.loadDir
    #
    def selectImageFiles(self):
        file_dialog = QtWidgets.QFileDialog(self)
        file_dialog.setNameFilters(["TIFF Images (*.tif *.tiff)", "All files (*.*)"])
        file_dialog.selectNameFilter('')
        file_dialog.setWindowTitle('Browse Source Images')
        file_dialog.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
        file_dialog.setLabelText(QtWidgets.QFileDialog.Accept, 'Select')
        file_dialog.setWindowFilePath(QtCore.QDir.homePath())
        file_dialog.setDirectory(self.loadDir)
        rc = file_dialog.exec_()
        if not rc:
            return False

        img_filenames = file_dialog.selectedFiles()
        if not img_filenames:
            return False
        self.annDir = self.setImageList(img_filenames)
        return True
    #
    def _on_img_btn(self, e):
        self.selectImageFiles()
    def _on_ann_btn(self, e):
        dir_name = QtWidgets.QFileDialog.getExistingDirectory(self, \
                'Select Annotations Directory', self.loadDir)
        if not dir_name:
            return
        self.annDir = dir_name
    #
    def setCheckedImages(self, img_list):
        img_set = set([os.path.basename(fpath) for fpath in img_list])
        n_checked = 0
        for row, fn in enumerate(self.img_list):
            if fn in img_set:
                self.imageTable.cellWidget(row, 0).setChecked(True)
                n_checked += 1
            else:
                self.imageTable.cellWidget(row, 0).setChecked(False)
        if n_checked == 0:
            for row in range(self.imageTable.rowCount()):
                self.imageTable.cellWidget(row, 0).setChecked(True)
    #
    def getImageList(self):
        ldir = self.loadDir
        lst = []
        for row, fn in enumerate(self.img_list):
            if self.imageTable.cellWidget(row, 0).isChecked():
                lst.append(os.path.join(ldir, fn))
        return lst
    def getAnnotationsList(self):
        lst = []
        if self.isNoAnnotations():
            return lst
        adir = self.annDir
        for row, fn in enumerate(self.ann_list):
            if not self.imageTable.cellWidget(row, 0).isChecked():
                continue
            if fn:
                fn = os.path.join(adir, fn)
                if not os.path.isfile(fn):
                    fn = None
            else:
                fn = None
            lst.append(fn)
        return lst
    def isNoAnnotations(self):
        return self.no_ann_cb.isChecked()
    #

class ao_loc_dialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(ao_loc_dialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setSizeGripEnabled(True)
        self.save_geom = None
        #
        self._setup_layout()
    #
    def _setup_layout(self):
        self.setWindowTitle('Image Data Locations')
        view_layout = QtWidgets.QGridLayout()
        self.setLayout(view_layout)
        #
        self.img_lab = QtWidgets.QLabel('Image File:')
        view_layout.addWidget(self.img_lab, 0, 0)
        self.img_txt = QtWidgets.QLineEdit('')
        self.img_txt.setReadOnly(True)
        view_layout.addWidget(self.img_txt, 1, 0)

        local_lab = QtWidgets.QLabel('Contours File (grayed if does not exist):')
        view_layout.addWidget(local_lab, 2, 0)
        self.local_txt = QtWidgets.QLineEdit('')
        self.local_txt.setReadOnly(True)
        view_layout.addWidget(self.local_txt, 3, 0)
        
        hist_lab = QtWidgets.QLabel('Auto-backup (History) File:')
        view_layout.addWidget(hist_lab, 4, 0)
        self.hist_txt = QtWidgets.QLineEdit('')
        self.hist_txt.setReadOnly(True)
        view_layout.addWidget(self.hist_txt, 5, 0)
        
        self.buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        self.buttonbox.accepted.connect(self.accept)
        
        view_layout.addWidget(self.buttonbox, 6, 0)
    #
    def hideEvent(self, e):
        self.save_geom = self.geometry()
        QtWidgets.QDialog.hideEvent(self, e)
    def showEvent(self, e):
        QtWidgets.QDialog.showEvent(self, e)
        if not self.save_geom is None:
            self.setGeometry(self.save_geom)
    #
    def setPaths(self, img, img_path, loc_path, hist_path):
        try:
            _ts = datetime.datetime.fromtimestamp(os.stat(img_path).st_mtime_ns * 0.000000001)
            ts = _ts.strftime('%m/%d/%Y %H:%M:%S.%f')[:-3]
        except Exception:
            ts = '--'
        img_info = 'Image File [%dx%d pix, last modified %s]:' % (img.GetWidth(), img.GetHeight(), ts)
        self.img_lab.setText(img_info)
        self.img_txt.setText(img_path)
        self.local_txt.setText(loc_path)
        pal = QtGui.QPalette()
        if not os.path.isfile(loc_path):
            pal.setColor(QtGui.QPalette.Text, QtGui.QColor(0xC0, 0xC0, 0xC0))
        self.local_txt.setPalette(pal)
        self.hist_txt.setText(hist_path)
    #
    
class TipLabel(QtWidgets.QLabel):
    def __init__(self, pixmap, msg):
        super(TipLabel, self).__init__()
        self.msg = msg
        #
        self.setPixmap(pixmap)
        self.setToolTip(msg)
    #
    def mousePressEvent(self, e):
        QtWidgets.QToolTip.showText(e.globalPos(), self.msg)

class ao_parameter_dialog(QtWidgets.QDialog):
    TIP_ITERATIONS = u'''Level-set iterations: the default number is 200, which works for most cases.
If the image quality is poor and over-segmentation is observed, please reduce this number.
Otherwise, increase the value.'''
    TIP_CONTOUR_LENGTH = u'''Contour length: the shortest length of cell contours.
If a cell contour length is less than this value, then the result is discarded.'''
    TIP_FIELD_OF_VIEW = u"""Field of view: Field of view that the image was acquired with (typically 0.5 to 3.0 deg.)
For example, a 1.0 means that an image was acquired with a 1.0 deg. field of view with 750x605 pixels.
This parameter should be scaled if the pixel sampling differs."""
    TIP_MODEL_WEIGHTS = u'''Machine Learning Model Weights: the default is "Built-in pre-trained", which points to pre-trained
model weights supplied with the distribution.
If you have custom trained models, make sure they are stored in files ending with '_centroids.h5',
'_contours.h5' and '_regions.h5', place them in the same directory, switch to "Custom" and
select one of these files when prompted.'''
    #
    def __init__(self, parent=None):
        super(ao_parameter_dialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setSizeGripEnabled(True)
        self.save_geom = None
        #
        geom = QtWidgets.QApplication.primaryScreen().geometry()
        self.resize(geom.width()*36/100, geom.height()*60/100)
        #
        self._extended = True
        self._mute = False
        #
        self.normal = QtGui.QFont(self.font())
        self.bold = QtGui.QFont(self.normal)
        self.bold.setBold(True)
        #
        self._setup_layout()
        #
    #
    def hideEvent(self, e):
        self.save_geom = self.geometry()
        QtWidgets.QDialog.hideEvent(self, e)
    def showEvent(self, e):
        QtWidgets.QDialog.showEvent(self, e)
        if not self.save_geom is None:
            self.setGeometry(self.save_geom)
    #
    @staticmethod
    def _create_spin_box(v, r=(1, 10000), s=1):
        res = QtWidgets.QSpinBox()
        res.setRange(*r)
        res.setSingleStep(s)
        res.setValue(v)
        return res
    #
    def _setup_layout(self):
        self.setWindowTitle('Cone segmentation')
        
        qmark = QtGui.QPixmap(os.path.join(ICONS_DIR, 'help_small.png'));
        
        ml_panel = QtWidgets.QGroupBox('Machine Learning Model Weights')
        ml_layout = QtWidgets.QGridLayout()
        ml_panel.setLayout(ml_layout)

        self.rb_builtin = QtWidgets.QRadioButton('Built-in pre-trained')
        ml_layout.addWidget(self.rb_builtin, 0, 0)
        
        self.cb_builtin = QtWidgets.QComboBox()
        ml_layout.addWidget(self.cb_builtin, 0, 1)
        
        ml_q = TipLabel(qmark, self.TIP_MODEL_WEIGHTS)
        ml_layout.addWidget(ml_q, 0, 2)
        self.rb_custom = QtWidgets.QRadioButton('Custom')
        ml_layout.addWidget(self.rb_custom, 1, 0)
        self.txCustomDir = QtWidgets.QLineEdit()
        self.txCustomDir.setReadOnly(True)
        ml_layout.addWidget(self.txCustomDir, 1, 1)
        self.btnBrowse = QtWidgets.QPushButton('Browse')
        ml_layout.addWidget(self.btnBrowse, 1, 2)
        self.rb_builtin.setChecked(True)
        
        lb_ml_cur = QtWidgets.QLabel('Currently loaded:')
        lb_ml_cur.setAlignment(QtCore.Qt.AlignTop)
        ml_layout.addWidget(lb_ml_cur, 2, 0)
        self.lb_ml = QtWidgets.QLabel('\n\n')
        self.lb_ml.setStyleSheet('QLabel {color: #333366}')
        ml_layout.addWidget(self.lb_ml, 2, 1, 1, 2)

        # Mainstream version controls
        iteration_label_n = QtWidgets.QLabel('Level-set iterations:')
        iteration_label_n.setToolTip(self.TIP_ITERATIONS)
        self._iteration_input_n = self._create_spin_box(200, r=(1, 10000), s=1)
        iteration_q_n = TipLabel(qmark, self.TIP_ITERATIONS)
        self.visible_n = [iteration_label_n, self._iteration_input_n, iteration_q_n]
        
        # Extended/Advanced version controls
        iter_panel = QtWidgets.QGroupBox('Level-set iterations')
        iter_layout = QtWidgets.QGridLayout()
        iter_panel.setLayout(iter_layout)
        self.rb_single = QtWidgets.QRadioButton('Single value')
        self.rb_single.setStyleSheet('QRadioButton {margin-right: 48;}')
        iter_layout.addWidget(self.rb_single, 0, 0)
        self.rb_range = QtWidgets.QRadioButton('Value range')
        iter_layout.addWidget(self.rb_range, 1, 0)
        self.rb_single.setChecked(True)
        
        self._iteration_input_x = self._create_spin_box(200, r=(1, 10000), s=1)
        iter_layout.addWidget(self._iteration_input_x, 0, 1, 1, 2)
        
        start_lb = QtWidgets.QLabel(' Start:')
        start_lb.setAlignment(QtCore.Qt.AlignRight)
        self._start_input = self._create_spin_box(50, r=(1, 10000), s=1)
        end_lb = QtWidgets.QLabel(' End:')
        self._end_input = self._create_spin_box(300, r=(1, 10000), s=1)
        step_lb = QtWidgets.QLabel(' Step:')
        self._step_input = self._create_spin_box(50, r=(5, 100), s=5)
        
        iter_layout.addWidget(start_lb, 1, 1)
        iter_layout.addWidget(self._start_input, 1, 2)
        iter_layout.addWidget(end_lb, 1, 3)
        iter_layout.addWidget(self._end_input, 1, 4)
        iter_layout.addWidget(step_lb, 1, 5)
        iter_layout.addWidget(self._step_input, 1, 6)

        iteration_q = TipLabel(qmark, self.TIP_ITERATIONS)
        iter_layout.addWidget(iteration_q, 0, 3)
        self.visible_x = [iter_panel,]

        cell_contour_length_label = QtWidgets.QLabel('Cell contour length:')
        cell_contour_length_label.setToolTip(self.TIP_CONTOUR_LENGTH)
        self._cell_contour_length_input = QtWidgets.QSpinBox()
        self._cell_contour_length_input.setRange(1, 1000)
        self._cell_contour_length_input.setSingleStep(1)
        self._cell_contour_length_input.setValue(20)
        #self._cell_contour_length_input.setToolTip(self.TIP_CONTOUR_LENGTH)
        
        cell_contour_length_q = TipLabel(qmark, self.TIP_CONTOUR_LENGTH)

        fov_label = QtWidgets.QLabel('Field of view:')
        fov_label.setToolTip(self.TIP_FIELD_OF_VIEW)
        self._fov_input = QtWidgets.QLineEdit('0.75')
        self._fov_input.setValidator(QtGui.QDoubleValidator(0.0, 10.0, 3))
        #self._fov_input.setToolTip(self.TIP_FIELD_OF_VIEW)
        
        fov_q = TipLabel(qmark, self.TIP_FIELD_OF_VIEW)

        self.buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok |
                                          QtWidgets.QDialogButtonBox.Cancel)
        okBtn = self.buttonbox.button(QtWidgets.QDialogButtonBox.Ok)
        okBtn.setText('  Segment Checked  ')
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)

        self.imageTable = QtWidgets.QTableWidget(0, 2)
        self.imageTable.setColumnWidth(0, 8)
        self.imageTable.setHorizontalHeaderLabels([u'\u221A', u'Image File Name']);
        self.imageTable.horizontalHeader().setStretchLastSection(True)
        self.imageTable.verticalHeader().setVisible(False)
        self.imageTable.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers);
        self.imageTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows);
        self.imageTable.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection);
        self.imageTable.setShowGrid(False);
        self.imageTable.horizontalHeader().sectionClicked.connect(self.OnHeaderClicked)

        view_layout = QtWidgets.QGridLayout()
        view_layout.setHorizontalSpacing(12)
        view_layout.setVerticalSpacing(8)
        view_layout.setColumnStretch(0, 1)
        view_layout.setColumnStretch(1, 0)
        view_layout.setColumnStretch(2, 0)
        view_layout.setColumnStretch(3, 10)
        view_layout.addWidget(self.imageTable, 0, 0, 1, 4)
        
        view_layout.addWidget(ml_panel, 1, 0, 1, 4)
        
        view_layout.addWidget(iteration_label_n, 2, 0)
        view_layout.addWidget(self._iteration_input_n, 2, 1)
        view_layout.addWidget(iteration_q_n, 2, 2)
        
        view_layout.addWidget(iter_panel, 3, 0, 1, 4)
        
        tip_label = QtWidgets.QLabel('Press on (?) and hold the mouse\nto read a brief description.')
        tip_label.setAlignment(QtCore.Qt.AlignTop)
        tip_label.setStyleSheet('QLabel {color: gray; margin: 2, 12, 2, 12;}')
        view_layout.addWidget(tip_label, 4, 3, 2, 1)
        
        view_layout.addWidget(cell_contour_length_label, 4, 0)
        view_layout.addWidget(self._cell_contour_length_input, 4, 1)
        view_layout.addWidget(cell_contour_length_q, 4, 2)
        
        view_layout.addWidget(fov_label, 5, 0)
        view_layout.addWidget(self._fov_input, 5, 1)
        view_layout.addWidget(fov_q, 5, 2)
        
        self.defBtn = QtWidgets.QPushButton('Restore Defaults')
        view_layout.addWidget(self.defBtn, 6, 0)
        self.defBtn.clicked.connect(self.restoreDefaults)
        
        view_layout.addWidget(self.buttonbox, 7, 0, 1, 4)
        self.setLayout(view_layout)
        #
        self.update_builtin_weights()
        #
        self.btnBrowse.clicked.connect(self._on_browse_custom)
        self.rb_custom.toggled.connect(self._handle_custom_rb)
        self.rb_single.toggled.connect(self._handle_iter_rb)
        self.rb_range.toggled.connect(self._handle_iter_rb)
        self.cb_builtin.currentTextChanged.connect(self._update_weights_label)
        self._handle_iter_rb(True)
        self._update_weights_label()
    #
    def restoreDefaults(self):
        self.rb_builtin.setChecked(True)
        self.rb_single.setChecked(True)
        self._iteration_input_x.setValue(200)
        self._start_input.setValue(50)
        self._end_input.setValue(300)
        self._step_input.setValue(50)
        self._iteration_input_n.setValue(200)
        self._cell_contour_length_input.setValue(20)
        self._fov_input.setText('0.75')
        self._handle_iter_rb(True)
    #
    def _handle_iter_rb(self, st):
        st = self.rb_single.isChecked()
        self._iteration_input_x.setEnabled(st)
        self._start_input.setEnabled(not st)
        self._end_input.setEnabled(not st)
        self._step_input.setEnabled(not st)
    #
    def SetImageList(self, items):
        self.imageTable.setRowCount(len(items))
        for row, nm in enumerate(items):
            cb = QtWidgets.QCheckBox()
            cb.setContentsMargins(8, 2, 2, 0)
            self.imageTable.setCellWidget(row, 0, cb)
            self.imageTable.setItem(row, 1, QtWidgets.QTableWidgetItem(items[row]))
    #
    def SetCheckedRows(self, rows):
        for row in range(self.imageTable.rowCount()):
            self.imageTable.cellWidget(row, 0).setChecked(row in rows)
    def checkedRows(self):
        return [row for row in range(self.imageTable.rowCount()) \
            if self.imageTable.cellWidget(row, 0).isChecked()]
    #
    def SetHighlightedRow(self, h_row):
        for row in range(self.imageTable.rowCount()):
            self.imageTable.item(row, 1).setFont(self.bold if row==h_row else self.normal)
        if h_row >= 0 and h_row < self.imageTable.rowCount():
            self.imageTable.selectRow(h_row)
            self.imageTable.scrollToItem(self.imageTable.item(h_row, 1))
    #
    def OnHeaderClicked(self, col):
        if col != 0: return
        ck = len(self.checkedRows()) == 0
        for row in range(self.imageTable.rowCount()):
            self.imageTable.cellWidget(row, 0).setChecked(ck)
    #
    def accept(self):
        if len(self.checkedRows()) > 0:
            QtWidgets.QDialog.accept(self)
    #
    def update_builtin_weights(self):
        save_name = self.builtin_directory
        self._update_builtin_weights()
        if save_name:
            self.builtin_directory = save_name
    #
    def _update_builtin_weights(self):
        cdir = MODEL_WEIGHTS_DIR
        self.cb_builtin.clear()
        for mdir in os.listdir(cdir):
            fpath = os.path.join(cdir, mdir)
            if not os.path.isdir(fpath): continue
            if not self.scan_model_dir(fpath) is None:
                self.cb_builtin.addItem(mdir)
    #
    def _update_weights_label(self):
        res = self.model_weights
        if res:
            txt = '\n'.join([os.path.basename(x) for x in sorted(res.values())])
        else:
            txt = ' '
        self.lb_ml.setText(txt)
    #
    def _handle_custom_rb(self, st):
        if self._mute: return
        if self.custom:
            mw = self.scan_model_dir(self.custom_directory)
            if not mw:
                self._browse_custom()
        self._update_weights_label()
    #
    @staticmethod
    def scan_model_dir(mdir):
        if not mdir:
            return None
        mdir = os.path.abspath(mdir)
        res = {}
        for fn in os.listdir(mdir):
            fpath = os.path.join(mdir, fn)
            if not os.path.isfile(fpath): continue
            bn, ext = os.path.splitext(fn.lower())
            if ext != '.h5': continue
            parts = bn.split('_')
            for key in ('contours', 'regions', 'centroids'):
                if key in parts:
                    res[key] = fpath
                    break
        return res if len(res) == 3 else None
    #
    def _on_browse_custom(self):
        self._mute = True
        self.custom = True
        self._mute = False
        self._browse_custom()
    #
    def _validate_custom(self):
        if self.custom and not self.custom_directory:
            self._mute = True
            self.custom = False
            self._mute = False
        self._update_weights_label()
    #
    def _browse_custom(self):
        cdir = self.custom_directory if self.custom_directory else QtCore.QDir.home()
        file_dialog = QtWidgets.QFileDialog(self)
        file_dialog.setNameFilters(["Trained ML model weights (*contours.h5 *regions.h5 *centroids.h5)"])
        file_dialog.selectNameFilter('')
        file_dialog.setWindowTitle('Browse Trained ML Model Weights')
        file_dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        file_dialog.setLabelText(QtWidgets.QFileDialog.Accept, 'Select')
        file_dialog.setDirectory(cdir)
        rc = file_dialog.exec_()
        if not rc:
            self._validate_custom()
            return
        flist = file_dialog.selectedFiles()
        if len(flist) < 1:
            self._validate_custom()
            return
        mdir = os.path.dirname(flist[0])
        if not self.scan_model_dir(mdir) is None:
            self.custom_directory = mdir
        elif self.custom:
            #QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
            display_error('Missing Model Weights',
                "Please place '<>_centroids.h5', '<>_contours.h5' and '<>_regions.h5' "+
                "in a directory, then select one of these files.")
            self._validate_custom()
    #
    @property
    def custom(self):
        return self.rb_custom.isChecked()
    @custom.setter
    def custom(self, st):
        self.rb_builtin.setChecked(not st)
        self.rb_custom.setChecked(st)
    #
    @property
    def builtin_directory(self):
        return self.cb_builtin.currentText()
    @builtin_directory.setter
    def builtin_directory(self, v):
        fpath = os.path.join(MODEL_WEIGHTS_DIR, v)
        if not self.scan_model_dir(fpath) is None:
            self.cb_builtin.setCurrentText(v)
    #
    @property
    def custom_directory(self):
        return self.txCustomDir.text()
    @custom_directory.setter
    def custom_directory(self, v):
        self.txCustomDir.setText(v)
        self.txCustomDir.setToolTip(v)
    #
    def default_model_weights(self):
        cdir = MODEL_WEIGHTS_DIR
        wmap = {}
        mw = self.scan_model_dir(cdir)
        if mw:
            wmap['.'] = mw
        for fn in os.listdir(cdir):
            dpath = os.path.join(cdir, fn)
            if not os.path.isdir(dpath): continue
            mw = self.scan_model_dir(dpath)
            if mw:
                wmap[fn] = mw
        if self.builtin_directory in wmap:
            return wmap[self.builtin_directory]
        for k, v in wmap.items():
            return v
        return None
    #
    @property
    def model_weights(self):
        if self.custom:
            return self.scan_model_dir(self.custom_directory)
        return self.default_model_weights()
    #
    @property
    def extended(self):
        return self._extended
    @extended.setter
    def extended(self, st):
        for o in self.visible_n:
            o.setVisible(not st)
        for o in self.visible_x:
            o.setVisible(st)
        if self._extended != st:
            self.iteration_number = self.iteration_number
        self._extended = st
    #
    @property
    def iteration_single(self):
        return self.rb_single.isChecked()
    @iteration_single.setter
    def iteration_single(self, st):
        if st:
            self.rb_single.setChecked(True)
        else:
            self.rb_range.setChecked(True)
    #
    @property
    def iteration_range(self):
        return (self._start_input.value(), self._end_input.value(), self._step_input.value(),)
    @iteration_range.setter
    def iteration_range(self, v):
        try:
            self._start_input.setValue(int(v[0]))
            self._end_input.setValue(int(v[1]))
            self._step_input.setValue(int(v[2]))
        except Exception:
            self._start_input.setValue(100)
            self._end_input.setValue(300)
            self._step_input.setValue(20)
    #
    @property
    def iteration_number(self):
        if self.extended:
            return self._iteration_input_x.value()
        return self._iteration_input_n.value()
    @iteration_number.setter
    def iteration_number(self, v):
        v = int(v)
        self._iteration_input_n.setValue(v)
        self._iteration_input_x.setValue(v)
    #
    @property
    def contour_length(self):
        return self._cell_contour_length_input.value()
    @contour_length.setter
    def contour_length(self, v):
         v = int(v)
         self._cell_contour_length_input.setValue(v)
    #
    @property
    def image_fov(self):
        return float(self._fov_input.text())
    @image_fov.setter
    def image_fov(self, v):
        v = float(v)
        self._fov_input.setText(str(v))
    #
    @property
    def levelset_iterations(self):
        if not self.extended or self.iteration_single:
            return self.iteration_number
        return self.iteration_range
    #
    STATE_ATTRIBUTES = ('custom', 'custom_directory', 'builtin_directory',
            'iteration_number', 'contour_length', 'image_fov', 'iteration_single', 'iteration_range',)
    @property
    def state(self):
        return dict([(a, getattr(self,a)) for a in self.STATE_ATTRIBUTES])
    @state.setter
    def state(self, jobj):
        self._mute = True
        for a in self.STATE_ATTRIBUTES:
            if a in jobj:
                setattr(self, a, jobj[a])
        if self.custom and self.model_weights is None:
            self.custom = False
        self._mute = False
#

class _crossLabel(QtWidgets.QLabel):
    def __init__(self, callback=None):
        super(_crossLabel, self).__init__()
        self.callback = callback
        #
        self.margin = 10
        #
        self.setStyleSheet(f'margin: {self.margin} {self.margin} {self.margin} {self.margin};')
        self.setMouseTracking(True)
        #
        self.rangeX = (0, 1000)
        self.rangeY = (0, 1000)
        self.posX = 0
        self.posY = 0
        #
        img_data = np.empty(shape=(256, 256), dtype=np.float32)
        for c in range(256):
            img_data[0][c] = c
        row0 = img_data[0]
        for j in range(1,256):
            img_data[j] = row0 * ((255. - j * 0.85) / 255.) + (127.5 * j * 0.85 / 255.)
        img_data = np.transpose(img_data, (1,0)).copy()
        img = QtGui.QImage(img_data.astype(np.uint8), 256, 256, 256, QtGui.QImage.Format_Grayscale8)
        self.pixmap0 = QtGui.QPixmap.fromImage(img)
        self._updateScaledPixmap()
        #
    def _updateScaledPixmap(self):
        self.scpixmap = self.pixmap0.scaled(self.width()-self.margin*2, self.height()-self.margin*2, transformMode=QtCore.Qt.FastTransformation)
        self.setPixmap(self.scpixmap)
        #self.update()
    def resizeEvent(self, e):
        self._updateScaledPixmap()
    #
    def _handle_mouse_pos(self, e):
        pt = e.pos()
        x0 = self.margin
        x1 = self.width() - self.margin
        w = x1 - x0
        y0 = self.margin
        y1 = self.height() - self.margin
        h = y1 - y0
        x = (pt.x() - x0) * (self.rangeX[1] - self.rangeX[0]) / w + self.rangeX[0]
        y = (h - pt.y() + y0) * (self.rangeY[1] - self.rangeY[0]) / h + self.rangeY[0]
        if x>=self.rangeX[0] and x<=self.rangeX[1] and y>=self.rangeY[0] and y<=self.rangeY[1]:
            if self.callback:
                self.callback(int(x+0.5), int(y+0.5))
    #
    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self._handle_mouse_pos(e)
    def mouseMoveEvent(self, e):
        if e.buttons() == QtCore.Qt.LeftButton:
            self._handle_mouse_pos(e)
    #
    def paintEvent(self, e):
        super(_crossLabel, self).paintEvent(e)
        qp = QtGui.QPainter()
        qp.begin(self)
        pen = QtGui.QPen(QtCore.Qt.yellow, 2, QtCore.Qt.CustomDashLine)
        pen.setDashPattern([2, 4])
        qp.setPen(pen)
        #
        x0 = self.margin
        x1 = self.width() - self.margin
        w = x1 - x0
        y0 = self.margin
        y1 = self.height() - self.margin
        h = y1 - y0
        x = (self.posX - self.rangeX[0]) * w / (self.rangeX[1] - self.rangeX[0]) + x0
        qp.drawLine(x, y0, x, y1)
        y = h - (self.posY - self.rangeY[0]) * h / (self.rangeY[1] - self.rangeY[0]) + y0
        qp.drawLine(x0, y, x1, y)
        #
        qp.end()
    #

class ao_brightness_contrast(QtWidgets.QWidget):
    def __init__(self, mainwin, parent=None, callback=None):
        super(ao_brightness_contrast, self).__init__(parent)
        self.mainwin = mainwin
        self.callback = callback
        #
        self.manual = True
        #
        flags = self.windowFlags() | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAutoFillBackground(True)
        self.setBackgroundRole(QtGui.QPalette.Shadow)
        #
        geom = QtWidgets.QApplication.primaryScreen().geometry()
        wsz = geom.height() * 20 // 100
        self.resize(wsz, wsz)
        self.move(30, 30)
        #
        view_layout = QtWidgets.QGridLayout()
        view_layout.setHorizontalSpacing(2)
        view_layout.setVerticalSpacing(2)
        self.setLayout(view_layout)
        #
        for idx, stretch in enumerate((0., 1., 0.)):
            view_layout.setColumnStretch(idx, stretch)
            view_layout.setRowStretch(idx, stretch)
        #
        b_lab = QtWidgets.QLabel('\u263C')
        b_lab.setFont(QtGui.QFont('Arial', 10))
        view_layout.addWidget(b_lab, 0, 0)
        c_lab = QtWidgets.QLabel(' \u25D1')
        c_lab.setFont(QtGui.QFont('Arial', 16))
        view_layout.addWidget(c_lab, 2, 2)
        #
        self.c_sl = sl = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        sl.setRange(0,1000)
        sl.setTickInterval(100)
        sl.setTickPosition(QtWidgets.QSlider.TicksAbove)
        view_layout.addWidget(sl, 2, 1)
        self.b_sl = sl = QtWidgets.QSlider(QtCore.Qt.Vertical)
        sl.setRange(0,1000)
        sl.setTickInterval(100)
        sl.setTickPosition(QtWidgets.QSlider.TicksRight)
        view_layout.addWidget(sl, 1, 0)
        self.crosslabel = _crossLabel(callback=self.onCrossLabel)
        view_layout.addWidget(self.crosslabel, 1, 1)
        self.rbtn = QtWidgets.QPushButton('\u2A01')
        self.rbtn.setStyleSheet('margin: 0; padding: 1 4 1 4;')
        self.rbtn.setBackgroundRole(QtGui.QPalette.Dark)
        view_layout.addWidget(self.rbtn, 2, 0)
        #
        self.c_sl.valueChanged.connect(self.onColorWindowSlider)
        self.b_sl.valueChanged.connect(self.onColorLevelSlider)
        self.rbtn.clicked.connect(lambda: self.onCrossLabel(500,500))
        #
        self._mute = False
    #
    def onColorWindowSlider(self, v):
        self.crosslabel.posX = v
        self.crosslabel.update()
        if not self._mute and self.callback:
            self.callback(self.color_info)
    def onColorLevelSlider(self, v):
        self.crosslabel.posY = v
        self.crosslabel.update()
        if not self._mute and self.callback:
            self.callback(self.color_info)
    #
    def onCrossLabel(self, x, y):
        mute = self._mute
        self._mute = True
        self.b_sl.setValue(y)
        self.c_sl.setValue(x)
        self._mute = mute
        if not self._mute and self.callback:
            self.callback(self.color_info)
    #
    @property
    def color_info(self):
        y = self.b_sl.value()
        clvl = y * 767. / 1000. - 256. if y != 500 else 127.5
        x = self.c_sl.value()
        cwin = math.pow(x/125.1347,4.) + 0.1 if x != 500 else 255.
        return (clvl, cwin)
    @color_info.setter
    def color_info(self, v):
        try:
            clvl, cwin = v
            y = (clvl + 256.) * 1000. / 767.
            if y<0: y=0
            elif y>1000: y=1000
            if cwin <= 0.1: x=0
            else:
                x = math.pow((cwin-0.1), 0.25)*125.1347
                if x>1000: x=1000
            x = int(x)
            y = int(y)
        except Exception as ex:
            print(ex)
            x = y = 500
        self._mute = True
        self.onCrossLabel(x, y)
        self._mute = False
    #


class ao_source_window(QtWidgets.QWidget):
    def __init__(self, mainwin):
        super(ao_source_window, self).__init__(None)
        self.mainwin = mainwin
        #
        self.cmeta = MetaRecord(when=MetaRecord.TODAY, user=MetaRecord.CURRENT_USER)
        if self.mainwin:
            self.cmeta.realWho = self.mainwin.getRealName(self.cmeta.user)
        #
        flags = self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint
        #flags |= QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        #
        geom = QtWidgets.QApplication.primaryScreen().geometry()
        self.gw = geom.width()
        self.gh = geom.height()
        self.resize(self.gw * 60 // 100, self.gh * 32 // 100)
        #
        self._contours = None
        self._mute = False
        #
        self._setup_layout()
    #
    def _setup_layout(self):
        self.setWindowTitle('Annotation Sources')
        view_layout = QtWidgets.QGridLayout()
        view_layout.setHorizontalSpacing(8)
        view_layout.setVerticalSpacing(8)
        self.setLayout(view_layout)
        #
        name_layout = QtWidgets.QGridLayout()
        name_layout.setColumnStretch(0, 0)
        name_layout.setColumnStretch(1, 1)
        view_layout.addLayout(name_layout, 0, 0)
        nameLabel = QtWidgets.QLabel('Real User Name:')
        name_layout.addWidget(nameLabel, 0, 0)
        self.realNameTxt = QtWidgets.QLineEdit()
        name_layout.addWidget(self.realNameTxt, 0, 1)
        #
        self.sourceTable = QtWidgets.QTableWidget(0, 6)
        self.sourceTable.setColumnWidth(0, 8)
        self.sourceTable.setColumnWidth(1, 2)
        self.sourceTable.setColumnWidth(2, self.gw * 4 // 100)
        self.sourceTable.setColumnWidth(3, self.gw * 5 // 100)
        self.sourceTable.setColumnWidth(4, self.gw * 8 // 100)
        self.sourceTable.setHorizontalHeaderLabels([u'\u221A', u'', u'Count', u'Date', u'User', u'Comment']);
        self.sourceTable.horizontalHeader().setStretchLastSection(True)
        self.sourceTable.verticalHeader().setVisible(False)
        #self.sourceTable.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers);
        self.sourceTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows);
        self.sourceTable.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection);
        self.sourceTable.setShowGrid(False);
        self.sourceTable.horizontalHeader().sectionClicked.connect(self.OnHeaderClicked)
        view_layout.addWidget(self.sourceTable, 1, 0)
        #
        btn_layout = QtWidgets.QGridLayout()
        btn_layout.setColumnStretch(0, 0)
        btn_layout.setColumnStretch(1, 0)
        btn_layout.setColumnStretch(2, 1)
        btn_layout.setColumnStretch(3, 0)
        btn_layout.setHorizontalSpacing(16)
        view_layout.addLayout(btn_layout, 2, 0)
        self.newButton = QtWidgets.QPushButton('New')
        btn_layout.addWidget(self.newButton, 0, 0)
        self.delButton = QtWidgets.QPushButton('Delete')
        btn_layout.addWidget(self.delButton, 0, 1)
        self.dfltButton = QtWidgets.QPushButton('Default')
        btn_layout.addWidget(self.dfltButton, 0, 3)
        #
        self.realNameTxt.setText(self.cmeta.realWho)
        self.realNameTxt.editingFinished.connect(self.onRealNameChanged)
        self.sourceTable.cellChanged.connect(self.onDescriptionChanged)
        self.sourceTable.currentCellChanged.connect(self.onCurrentCellChange)
        self.newButton.clicked.connect(self.onNewButton)
        self.delButton.clicked.connect(self.onDelButton)
        self.dfltButton.clicked.connect(self.onDefaultButton)
    #
    def onRealNameChanged(self):
        self.cmeta.realWho = self.realNameTxt.text()
        MetaRecord.REAL_USER = self.cmeta.realUser if 'realUser' in self.cmeta.__dict__ else None
        for meta, lst in self._contours.itermapping():
            if meta.userkey == MetaRecord.current_key():
                meta.realWho = self.cmeta.realWho
        self.setMetaList(self._contours)
        if self.mainwin:
            self.mainwin.setRealName(self.cmeta.realWho)
    #
    def onDescriptionChanged(self, row, col):
        if self._mute: return
        if col != 5: return
        try:
            comment = self.sourceTable.item(row, col).text().strip()
            mrec = self._meta_list[row][0]
            if comment:
                mrec.__dict__['comment'] = comment
            else:
                if 'comment' in mrec.__dict__:
                    del mrec.comment
            self._update_defaults()
        except Exception:
            pass
    #
    def OnHeaderClicked(self, col):
        if col != 0: return
        self._mute = True
        ck = False
        for row in range(self.sourceTable.rowCount()):
            if not self.sourceTable.cellWidget(row, 0).isChecked():
                ck = True
                break
        for row in range(self.sourceTable.rowCount()):
            self.sourceTable.cellWidget(row, 0).setChecked(ck)
        self._mute = False
        self._update_selection(False)
    #
    def _update_selection(self, st):
        if self._mute or not hasattr(self._contours, 'setGrayMeta'):
            return
        grayed = []
        for cb, (meta, cnt) in zip(self._cb_list, self._meta_list):
            if not cb.isChecked():
                grayed.append(meta)
        self._contours.setGrayMeta(grayed)
        if self.mainwin:
            self.mainwin._update_sources()
    #
    def _update_button_status(self):
        curmeta = self._current_meta()
        self.delButton.setEnabled(self._contours.meta.can_delete_meta(curmeta))
        self.dfltButton.setEnabled(self._can_be_default(curmeta))
    #
    def onCurrentCellChange(self, row, col, prow, pcol):
        if self._mute: return
        self._mute = True
        if col != 5:
            self.sourceTable.setCurrentCell(row, 5)
        meta = self._current_meta()
        if self._can_be_default(meta):
            self._contours.meta.default = meta
            if self.mainwin:
                self.mainwin._set_contours(None)
        self._mute = False
        self._update_button_status()
    #
    def setMetaList(self, contours, cur_row=-1):
        if self._mute: return
        self._mute = True
        cur_col = -1
        if contours is self._contours:
            if cur_row < 0:
                cur_row = self.sourceTable.currentRow()
            cur_col = 5
        self._contours = contours
        self._meta_list = []
        self._cb_list = []
        for attr in ('meta', 'itermapping', 'isGrayMetaRec'):
            if not hasattr(self._contours, attr):
                self.sourceTable.setRowCount(0)
                return
        #
        for meta, lst in self._contours.itermapping():
            self._meta_list.append((meta, len(lst)))
        self.sourceTable.setRowCount(len(self._meta_list))
        #
        for row, (meta, cnt) in enumerate(self._meta_list):
            cb = QtWidgets.QCheckBox()
            cb.setChecked(not contours.isGrayMetaRec(meta))
            cb.setContentsMargins(8, 2, 2, 0)
            self.sourceTable.setCellWidget(row, 0, cb)
            cb.toggled.connect(self._update_selection)
            self._cb_list.append(cb)
            item = QtWidgets.QTableWidgetItem('')
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable);
            self.sourceTable.setItem(row, 1, item)
            item = QtWidgets.QTableWidgetItem(f'{cnt}   ')
            item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter);
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable);
            self.sourceTable.setItem(row, 2, item)
            item = QtWidgets.QTableWidgetItem(meta.when)
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable);
            self.sourceTable.setItem(row, 3, item)
            item = QtWidgets.QTableWidgetItem(meta.realWho)
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable);
            self.sourceTable.setItem(row, 4, item)
            item = QtWidgets.QTableWidgetItem(meta.description)
            if meta.userkey != MetaRecord.current_key():
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable);
            else:
                hi = 0xF0 if row&1 == 0 else 0xF8
                item.setBackground(QtGui.QBrush(QtGui.QColor(hi, hi, 0xFF)))
                item.setForeground(QtGui.QBrush(QtGui.QColor(0, 0, 0x55)))
            self.sourceTable.setItem(row, 5, item)
        #
        self.sourceTable.clearSelection()
        self.sourceTable.setCurrentCell(cur_row, cur_col)
        self._update_defaults()
        self._mute = False
    #
    def onNewButton(self):
        self.sourceTable.setFocus()
        self._mute = True
        meta = MetaRecord(user=MetaRecord.CURRENT_USER)
        self._contours.meta.addmeta(meta, newid=True, setdefault=True)
        if self.mainwin:
            self.mainwin._set_contours(None)
        self._mute = False
        self.setMetaList(self._contours, cur_row=0)
    #
    def onDelButton(self):
        self.sourceTable.setFocus()
        meta = self._current_meta()
        if not self._contours.meta.can_delete_meta(meta):
            return
        self._mute = True
        self._contours.meta.delmeta(meta)
        if self.mainwin:
            self.mainwin._set_contours(None)
        self._mute = False
        self.setMetaList(self._contours, cur_row=0)
    #
    def _can_be_default(self, meta):
        if meta is None: return False
        return meta.userkey == MetaRecord.current_key()
    #
    def _update_defaults(self):
        has_default = False
        self._mute = True
        for row, (meta, cnt) in enumerate(self._meta_list):
            st = ''
            if MetaRecord.COMMENT and self._can_be_default(meta) and not 'comment' in meta.__dict__:
                self.sourceTable.item(row, 5).setText(MetaRecord.COMMENT)
                if not has_default:
                    st = '*'
                    has_default = True
            self.sourceTable.item(row, 1).setText(st)
        self._mute = False
        self._update_button_status()
    #
    def _current_meta(self):
        try:
            return self._meta_list[self.sourceTable.currentRow()][0]
        except Exception:
            return None
    #
    def onDefaultButton(self):
        self.sourceTable.setFocus()
        meta = self._current_meta()
        if not self._can_be_default(meta):
            return
        #
        if MetaRecord.COMMENT:
            for _meta, cnt in self._meta_list:
                if _meta.userkey == meta.userkey and not 'comment' in _meta.__dict__:
                    _meta.__dict__['comment'] = MetaRecord.COMMENT
        #
        row = self.sourceTable.currentRow()
        if self.sourceTable.item(row, 1).text() == '*':
            MetaRecord.COMMENT = None
        else:
            txt = self.sourceTable.item(row, 5).text().strip()
            if not txt:
                txt = None
            MetaRecord.COMMENT = txt
            if 'comment' in meta.__dict__:
                del meta.__dict__['comment']
        self._update_defaults()
    #


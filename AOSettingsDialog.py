import os
import sys
import time
import datetime
import traceback

from PyQt5 import QtCore, QtWidgets, QtGui

if hasattr(sys, '_MEIPASS'):
    icon_dir = os.path.join(sys._MEIPASS, 'Icons')
else:
    icon_dir = os.path.join(os.path.dirname(__file__), 'Icons')

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
        file_dialog.exec()

        img_filenames = file_dialog.selectedFiles()
        if not img_filenames:
            return
        self.annDir = self.setImageList(img_filenames)
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
    def __init__(self, parent=None):
        super(ao_parameter_dialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setSizeGripEnabled(True)
        self.save_geom = None
        #
        self._segmentation_weights = {}
        self._segmentation_method = '-- No method --'
        #
        self.normal = QtGui.QFont(self.font())
        self.bold = QtGui.QFont(self.normal)
        self.bold.setBold(True)
        #
        self._setup_layout()
    #
    def hideEvent(self, e):
        self.save_geom = self.geometry()
        QtWidgets.QDialog.hideEvent(self, e)
    def showEvent(self, e):
        QtWidgets.QDialog.showEvent(self, e)
        if not self.save_geom is None:
            self.setGeometry(self.save_geom)
    #
    @property
    def segmentation_method(self):
        return self._segmentation_method
    @segmentation_method.setter
    def segmentation_method(self, v):
        if not v in self._segmentation_weights:
            return
        self._segmentation_method = v
        if hasattr(self, '_segmentation_method_box'):
            self._segmentation_method_box.setText(v)
    #
    def _setup_layout(self):
        self.setWindowTitle('Cone segmentation')
        
        qmark = QtGui.QPixmap(os.path.join(icon_dir, 'help_small.png'));
        
#         segmentation_method_label = QtWidgets.QLabel('Segmentation method:')
#         #self._segmentation_method_box = QtWidgets.QComboBox()
#         #self._detection_method_box.currentIndexChanged.connect(self._select_detection_method)
#         self._segmentation_method_box = QtWidgets.QLineEdit(self._segmentation_method)
#         self._segmentation_method_box.setReadOnly(True)
#         self._segmentation_method_box.setStyleSheet(
#             "QLineEdit {background: rgb(220, 220, 220); selection-background-color: rgb(128, 160, 255);}")

        iteration_label = QtWidgets.QLabel('Level-set iterations:')
        iteration_label.setToolTip(self.TIP_ITERATIONS)
        self._iteration_input = QtWidgets.QSpinBox()
        self._iteration_input.setRange(1, 10000)
        self._iteration_input.setSingleStep(1)
        self._iteration_input.setValue(200)
        #self._iteration_input.setToolTip(self.TIP_ITERATIONS)

        iteration_q = TipLabel(qmark, self.TIP_ITERATIONS)

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
        
#         view_layout.addWidget(segmentation_method_label, 1, 0)
#         view_layout.addWidget(self._segmentation_method_box, 1, 1, 1, 3)
        
        view_layout.addWidget(iteration_label, 2, 0)
        view_layout.addWidget(self._iteration_input, 2, 1)
        view_layout.addWidget(iteration_q, 2, 2)
        
        tip_label = QtWidgets.QLabel('Press on (?) and hold the mouse\nto read a brief description.')
        tip_label.setAlignment(QtCore.Qt.AlignTop)
        tip_label.setStyleSheet('QLabel {color: gray; margin: 2, 12, 2, 12;}')
        view_layout.addWidget(tip_label, 2, 3, 3, 1)
        
        view_layout.addWidget(cell_contour_length_label, 3, 0)
        view_layout.addWidget(self._cell_contour_length_input, 3, 1)
        view_layout.addWidget(cell_contour_length_q, 3, 2)
        
        view_layout.addWidget(fov_label, 4, 0)
        view_layout.addWidget(self._fov_input, 4, 1)
        view_layout.addWidget(fov_q, 4, 2)
        
        self.defBtn = QtWidgets.QPushButton('Restore Defaults')
        view_layout.addWidget(self.defBtn, 5, 0)
        self.defBtn.clicked.connect(self.restoreDefaults)
        
        view_layout.addWidget(self.buttonbox, 6, 0, 1, 4)
        self.setLayout(view_layout)
    #
    def restoreDefaults(self):
        self._iteration_input.setValue(200)
        self._cell_contour_length_input.setValue(20)
        self._fov_input.setText('0.75')
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
    def set_segmentation_weights(self, weights):
        self._segmentation_weights = weights or {}
        if not self.segmentation_method in self._segmentation_weights:
            for method in sorted(weights.keys()):
                self.segmentation_method = method
                break
                # self._segmentation_method_box.addItem(method)

    def get_iteration_number(self):
        return self._iteration_input.value()

    def get_cell_contour_length(self):
        return self._cell_contour_length_input.value()

    def get_image_fov(self):
        return float(self._fov_input.text())
    #
    def get_state(self):
        jobj = {
            'segmentation_method': self.segmentation_method,
            'levelset_iterations': self.get_iteration_number(),
            'contour_length': self.get_cell_contour_length(),
            'image_fov': self.get_image_fov(),
        }
        return jobj
    #
    def set_state(self, jobj):
        try:
            if 'levelset_iterations' in jobj:
                self._iteration_input.setValue(int(jobj['levelset_iterations']))
            if 'contour_length' in jobj:
                self._cell_contour_length_input.setValue(int(jobj['contour_length']))
            if 'image_fov' in jobj:
                self._fov_input.setText(str(jobj['image_fov']))
            if 'segmentation_method' in jobj:
                self.segmentation_method = jobj['segmentation_method']
                # self._segmentation_method_box.setCurrentText(jobj['segmentation_method'])
        except Exception:
            pass
#




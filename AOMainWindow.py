from __future__ import division
import os, sys
import json
import vtk

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5 import Qt
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
# import matplotlib.pyplot as plt
import SimpleITK as sitk

import numpy as np
from keras.preprocessing.image import load_img
from AOUtil import *
import AOImageView
from AOImageView import MouseOp
import AOFileIO
import AOMethod
from AOMetaList import *
from AOSettingsDialog import *
from AODisplay import ao_display_settings
from AOSnap import ao_snap_dialog
from AOHotKey import ao_hotkey_dialog
import AOConfig as cfg

IMG_ICON_2D = 0
IMG_ICON_ANN = 1
IMG_ICON_3D = 2
IMG_ICON_OPEN = 4

_big_icon = QtCore.QUrl.fromLocalFile(os.path.join(ICONS_DIR, 'ConeSegmentationML256.png'))
about_html = '''
<table><tr>
<td><img src="%s">&nbsp;&nbsp;</td>
<td><b>%s %s</b><div>
<a href="https://nei.nih.gov/intramural/translational-imaging">Tam lab</a><br>
<a href="https://nei.nih.gov/">National Eye Institute</a><br>
<a href="https://www.nih.gov/">National Institutes of Health</a></div><div><br>
Cone Segmentation (Machine Learning edition)<br><br>
If any portion of this software is used, please<br>
cite the following paper in your publication:
</div></td></tr><tr><td colspan=2>
<b>Jianfei Liu, Christine Shen, Nancy Aguilera, Catherine Cukras, Robert B. Hufnagel,<br>
Wadih M. Zein, Tao Liu, and Johnny Tam.</b><br>
"Active Cell Appearance Model Induced Generative Adversarial Networks for Annotation-Efficient<br>
Cell Segmentation and Identification on Adaptive Optics Retinal Images,"<br>
<i>IEEE Transactions on Medical Imaging</i>, 2021 (DOI: 10.1109/TMI.2021.3055483)<br>
</td></tr></table>
''' % (_big_icon.url(), cfg.APP_NAME, cfg.APP_VERSION)
#
class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(AboutDialog, self).__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        #self.setSizeGripEnabled(True)
        self.setWindowIcon(qt_icon('about.png'))
        self.setWindowTitle('About '+cfg.APP_NAME)
        #
        layout = QtWidgets.QVBoxLayout()
        lbl = QtWidgets.QLabel(about_html)
        lbl.setTextFormat(QtCore.Qt.RichText)
        lbl.setOpenExternalLinks(True)
        #
        buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.close)
        #
        layout.addWidget(lbl)
        layout.addWidget(buttonbox)
        self.setLayout(layout)
#

class AODirectoryDialog(QtWidgets.QFileDialog):
    save_geom = None
    def __init__(self, ini_dir, title='Select a directory'):
        super(AODirectoryDialog, self).__init__()
        self.setFileMode(QtWidgets.QFileDialog.Directory)
        self.setOption(QtWidgets.QFileDialog.DontUseNativeDialog)
        self.setWindowTitle(title)
        self.setDirectory(ini_dir)
        #
        lay = self.layout()
        nextRow = self.layout().rowCount()
        numCols = self.layout().columnCount()
        #
        optlay = QtWidgets.QGridLayout()
        optlay.setColumnStretch(0, 0)
        optlay.setColumnStretch(1, 1)
        optlay.setHorizontalSpacing(50)
        lay.addLayout(optlay, nextRow, 0, 1, numCols)
        #
        self.cbCenters = QtWidgets.QCheckBox('Write contour centers (*_detections.csv)')
        optlay.addWidget(self.cbCenters, 0, 0)
        self.cbMeasures = QtWidgets.QCheckBox('Write contour measurements (*_measurements.csv)')
        optlay.addWidget(self.cbMeasures, 0, 1)
        #
        geom = QtWidgets.QApplication.primaryScreen().geometry()
        self.gw = geom.width()
        self.gh = geom.height()
        self.resize(self.gw * 60 // 100, self.gh * 50 // 100)
    #
    def hideEvent(self, e):
        AODirectoryDialog.save_geom = self.geometry()
        QtWidgets.QDialog.hideEvent(self, e)
    def showEvent(self, e):
        QtWidgets.QDialog.showEvent(self, e)
        if not AODirectoryDialog.save_geom is None:
            self.setGeometry(AODirectoryDialog.save_geom)
    #
    @property
    def xoptions(self):
        return {
            'detections': self.cbCenters.isChecked(),
            'measurements': self.cbMeasures.isChecked(),
        }
    #
    @xoptions.setter
    def xoptions(self, v):
        try:
            self.cbCenters.setChecked(v['detections'])
            self.cbMeasures.setChecked(v['measurements'])
        except Exception:
            pass
    #
    def run(self):
        try:
            if self.exec_():
                return self.selectedFiles()[0]
        except Exception:
            pass
        return None
#

class InputImageData(object):
    def __init__(self, img_fpath, itk_img):
        self.itk_img = itk_img
        self.filepath = img_fpath
        self._name = os.path.splitext(os.path.basename(self.filepath))[0]
        self.color = (127.5, 255.)
        #
        self.imgsz = self.itk_img.GetSize()
        self.ndim = len(self.imgsz)
        self.nframes = 1 if self.ndim == 2 else self.imgsz[2]
        self._cframe = 0
        self.all_annotations = [None for _ in range(self.nframes)]
        self._unchecked = set()
        #
        self.local_apath = None
        self.hist_apath = None
    #
    @property
    def name(self):
        return self._name
    @property
    def listname(self):
        return self._name if self.ndim==2 else f'[{self.nframes}] {self._name}'
    @property
    def statusname(self):
        parts = []
        if self.ndim == 3:
            parts.append(f'Frame {self.cframe+1} of {self.nframes}')
        sz = self.GetSize()
        parts.append(f'[{sz[0]}x{sz[1]}]')
        parts.append(self._name)
        if self.is_annotated:
            parts.append('(Annotated)')
        return ' '.join(parts)
    @property
    def titlename(self):
        if self.nframes > 1:
            return f'[{self.cframe}] {self._name}'
        return self._name
    # @property
    # def listName(self):
    #     bn = self._name if self.ndim==2 else f'[{self.nframes}] {self._name}'
    #     if self.is_annotated:
    #         return u'\u221A'+bn
    #     return u' '+bn
    #
    @property
    def cframe(self):
        return self._cframe
    @cframe.setter
    def cframe(self, v):
        try:
            if v < 0: v = 0
            elif v >= self.nframes: v = self.nframes - 1
        except Exception:
            v = 0
        self._cframe = v
    #
    @property
    def annotations(self):
        ann = self.all_annotations[self.cframe]
        if ann is None:
            ann = self.all_annotations[self.cframe] = MetaList()
        return ann
    @annotations.setter
    def annotations(self, v):
        self.all_annotations[self.cframe] = v
    #
    @property
    def is_annotated(self):
        return os.path.isfile(self.local_apath)
    #
    def GetNdArray(self):
        n_array = sitk.GetArrayFromImage(self.itk_img)
        return n_array[self.cframe] if self.ndim == 3 else n_array
    def GetOrigin(self):
        orig = self.itk_img.GetOrigin()
        return orig[:2] if self.ndim == 3 else orig
    def GetSize(self):
        return self.imgsz[:2] if self.ndim == 3 else self.imgsz
    def GetSpacing(self):
        spacing = self.itk_img.GetSpacing()
        return spacing[:2] if self.ndim == 3 else spacing
    #
    def isChecked(self, fr):
        return not fr in self._unchecked
    def setChecked(self, fr, st):
        if fr < 0 or fr >= self.nframes:
            return
        if not st:
            self._unchecked.add(fr)
        else:
            self._unchecked.discard(fr)
    def anyChecked(self):
        return len(self._unchecked) < self.nframes
    #
    def countChecked(self):
        return self.nframes - len(self._unchecked)
    #
    def importAnnotations(self, aa):
        for fr, _ in enumerate(self.all_annotations):
            ann = aa.get(fr)
            if isinstance(ann, tuple):
                ann = list(ann)
            self.all_annotations[fr] = ann
        if 'unchecked' in aa:
            self._unchecked.clear()
            for fr in aa['unchecked']:
                self._unchecked.add(fr)
    #
    def exportAnnotations(self):
        res = {}
        for fr, ann in enumerate(self.all_annotations):
            if not ann is None:
                res[fr] = ann
        if len(self._unchecked) > 0:
            res['unchecked'] = sorted(self._unchecked)
        return res
    #
    def acount(self):
        res = 0
        for ann in self.all_annotations:
            if ann:
                res += len(ann)
        return res
    #
    def aclear(self):
        self.all_annotations = [None for _ in range(self.nframes)]
    #

class EnterListWidget(QtWidgets.QListWidget):
    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == QtCore.Qt.Key_Enter or event.key() == QtCore.Qt.Key_Return:
            if self.currentItem():
                self.itemDoubleClicked.emit(self.currentItem())
        else:
            super().keyPressEvent(event)
#

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        
        self.setWindowIcon(qt_icon('ConeSegmentationML.png'))

        self._mute = True
        self._input_data = []
        self._cur_img_id = -1
        self._cur_3d = None
        self._status_id = -1
        
        self._icon_map = dict([
            (IMG_ICON_2D, qt_icon('circlegray')),
            (IMG_ICON_2D | IMG_ICON_ANN, qt_icon('circlegreen')),
            (IMG_ICON_3D, qt_icon('squareplusgray')),
            (IMG_ICON_3D | IMG_ICON_ANN, qt_icon('squareplusgreen')),
            (IMG_ICON_OPEN, qt_icon('squareminus')),
            (IMG_ICON_OPEN | IMG_ICON_ANN, qt_icon('squareminus'))
        ])
        
        self.loadDir = QtCore.QDir.home()
        self.saveDir = QtCore.QDir.home()
        self.xoptions = {}
        self.realNameMap = {}

        # State dir/files
        self.state_dir = os.path.join(os.path.expanduser('~'), '.ConeSegmentationML')
        if not os.path.exists(self.state_dir):
            os.mkdir(self.state_dir)
        self.state_file = os.path.join(self.state_dir, 'state.json')
        self.shortcuts_file = os.path.join(self.state_dir, 'shortcuts.json')
        
        #create backup directory
        self.hist = cfg.HistoryManager(self.state_dir, suffix='_contours.csv', retention_days=365)
            
        self._undo_buf = []

        self.setWindowTitle(cfg.APP_NAME+' ver. '+cfg.APP_VERSION)
        geom = QtWidgets.QApplication.primaryScreen().geometry()
        self.setMinimumSize(geom.width()*60/100, geom.height()*65/100)
        
        self.resize(geom.width()*70/100, geom.height()*70/100)
        self.move(geom.width()*12/100, geom.height()*10/100)

        self._setup_layout()
        self._setup_menu()
        self._setup_toolbar()

        self._status_bar = QtWidgets.QStatusBar()
        self._status_bar.setStyleSheet("QStatusBar{border-top: 1px outset grey;}")
        self.setStatusBar(self._status_bar)

        self._status_id = -1
        self.mposText = QtWidgets.QLabel()
        #self.mposText.setReadOnly(True)
        self.mposText.setMaximumWidth(geom.width()*40//100)
        self._status_bar.addPermanentWidget(self.mposText, 0)

        self._segmentation_para_dlg = ao_parameter_dialog(self)
        self._segmentation_para_dlg.setMinimumSize(geom.width()*24//100, geom.height()//4)
        self._display_settings_dlg = ao_display_settings(self)
        self._display_settings_dlg.smoothHotKey = self.smooth_act.shortcut().toString()
        self._display_settings_dlg.changed.connect(self._on_display_settings)
        self._display_settings_dlg.smoothChanged.connect(self._on_smooth_changed)
        self._progress_dlg = ao_progress_dialog(self)
        self._progress_dlg.setMinimumWidth(geom.width()/5)
        self._file_io = AOFileIO.ao_fileIO()
        self._segmentation = AOMethod.ao_method()
        #self._segmentation_models = self._segmentation.create_segmentation_models('model_weights')
        #self._segmentation_para_dlg.set_segmentation_weights(self._segmentation_models)
        #
        self._data_loc_dlg = ao_loc_dialog(self)
        self._data_loc_dlg.setMinimumWidth(geom.width()/2)
        #
        self._action_map = self.actionMap()
        self._default_key_map = self.hotkeys
        #
        self.status('Press F1 for help.')
        self.loadState()
        self.loadShortcuts()
        self.setAcceptDrops(True)
        self._mute = False
    #
    def keyReleaseEvent(self, e):
        if e.key() in (Qt.Qt.Key_Alt, Qt.Qt.Key_AltGr):
            while QtWidgets.QApplication.overrideCursor():
                QtWidgets.QApplication.restoreOverrideCursor()
            self._image_view.alt_reset()
    #
    def status(self, msg, temp=False):
        if temp:
            self.mposText.setText(msg)
        else:
            self._status_bar.showMessage(msg)
    #
    def actionMap(self):
        actmap = {}
        for onm in dir(self):
            if not hasattr(self, onm) or onm.startswith('__') or onm.startswith('_h_'): continue
            act = getattr(self, onm)
            if not isinstance(act, QtWidgets.QAction): continue
            ks = act.shortcut().toString()
            if ks:
                actmap[act.text()] = act
        return actmap
    #
    @property
    def hotkeys(self):
        res = {}
        for act_name, act in self._action_map.items():
            res[act_name] = act.shortcut().toString()
        return res
    @hotkeys.setter
    def hotkeys(self, key_map):
        for act_name, act in self._action_map.items():
            keystr = key_map.get(act_name, '')
            descr = act.statusTip() or act.toolTip()
            if not descr:
                descr = ''
            else:
                descr = descr.split('[')[0].strip()
            act.setShortcut(QtGui.QKeySequence(keystr))
            if descr and keystr:
                descr = f'{descr} [{keystr}]'
                act.setStatusTip(descr)
                act.setToolTip(descr)
        self._display_settings_dlg.smoothHotKey = self.smooth_act.shortcut().toString()
    #
    def loadState(self):
        try:
            with open(self.state_file, 'r') as fi:
                jobj = json.load(fi)
            if 'displaySettings' in jobj:
                self._image_view.displaySettings = jobj['displaySettings']
            self._segmentation_para_dlg.state = jobj['segmentation_para']
            if 'loadDir' in jobj:
                self.loadDir = QtCore.QDir(jobj['loadDir'])
            if 'saveDir' in jobj:
                self.saveDir = QtCore.QDir(jobj['saveDir'])
            if 'extended' in jobj:
                self.extended = jobj['extended']
            if 'realNameMap' in jobj:
                for usern, realn in jobj['realNameMap'].items():
                    self.realNameMap[usern] = realn
            if 'smooth' in jobj:
                self.smooth = jobj['smooth']
                self._on_smooth_act()
            if 'xoptions' in jobj:
                self.xoptions = jobj['xoptions']
        except Exception:
            pass
        usern = self.getUserName()
        if usern in self.realNameMap:
            realn = self.realNameMap[usern]
            if realn and realn != usern:
                MetaRecord.REAL_USER = self.getRealName()
        self._sync_display_controls()
    def saveState(self):
        try:
            ldir = self.loadDir.canonicalPath()
        except Exception:
            ldir = None
        try:
            sdir = self.saveDir.canonicalPath()
        except Exception:
            sdir = None
        try:
            jobj = {
                'segmentation_para': self._segmentation_para_dlg.state,
                'displaySettings': self._image_view.displaySettings,
                'extended': self.extended,
                'realNameMap': self.realNameMap,
                'smooth': self.smooth,
                'xoptions': self.xoptions,
            }
            if not ldir is None:
                jobj['loadDir'] = ldir
            if not sdir is None:
                jobj['saveDir'] = sdir
            with open(self.state_file, 'w') as fo:
                json.dump(jobj, fo, indent=2)
        except Exception:
            pass
    #
    def loadShortcuts(self):
        try:
            with open(self.shortcuts_file, 'r') as fi:
                self.hotkeys = json.load(fi)
        except Exception:
            pass
    def saveShortcuts(self):
        try:
            with open(self.shortcuts_file, 'w') as fo:
                json.dump(self.hotkeys, fo, indent=2)
        except Exception:
            pass
    #
    def getUserName(self):
        return os.getenv('USERNAME', '=Anonymous=')
    def getRealName(self, usern=None):
        if usern is None:
            usern = self.getUserName()
        if usern in self.realNameMap:
            return self.realNameMap[usern]
        return usern
    def setRealName(self, realn):
        usern = os.getenv('USERNAME', '=Anonymous=')
        if realn and realn != usern:
            self.realNameMap[usern] = realn
        else:
            if usern in self.realNameMap:
                del self.realNameMap[usern]
        self.saveState()
    #
    def dragEnterEvent(self, e):
        e.acceptProposedAction()
    def dropEvent(self, e):
        flist = cfg.InputList([url.toLocalFile() for url in e.mimeData().urls()])
        img_filenames = flist.get_files(('.tif', '.tiff'))
        csv_filenames = flist.get_files('.csv')
        strict = False
        if len(img_filenames) > 0:
            self._open_image_list(img_filenames, save_state=True)
            strict = True
        if len(csv_filenames) > 0:
            self._open_contour_list(csv_filenames, strict)
    #
    def closeEvent(self, e):
        for winname in ('helpwindow', 'srcwin', '_display_settings_dlg'):
            if hasattr(self, winname):
                getattr(self, winname).close()
        self._image_view.cancel_editing()
        self.saveState()
        e.accept()
    #
    def _set_mouse_mode(self, m):
        self._image_view._style.mouse_mode = m
        self._image_view.cancel_editing()
        self._image_view.visibility = True
        self._sync_display_controls()
        if m != MouseOp.Normal:
            if hasattr(self, 'bcwin') and not self.bcwin.manual:
                self.bcwin.close()
                del self.bcwin
                self._mute = True
                self.bc_act.setChecked(False)
                self._mute = False
    #
    def _initialize_input_data(self):
        self._image_view.abort_editing()
        self._input_data = []
        self._cur_img_id = -1
        self._cur_3d = None

    def _setup_layout(self):
        frame = Qt.QFrame()
        self._file_list = EnterListWidget(self)
        self._file_list.currentRowChanged.connect(self._file_list_row_changed)
        self._file_list.itemDoubleClicked.connect(self._file_list_item_doublecklicked)
        self._file_list.itemChanged.connect(self._file_list_item_changed)

        self.vtkFrame = vtkWidget = QVTKRenderWindowInteractor(frame)
        self._image_view = AOImageView.ao_visualization(vtkWidget, parent=self)

        flist_layout = Qt.QVBoxLayout()
        flist_layout.addWidget(self._file_list, 4)
        
        self.vtkWinWidget = QtWidgets.QWidget(self)
        vtk_layout = Qt.QVBoxLayout()
        self.vtkWinWidget.setLayout(vtk_layout)
        vtk_layout.addWidget(vtkWidget)

        view_layout = Qt.QGridLayout()
        view_layout.addWidget(self.vtkWinWidget, 0, 0)
        #view_layout.addWidget(vtkWidget, 0, 0)
        view_layout.addLayout(flist_layout, 0, 1, QtCore.Qt.AlignRight)
        view_layout.setColumnStretch(0, 5)
        view_layout.setColumnStretch(1, 1)

        ctl_layout = Qt.QGridLayout()
        ctl_layout.setColumnStretch(0, 0)
        ctl_layout.setColumnStretch(1, 10)
        ctl_layout.setColumnStretch(2, 0)
        ctl_layout.setColumnStretch(3, 0)
        iter_lb = QtWidgets.QLabel('Levelset Iterations:')
        ctl_layout.addWidget(iter_lb, 0, 0)
        self.iter_sl = sl = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        sl.setRange(0, 9)
        sl.setTickInterval(1)
        sl.setTickPosition(QtWidgets.QSlider.TicksAbove)
        sl.valueChanged.connect(self.onIterSlider)
        ctl_layout.addWidget(sl, 0, 1)
        self.iter_txt = QtWidgets.QLineEdit()
        self.iter_txt.setReadOnly(True)
        self.iter_txt.setMaximumWidth(150)
        ctl_layout.addWidget(self.iter_txt, 0, 2)
        self.iter_btn = QtWidgets.QPushButton("Freeze")
        self.iter_btn.setToolTip('Freeze current set of annotations, purge the rest')
        ctl_layout.addWidget(self.iter_btn, 0, 3)
        self.iter_btn.clicked.connect(self.onIterFreeze)
        
        self.visible_x = [iter_lb, self.iter_sl, self.iter_txt, self.iter_btn]
        for o in self.visible_x:
            o.setVisible(False)
        
        view_layout.addLayout(ctl_layout, 1, 0, 1, 2)

        self._iter_slider_status()
        #
        frame.setLayout(view_layout)
        self.setCentralWidget(frame)
        self.show()
    #
    def _iter_slider_status(self, rng=None, pos=None, val=None):
        if rng is None:
            self.iter_sl.setRange(0, 1)
            self.iter_sl.setValue(0)
            self.iter_sl.setEnabled(False)
            self.iter_txt.setText("")
            self.iter_txt.setEnabled(False)
            self.iter_btn.setEnabled(False)
        else:
            self.iter_sl.setRange(0, rng)
            self.iter_sl.setValue(pos)
            self.iter_sl.setEnabled(True)
            self.iter_txt.setText(str(val))
            self.iter_txt.setEnabled(True)
            self.iter_btn.setEnabled(True)
    #
    def _setup_menu(self):
        self.open_image_act = QtWidgets.QAction('Open...', self, shortcut=QtGui.QKeySequence.Open,
                    icon=qt_icon('open'),
                    toolTip='Open images and, optionally, segmentation results (contours-annotations)',
                    triggered=self._open_images)

        self.save_data_act = QtWidgets.QAction('Save...', self, shortcut=QtGui.QKeySequence.Save,
                    icon=qt_icon('save'),
                    toolTip='Save segmentation results (contours-annotations)',
                    triggered=self._save_data)

        self.save_stats_act = QtWidgets.QAction('Export Annotation Stats...', self,
                    toolTip='Export Statistics from the Annotation Tracking system',
                    triggered=self._save_stats)

        self.delete_all_act = QtWidgets.QAction('Delete Annotations', self,
                                      statusTip='Delete all annotations on current image', triggered=self._delete_all)

        self.quit_act = QtWidgets.QAction('Exit', self, shortcut=QtGui.QKeySequence.Quit,
                     toolTip="Quit the application", triggered=self._quit)
        
        self.experimental_act = QtWidgets.QAction('Multiple Levelset Iterations', self,
                checkable=True, checked=False,
                statusTip='Enable multiple values for the Levelset Iterations segmentation parameter',
                triggered=self._toggle_extended)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.open_image_act)
        file_menu.addAction(self.save_data_act)
        file_menu.addAction(self.save_stats_act)
        file_menu.addSeparator()
        file_menu.addAction(self.delete_all_act)
        advMenu = file_menu.addMenu('Advanced Options')
        advMenu.addAction(self.experimental_act)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_act)

        self.toggle_visibility = QtWidgets.QAction('Annotation Visibility', self, shortcut='F2',
                    iconText='Show', icon=qt_icon('fovea'),
                    checkable=True, checked=True,
                    statusTip='Show/Hide all annotations [F2]',
                    toolTip='Show/Hide all annotations [F2]',
                    triggered=self._toggle_visibility)

        self.toggle_rotation = QtWidgets.QAction('Contour Rotation', self, shortcut='Ctrl+R',
                    checkable=True, checked=True,
                    statusTip='Enable rotation when editing contours [Ctrl+R]',
                    toolTip='Enable rotation when editing contours [Ctrl+R]',
                    triggered=self._toggle_rotation)

        self.voronoi_act = QtWidgets.QAction('Voronoi', shortcut='Ctrl+V',
                icon=qt_icon('Voronoi'), statusTip='Toggle Voronoi Diagram display [Ctrl+V]',
                checkable=True, checked=False,
                triggered=self._toggle_voronoi)

        self.toggle_interpolation = QtWidgets.QAction('Image Interpolation', self, shortcut='Ctrl+I',
                    checkable=True, checked=True,
                    statusTip='Toggle Image Scale Pixel Interpolation [Ctrl+I]',
                    triggered=self._toggle_interpolation)

        self.reset_brightness_contrast = QtWidgets.QAction('Reset Image View', self, shortcut='F10',
                    statusTip='Reset Image View to the original size, position, brightness/contrast, etc. [F10]',
                    triggered=self._reset_brightness_contrast)

        self.data_loc_act = QtWidgets.QAction('Show data file locations', self, shortcut='Ctrl+L',
                    statusTip='Show data locations of the current image file [Ctrl+L]',
                    triggered=self._show_data_locations)

        self.bc_act = QtWidgets.QAction('Brightness/Contrast...', shortcut='F3',
                statusTip='Toggle Brightness/Contrast Window [F3]',
                checkable=True, checked=False,
                triggered=self._toggle_brightness_contrast)
        
        self.disp_act = QtWidgets.QAction('Display Settings...', iconText='Settings', shortcut='F5',
                icon=qt_icon('settings'), toolTip='Change Display Settings [F5]',
                triggered=self._show_display_settings)
        
        self.meta_act = QtWidgets.QAction('Annotation Sources...', shortcut='F6',
                toolTip='Highlight select annotation sources [F6]',
                triggered=self._select_annotation_sources)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.toggle_visibility)
        view_menu.addAction(self.voronoi_act)
        view_menu.addAction(self.toggle_interpolation)
        view_menu.addSeparator()
        view_menu.addAction(self.bc_act)
        view_menu.addAction(self.disp_act)
        view_menu.addAction(self.meta_act)
        view_menu.addSeparator()
        self.snap_annotated_act = QtWidgets.QAction('Snapshot...', self, shortcut='F7',
                    icon=qt_icon('camera'),
                    statusTip='Take a snapshot of the current image with annotations [F7]',
                    toolTip='Take a snapshot of the current image with annotations [F7]',
                    triggered=self._snap_annotated)
        view_menu.addAction(self.snap_annotated_act)

        self.screen_act = QtWidgets.QAction('Screenshot', self, shortcut='Ctrl+F7',
                    statusTip='Copy screenshot to clipboard [Ctrl+F7]',
                    toolTip='Copy screenshot to clipboard [Ctrl+F7]',
                    triggered=self._screen)
        view_menu.addAction(self.screen_act)

        view_menu.addSeparator()
        view_menu.addAction(self.data_loc_act)
        view_menu.addAction(self.reset_brightness_contrast)
        
        opt_menu = self.menuBar().addMenu("&Options")
        self.smooth_act = QtWidgets.QAction('Smooth Annotations', shortcut='Ctrl+T',
                toolTip='Apply Smmothing Splines to manually added or edited annotations [Ctrl+T]',
                statusTip='Apply Smmothing Splines to manually added or edited annotations [Ctrl+T]',
                checkable=True, checked=False, triggered=self._on_smooth_act)
        opt_menu.addAction(self.smooth_act)
        opt_menu.addAction(self.toggle_rotation)

        self.hotkey_act = QtWidgets.QAction('Customize Keyboard Shortcuts...',
                statusTip='Select user-defined keyboard shortcuts for common actions',
                triggered=self._on_hotkey_act)
        opt_menu.addAction(self.hotkey_act)

        self.about_act = QtWidgets.QAction('About', self,
                    icon=qt_icon('about'),
                    triggered=self._display_about)
        self.help_act = QtWidgets.QAction('Help on controls...', self, shortcut='F1',
                    icon=qt_icon('help'),
                    toolTip='Display help on keyboard and mouse controls [F1]',
                    statusTip='Display help on keyboard and mouse controls [F1]',
                    triggered=self._display_help)
        
        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.about_act)
        help_menu.addAction(self.help_act)
    #
    def _screen(self):
        orig = self.vtkFrame.mapToGlobal(QtCore.QPoint(0,0))
        sz = self.vtkFrame.size()
        rect = QtCore.QRect(orig, sz)
        pixmap = QtWidgets.QApplication.primaryScreen().grabWindow(0)
        pixmap = pixmap.copy(rect)
        #
        clip = QtWidgets.QApplication.clipboard()
        clip.setPixmap(pixmap)
        self.status('Viewport copied to clipboard.')
    #
    def _update_listwidget(self, newlist=True):
        if not self._cur_3d is None:
            imdat = self._cur_3d
            nitems = imdat.nframes + 1
            if nitems != self._file_list.count():
                newlist = True
            self._mute = True
            if newlist:
                self._file_list.clear()
                item = QtWidgets.QListWidgetItem(self._icon_map[IMG_ICON_OPEN], imdat.name, self._file_list)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Checked if imdat.anyChecked() else QtCore.Qt.Unchecked)
                font = item.font()
                hfont = QtGui.QFont(font.family(), font.pointSize(), QtGui.QFont.Bold)
                item.setFont(hfont)
                for i in range(imdat.nframes):
                    item = QtWidgets.QListWidgetItem(f'Frame {i+1}', self._file_list)
                    item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            for i in range(imdat.nframes):
                item = self._file_list.item(i+1)
                item.setCheckState(QtCore.Qt.Checked if imdat.isChecked(i) else QtCore.Qt.Unchecked)
            self._mute = False
            return
        if len(self._input_data) != self._file_list.count():
            newlist = True
        if newlist:
            self._file_list.clear()
            for imdat in self._input_data:
                ico_idx = IMG_ICON_3D if imdat.nframes > 1 else IMG_ICON_2D
                if imdat.is_annotated:
                    ico_idx |= IMG_ICON_ANN
                QtWidgets.QListWidgetItem(self._icon_map[ico_idx], imdat.listname, self._file_list)
                #self._file_list.addItem(imdat.listName)
        else:
            for row, imdat in enumerate(self._input_data):
                self._file_list.item(row).setText(imdat.listname)

    def _setup_toolbar(self):
        settings_bar = self.addToolBar("Settings")
        settings_bar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon);
        settings_bar.addAction(self.open_image_act)
        
        settings_bar.addAction(self.save_data_act)
        settings_bar.addSeparator()
        
        # Mouse Op button group
        mouse_group = QtWidgets.QActionGroup(self)
        self.default_act = QtWidgets.QAction('Adjust', mouse_group, shortcut='Ctrl+M',
                icon=qt_icon('mouse'), toolTip='Default Mouse Mode - adjust brightness/contrast [Ctrl+M]',
                checkable=True, checked=True,
                triggered=lambda: self._set_mouse_mode(MouseOp.Normal))
        settings_bar.addAction(self.default_act)
        self.draw_act = QtWidgets.QAction('Draw', mouse_group, shortcut='Ctrl+C',
                icon=qt_icon('draw_contour'), toolTip='Mouse Mode - Draw Cone Contours [Ctrl+C]',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.DrawContour))
        settings_bar.addAction(self.draw_act)
        self.edit_act = QtWidgets.QAction('Edit', mouse_group, shortcut='Ctrl+E',
                icon=qt_icon('edit'), toolTip='Mouse Mode - Edit Cone Contours [Ctrl+E]',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.EditContour))
        settings_bar.addAction(self.edit_act)
        self.erase_multi_act = QtWidgets.QAction('Erase M', mouse_group, shortcut='Ctrl+D',
                icon=qt_icon('erase'), toolTip='Mouse Mode - Erase Multiple Cone Contours [Ctrl+D]',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.EraseMulti))
        settings_bar.addAction(self.erase_multi_act)
        self.erase_single_act = QtWidgets.QAction('Erase S', mouse_group, shortcut='Ctrl+W',
                icon=qt_icon('erase_contour'), toolTip='Mouse Mode - Erase Single Cone Contour [Ctrl+W]',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.EraseSingle))
        settings_bar.addAction(self.erase_single_act)
        settings_bar.addSeparator()
        
        self.undo_act = QtWidgets.QAction('Undo', shortcut='Ctrl+Z',
                icon=qt_icon('redo'), toolTip='Undo last operation [Ctrl+Z]',
                triggered=self._undo)
        settings_bar.addAction(self.undo_act)
        self.undo_act.setEnabled(False)
        settings_bar.addSeparator()
        #
        settings_bar.addAction(self.toggle_visibility)
        settings_bar.addAction(self.disp_act)
        settings_bar.addAction(self.snap_annotated_act)
        settings_bar.addSeparator()
        #
        self.segment_act = QtWidgets.QAction('Segment', shortcut='Ctrl+G',
                icon=qt_icon('segment'), toolTip='Segment Cones on select images [Ctrl+G]',
                triggered=self._segment_cone_cells)
        settings_bar.addAction(self.segment_act)

        # segment_button = QtWidgets.QToolButton()
        # segment_button.setToolTip("Segment Cones on select images (Ctrl+G)")
        # segment_button.setIcon(qt_icon('segment'))
        # segment_button.setText("Segment")
        # segment_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        # segment_button.setShortcut('Ctrl+G')
        # segment_button.clicked.connect(self._segment_cone_cells)
        # settings_bar.addWidget(segment_button)
    #
    def _display_about(self):
        dlg = AboutDialog(self)
        dlg.exec_()
    #
    def _display_help(self):
        self.helpWindow = helpWindow = QtWidgets.QWidget()
        helpWindow.setWindowTitle(cfg.APP_NAME)
        helpWindow.setWindowIcon(qt_icon('help'))
        
        layout = Qt.QVBoxLayout()
        helpWindow.setLayout(layout)
        
        helpBrowser = QtWidgets.QTextBrowser()
        helpBrowser.setOpenExternalLinks(True)
        layout.addWidget(helpBrowser)
        
        helpFile = os.path.join(HELP_DIR, 'segmentml.html')
        if os.path.isfile(helpFile):
            url = QtCore.QUrl.fromLocalFile(helpFile)
            helpBrowser.setSource(url)
        else:
            helpBrowser.setText("Sorry, no help available at this time.")
        
        geom = QtWidgets.QApplication.primaryScreen().geometry()
        helpWindow.setMinimumSize(geom.width() * 60 // 100, geom.height() * 56 // 100)
        helpWindow.move(geom.width() * 20 // 100, geom.height() * 14 // 100)
        
        helpWindow.showNormal()
    #
    def _on_hotkey_act(self):
        dlg = ao_hotkey_dialog(self, self._action_map, self._default_key_map)
        dlg.update_key_map(self.hotkeys)
        if dlg.exec_():
            self.hotkeys = dlg.key_map
            self.saveShortcuts()
    #
    @property
    def smooth(self):
        return self.smooth_act.isChecked()
    @smooth.setter
    def smooth(self, st):
        self.smooth_act.setChecked(st)
    #
    @property
    def extended(self):
        return self.experimental_act.isChecked()
    @extended.setter
    def extended(self, st):
        self.experimental_act.setChecked(st)
    #
    def _toggle_extended(self):
        try:
            st = self.extended
            for o in self.visible_x:
                o.setVisible(st)
        except Exception:
            pass
    #
    def onIterSlider(self, v):
        try:
            self._image_view.cancel_editing()
            self.clear_undo()
            contours = self._input_data[self._cur_img_id].annotations
            contours.current_index = v
            #self.contour_pts_checkbox.setChecked(True)
            self._image_view.visibility = True
            self._sync_display_controls()
            self._set_contours(self._cur_img_id)
            self.SaveHistory()
        except Exception:
            pass
    #
    def onIterFreeze(self):
        try:
            contours = self._input_data[self._cur_img_id].annotations
            
            if not askYesNo('Confirm',
                    'You are about to "freeze" current set of annotations by deleting alternatives.',
                    detail='This operation can not be undone. \nContinue?'):
                return
            
            self._input_data[self._cur_img_id].annotations = contours.contours
            self._set_contours(self._cur_img_id)
            self.SaveHistory()
        except Exception:
            self.iter_btn.setEnabled(False)
    #
    def selected_imdat(self):
        if len(self._input_data) == 0 or self._cur_img_id == -1:
            return None
        return self._input_data[self._cur_img_id]
    def _snap_annotated(self):
        imdat = self.selected_imdat()
        if imdat is None: return
        dlg = ao_snap_dialog(parent=self, glyph_scale=0.5)
        dlg.setWindowTitle(imdat.listname+' - Snapshot')
        dlg.setWindowIcon(qt_icon('ConeSegmentationML.png'))
        dlg.setImageData(
            imdat.filepath,
            imdat.GetNdArray(),
            displaySettings=self._image_view.displaySettings,
            colorInfo=self._image_view.color_info,
        )
        contours = imdat.annotations
        if hasattr(contours, 'contours'):
            contours = contours.contours
        dlg.setContours(contours)
        dlg.exec_()
    #
    def _open_images(self):
        dlg = ao_open_dialog(self, self.hist)
        try:
            dlg.loadDir = self.loadDir.canonicalPath()
            dlg.annDir = self.saveDir.canonicalPath()
            dlg.setCheckedImages([imdat.filepath for imdat in self._input_data])
        except Exception:
            pass
        rc = dlg.selectImageFiles()
        if not rc: return
        rc = dlg.exec_()
        if not rc: return
        img_list = dlg.getImageList()
        ann_list = dlg.getAnnotationsList()
        no_ann = dlg.isNoAnnotations()
        if len(img_list) > 0:
            self.loadDir = QtCore.QDir(dlg.loadDir)
            self.saveDir = self.loadDir if no_ann else QtCore.QDir(dlg.annDir)
            self.saveState()
            self._open_image_list(img_list, ann_list, no_ann)
    #
    def _open_image_list(self, img_filenames, ann_filenames=None, no_ann=False, save_state=False):
        img_dir = None
        err_files = []
        if len(img_filenames) == 0:
            return
        self._initialize_input_data()
        self._image_view.reset_color()
        if hasattr(self, 'bcwin'):
            self.bcwin.color_info = self._image_view.color_info
        metainit()
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        self._progress_dlg.setWindowTitle('Open Images')
        self._progress_dlg.show()
        self._progress_dlg.set_progress(0)

        for idx, img_name in enumerate(img_filenames):
            try:
                itk_img = self._file_io.read_image(img_name)
                assert len(itk_img.GetSize()) in (2, 3)
            except Exception as ex:
                print(f'Failed to open {img_name}, possibly wrong format: {ex}')
                continue
            imdat = InputImageData(img_name, itk_img)
            imdat.hist_apath = self.hist.get_history_file(img_name)
            imdat.local_apath = self.hist.get_local_file(img_name)
            self._input_data.append(imdat)
            
            if img_dir is None:
                img_dir = os.path.abspath(os.path.dirname(img_name))
            
            aa = {}
            save_hist = False
            if not no_ann:
                if os.path.isfile(imdat.hist_apath):
                    aa = self._file_io.read_contours(imdat.hist_apath)
                elif os.path.isfile(imdat.local_apath):
                    aa = self._file_io.read_contours(imdat.local_apath)
                    save_hist = True
            imdat.importAnnotations(aa)
                
            if save_hist:
                self._file_io.write_contour(imdat.hist_apath, imdat.exportAnnotations(),
                        imdat.itk_img.GetOrigin(), imdat.itk_img.GetSpacing())

            self._progress_dlg.set_progress((idx+1)/float(len(img_filenames))* 100)
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)

        self._update_listwidget()
        self._image_view.image_visibility = True
        self._display_image(0)
        self._cur_img_id = 0
        self._file_list.setCurrentRow(self._cur_img_id)

        self._progress_dlg.set_progress(0);
        QtWidgets.QApplication.restoreOverrideCursor()
        self._progress_dlg.hide()
        #
        if img_dir is None:
            img_dir = ''
        elif save_state:
            self.saveDir = self.loadDir = QtCore.QDir(img_dir)
            self.saveState()
        self.status(img_dir)
    #
    def _get_data_index(self, csv_file_path, strict=True):
        fn = os.path.basename(csv_file_path)
        bn, ext = os.path.splitext(fn)
        for id, imdat in enumerate(self._input_data):
            if strict:
                if bn == imdat.name:
                    return id
        else:
            if bn.startswith(imdat.name):
                return id
        return -1
    #        
    def _open_contour_list(self, csv_filenames, strict=True):
        err_files = []
        for csv_file in csv_filenames:
            id = self._get_data_index(csv_file, strict)
            if id != -1:
                imdat = self._input_data[id]
                try:
                    aa = self._file_io.read_contours(csv_file, ignore_errors=False)
                except Exception:
                    err_files.append(os.path.basename(csv_file))
                    continue
                
                imdat.importAnnotations(aa)
                self._file_io.write_contour(imdat.hist_apath, imdat.exportAnnotations(),
                                imdat.itk_img.GetOrigin(), imdat.itk_img.GetSpacing())
        if self._cur_img_id >= 0:
            self._display_image(self._cur_img_id)
        if len(err_files) > 0:
            if len(err_files) > 5:
                err_files = err_files[:4] + ['... +%d more.' % (len(err_files)-4,)]
            display_error('Failed to read the following file(s):', '\n'.join(err_files) + \
                '\n(do you attempt to open spreadsheet(s) generated by other applications?)')
    #
    def _show_data_locations(self):
        if self._cur_img_id < 0 or self._cur_img_id >= len(self._input_data):
            return
        imdat = self._input_data[self._cur_img_id]
        #
        img_path = os.path.abspath(imdat.filepath)
        self._data_loc_dlg.setPaths(imgdat.itk_img, img_path, imdat.local_apath, imdat.hist_apath)
        self._data_loc_dlg.exec()
    #
    def next_image(self):
        if self._file_list.currentRow() < self._file_list.count() - 1:
            self._file_list.setCurrentRow(self._file_list.currentRow() + 1)
    def previous_image(self):
        if self._file_list.currentRow() > 0:
            self._file_list.setCurrentRow(self._file_list.currentRow() - 1)
    def _file_list_row_changed(self, newrow):
        if self._cur_3d:
            imdat = self._cur_3d
            imdat.color = self._image_view.color_info
            if newrow > 0 and newrow <= imdat.nframes:
                imdat.cframe = newrow - 1
                self._display_image(self._cur_img_id)
            return
        if self._cur_img_id >= 0:
            imdat = self._input_data[self._cur_img_id]
            imdat.color = self._image_view.color_info
        self._cur_img_id = newrow
        self._display_image(self._cur_img_id)
    #
    def _file_list_item_doublecklicked(self, item):
        row = self._file_list.row(item)
        if self._cur_3d:
            if row == 0:
                self._cur_3d = None
                row = self._cur_img_id
            else:
                row = -1
        else:
            imdat = self._input_data[row]
            if imdat.nframes > 1:
                self._cur_img_id = row
                self._cur_3d = imdat
                row = imdat.cframe + 1
            else:
                row = -1
        if row >= 0:
            self._update_listwidget(newlist=True)
            self._file_list.setCurrentRow(row)
    #
    def _file_list_item_changed(self, item):
        if self._mute or self._cur_3d is None: return
        self._mute = True
        row = self._file_list.row(item)
        checked = item.checkState() == QtCore.Qt.Checked
        imdat = self._cur_3d
        if row == 0:
            check = QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked
            for i in range(1, self._file_list.count()):
                self._file_list.item(i).setCheckState(check)
                imdat.setChecked(i-1, checked)
        else:
            imdat.setChecked(row-1, checked)
        self._mute = False
        if row != self._file_list.currentRow():
            self._file_list.setCurrentRow(row)
    def _update_source_win(self, contours):
        if self._mute: return
        if hasattr(self, 'srcwin') and self.srcwin.isVisible():
            self.srcwin.setMetaList(contours)
    #
    def _set_contours(self, idx, edit_idx=None):
        if idx is None:
            idx = self._cur_img_id
        if idx < 0 or idx >= len(self._input_data):
            return
        imdat = self._input_data[idx]

        contours = imdat.annotations
        if hasattr(contours, 'contours'):
            self._image_view.set_contours(contours.contours, edit_idx)
            self._iter_slider_status(
                    rng=len(contours.keys())-1,
                    pos=contours.current_index,
                    val=contours.current_key)
        else:
            self._image_view.set_contours(contours, edit_idx)
            self._iter_slider_status(None)
        self._update_source_win(contours)
    #
    def _display_image(self, idx):
        self.clear_undo()
        self._image_view.initialization()
        if idx < 0 or idx >= len(self._input_data):
            return
        imdat = self._input_data[idx]
        self._image_view.set_image(imdat.itk_img, n_array=imdat.GetNdArray())
        self._image_view.color_info = imdat.color
        self._set_contours(idx)
        self._image_view.visibility = True
        self._sync_display_controls()
        self._image_view.reset_view(True)
        if hasattr(self, 'bcwin'):
            self.bcwin.color_info = self._image_view.color_info

    def _segment_cone_cells(self):
        #res = AOSettingsDialog.display_warning('Detecting cone cells', 'Do you really want to detect cells?')
        self._segmentation_para_dlg.extended = self.extended
        sv_state = self._segmentation_para_dlg.state
        self._segmentation_para_dlg.SetImageList([imdat.name for imdat in self._input_data])
        c_rows = [row for row, imdat in enumerate(self._input_data) if imdat.acount() == 0]
        self._segmentation_para_dlg.SetCheckedRows(c_rows)
        self._segmentation_para_dlg.SetHighlightedRow(self._cur_img_id)
        res = self._segmentation_para_dlg.exec()
        if res == QtWidgets.QDialog.Rejected:
            self._segmentation_para_dlg.state = sv_state
            return
        
        c_rows = self._segmentation_para_dlg.checkedRows()
        self.saveState()
        progr_total = sum([self._input_data[row].countChecked() for row in c_rows])
        if progr_total == 0:
            display_error('Input error', 'Nothing was checked.')
            return

        cur_segmentation_model = self._segmentation_para_dlg.model_weights
        if not cur_segmentation_model:
            display_error('Input errors:', 'Missing Segmentation Model Weights!')
            return
        for fpath in cur_segmentation_model.values():
            mdir = os.path.dirname(fpath)
            self.status('Using Segmentation Model Weights from: '+mdir)
            break

        self._image_view.cancel_editing()
        self.clear_undo()
        self._image_view.visibility = True
        self._sync_display_controls()

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        self._progress_dlg.setWindowTitle('Segment cones ...')
        self._progress_dlg.show()
        self._progress_dlg.set_progress(0)
        progr_cur = 0

        fov = self._segmentation_para_dlg.image_fov
        levelset_iterations = self._segmentation_para_dlg.levelset_iterations
        contour_length = self._segmentation_para_dlg.contour_length

        try:
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
            
            for i, row in enumerate(c_rows):
                imdat = self._input_data[row]
                
                aa = {}
                if imdat.nframes > 1:
                    n_array = sitk.GetArrayFromImage(imdat.itk_img)
                    for fr in range(imdat.nframes):
                        if not imdat.isChecked(fr): continue
                        itk_img = sitk.GetImageFromArray(n_array[fr])
                        aa[fr] = self._segmentation.segment_cones(
                            cur_segmentation_model, itk_img, fov, levelset_iterations, contour_length)
                        progr_cur += 1
                        self._progress_dlg.set_progress(float(progr_cur)/float(progr_total) * 100.)
                        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
                else:
                    aa[0] = self._segmentation.segment_cones(
                        cur_segmentation_model, imdat.itk_img, fov, levelset_iterations, contour_length)
                    progr_cur += 1
                    self._progress_dlg.set_progress(float(progr_cur)/float(progr_total) * 100.)
                    QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
                
                imdat.importAnnotations(aa)
                self.SaveHistory(row)
    
                self._progress_dlg.set_progress( (i+1)*100. / float(len(c_rows)) )
                QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
    
            if not self._cur_img_id in c_rows:
                self._file_list.setCurrentRow(c_rows[0])
            else:
                self._set_contours(self._cur_img_id)
                self._image_view.reset_view()
        except Exception as ex:
            display_error('In Segment Cone Cells:', ex)

        self._progress_dlg.set_progress(0);
        QtWidgets.QApplication.restoreOverrideCursor()
        self._progress_dlg.hide()
    #
    def SaveHistory(self, i=None):
        if i is None:
            i = self._cur_img_id
        if i < 0:
            return
        imdat = self._input_data[i]
        aa_src = imdat.exportAnnotations()
        aa = {}
        for fr, contours in aa_src.items():
            if hasattr(contours, 'contours'):
                contours = contours.contours
            aa[fr] = contours
        self._file_io.write_contour(imdat.hist_apath, aa, imdat.itk_img.GetOrigin(), imdat.itk_img.GetSpacing())
    #
    def _sync_display_controls(self):
        self._mute = True
        self.toggle_interpolation.setChecked(self._image_view.interpolation)
        self.voronoi_act.setChecked(self._image_view.voronoi)
        self.toggle_visibility.setChecked(self._image_view.visibility)
        self.toggle_rotation.setChecked(self._image_view.rotation)
        self._mute = False
        self._toggle_extended()
    def _on_display_settings(self, param):
        self._image_view.displaySettings = param
        self._sync_display_controls()
        self._image_view.reset_view(False)
        self.saveState()
    #
    def _undo(self, e):
        self._image_view.cancel_editing()
        self._image_view.visibility = True
        self._sync_display_controls()
        self.do_undo()
    #
    def do_undo(self):
        if len(self._undo_buf) == 0:
            return
        if self._cur_img_id == -1:
            self.clear_undo()
            return
        contours = self._input_data[self._cur_img_id].annotations
        modified = False
        while True:
            e = self._undo_buf.pop()
            if e.op == UndoOp.Added:
                for i, c in enumerate(contours):
                    if e.data is c:
                        del contours[i]
                        modified = True
                        break
            elif e.op == UndoOp.Removed:
                contours.append(e.data)
                modified = True
            elif e.op == UndoOp.Image:
                self._image_view.color_info = e.data
                if hasattr(self, 'bcwin'):
                    self.bcwin.color_info = e.data
            if e.last: break
        if modified:
            self._set_contours(self._cur_img_id)
            self.SaveHistory()
        self.undo_act.setEnabled(len(self._undo_buf) > 0)
    #
    def push_undo(self, op, data, last=True):
        self._undo_buf.append(UndoEntry(op, last, data))
        self.undo_act.setEnabled(True)
    #
    def push_color_undo(self, ci):
        if len(self._undo_buf) == 0 or self._undo_buf[-1].op != UndoOp.Image:
            self._undo_buf.append(UndoEntry(UndoOp.Image, True, ci))
        self.undo_act.setEnabled(True)
    #
    def clear_undo(self):
        self._undo_buf.clear()
        self.undo_act.setEnabled(False)
    #
    def _toggle_voronoi(self):
        if not self._mute:
            self._image_view.voronoi = self.voronoi_act.isChecked()
            self.saveState()
    #
    def AddContour(self, contour_pts):
        if self._cur_img_id == -1:
            return
        contours = self._input_data[self._cur_img_id].annotations
        c = optimizeContour(contour_pts)
        if self.smooth:
            c = smoothContour(c, clip=self._image_view.get_original_size())
        if len(c) < 3:
            return
        if isTooSmall(c):
            if not askYesNo('Annotation too small', 'Are you sure you want to add it?'):
                return
        self.push_undo(UndoOp.Added, c)
        contours.append(c)
        self._set_contours(self._cur_img_id)
        self.SaveHistory()
    #
    def RemoveContoursInside(self, contour_pts):
        if self._cur_img_id == -1:
            return
        contour_pts = optimizeContour(contour_pts)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        in_contours = self._input_data[self._cur_img_id].annotations
        out_contours = []
        last = True
        for c in in_contours:
            if isIntersected(c, contour_pts):
                self.push_undo(UndoOp.Removed, c, last)
                last = False
            else:
                out_contours.append(c)
        QtWidgets.QApplication.restoreOverrideCursor()
        if not last:
            if hasattr(in_contours, 'contours'):
                in_contours = in_contours.contours
            if hasattr(in_contours, 'update'):
                in_contours.update(out_contours)
            else:
                self._input_data[self._cur_img_id].annotations = out_contours
            self._set_contours(self._cur_img_id)
            self.SaveHistory()
    #
    def RemoveContourAt(self, pt):
        if self._cur_img_id == -1:
            return
        in_contours = self._input_data[self._cur_img_id].annotations
        out_contours = []
        last = True
        for c in in_contours:
            if isPointInside(pt, c):
                self.push_undo(UndoOp.Removed, c, last)
                last = False
            else:
                out_contours.append(c)
        if not last:
            if hasattr(in_contours, 'contours'):
                in_contours = in_contours.contours
            if hasattr(in_contours, 'update'):
                in_contours.update(out_contours)
            else:
                self._input_data[self._cur_img_id].annotations = out_contours
            self._set_contours(self._cur_img_id)
            self.SaveHistory()
    #
    def EditContourAt(self, pt):
        if self._cur_img_id == -1:
            return
        contours = self._input_data[self._cur_img_id].annotations
        if hasattr(contours, 'contours'):
            contours = contours.contours
        self._edited_contour_idx = idx = findContour(pt, contours)
        if idx < 0:
            idx = None
        else:
            contour = optimizeContour(contours[idx])
            contours[idx][:] = contour
            if self.smooth:
                sm_contour = smoothContour(contour, clip=self._image_view.get_original_size())
                if contourChanged(sm_contour, contour):
                    self.push_undo(UndoOp.Added, sm_contour)
                    self.push_undo(UndoOp.Removed, contours[idx], False)
                    contours[idx] = sm_contour
        self._set_contours(self._cur_img_id, idx)
    #
    def UpdateContour(self, idx, contour_pts):
        if self._cur_img_id == -1:
            return
        contours = self._input_data[self._cur_img_id].annotations
        if hasattr(contours, 'contours'):
            contours = contours.contours
        meta_changed = False
        if hasattr(contours, 'meta'):
            if contours.meta.objmeta(contours[idx]).metakey != contours.meta.default.metakey:
                meta_changed = True
        if meta_changed or contourChanged(contours[idx], contour_pts):
            if self.smooth:
                contour_pts = smoothContour(contour_pts, clip=self._image_view.get_original_size())
            self.push_undo(UndoOp.Added, contour_pts)
            self.push_undo(UndoOp.Removed, contours[idx], False)
            contours[idx] = contour_pts
            self.SaveHistory()
            self._update_source_win(contours)
    #
    def _save_data(self):
        if len(self._input_data) == 0: return
        self._image_view.cancel_editing()
        try:
            try:
                sdir = self.saveDir.canonicalPath()
            except Exception:
                sdir = QtCore.QDir.homePath()
                
            dlg = AODirectoryDialog(sdir, 'Select output directory')
            dlg.xoptions = self.xoptions
            dir_name = dlg.run()
                
            #dir_name = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select saving directory', sdir)
            
            if dir_name:
                self.xoptions = dlg.xoptions
                cnt = 0
                for imdat in self._input_data:
                    if imdat.acount() == 0: continue
                    img_name, _ = os.path.splitext(imdat.name)
                    fn = os.path.basename(imdat.local_apath)
                    apath = os.path.abspath(os.path.join(dir_name, fn))
                    self._file_io.write_contour(apath, imdat.exportAnnotations(), imdat.GetOrigin(), imdat.GetSpacing())
                    self._file_io.write_contour_extra(dir_name, img_name, imdat.exportAnnotations(), self.xoptions)
                    cnt += 1
                #
                self.status('%d contour file(s) saved to %s' % (cnt, dir_name))
                self._update_listwidget(newlist=False)
                self.saveDir = QtCore.QDir(dir_name)
                self.saveState()
        except Exception as ex:
            display_error('Error saving data', ex)
    #
    def _delete_all(self):
        id = self._cur_img_id
        if id < 0: return
        imdat = self._input_data[self._cur_img_id]
        if imdat.acount() == 0: return
        if not askYesNo('Confirm',
                'You are about to delete all annotations \non the current image.',
                detail='This operation can not be undone. \nContinue?'):
            return
        self._image_view.cancel_editing()
        self.clear_undo()
        #self.contour_pts_checkbox.setChecked(True)
        self._image_view.visibility = True
        self._sync_display_controls()
        imdat.aclear()
        self._image_view.set_contours(imdat.annotations)
        self._image_view.reset_view(False)
        self.SaveHistory()

    def _quit(self, event):
        self.close()
        
    def _toggle_visibility(self):
        if not self._mute:
            self._image_view.visibility = self.toggle_visibility.isChecked()
    #
    def _toggle_interpolation(self):
        if not self._mute:
            self._image_view.interpolation = self.toggle_interpolation.isChecked()
            self._image_view.reset_view()
            self.saveState()
    #
    def _toggle_rotation(self):
        if not self._mute:
            self._image_view.rotation = self.toggle_rotation.isChecked()
    #
    def _reset_brightness_contrast(self):
        self.resetSources()
        self._image_view.reset_color()
        if hasattr(self, 'bcwin'):
            self.bcwin.color_info = self._image_view.color_info
        if self._cur_img_id >= 0:
            self._input_data[self._cur_img_id].color = self._image_view.color_info
        self._image_view.reset_view(True)
        self._image_view.image_visibility = True
    #
    def _show_display_settings(self, e):
        self._display_settings_dlg.displaySettings = self._image_view.displaySettings
        self._display_settings_dlg.showNormal()
    #
    def trackMousePos(self, x, y):
        msg = ''
        try:
            contours = self._input_data[self._cur_img_id].annotations
            if hasattr(contours, 'contours'):
                contours = contours.contours
            idx = findContour((x, y, 0), contours)
            meta = contours.objmeta(contours[idx])
            if meta:
                meta = str(meta)
            else:
                meta = ''
        except Exception:
            idx = -1
            meta = ''
        if self._status_id != idx:
            self._status_id = idx
            if idx >= 0:
                x, y = contourCenter(contours[idx])
                msg = f'({x:.0f},{y:.0f}): {meta}'
            self.status(msg, temp=True)
    #
    def _update_sources(self):
        self._mute = True
        self._set_contours(self._cur_img_id)
        self._image_view.reset_view()
        self._mute = False
    #
    def resetSources(self, update=False):
        id = self._cur_img_id
        if id < 0: return
        contours = self._input_data[id].annotations
        if hasattr(contours, 'contours'):
            contours = contours.contours
        if hasattr(contours, 'setGrayMeta'):
            contours.setGrayMeta([])
        self._set_contours(self._cur_img_id)
        if update:
            self._image_view.reset_view()
    #
    def _select_annotation_sources(self, e):
        id = self._cur_img_id
        if id < 0: return
        contours = self._input_data[id].annotations
        if hasattr(contours, 'contours'):
            contours = contours.contours
        #if len(contours) == 0: return

        self._image_view.cancel_editing()
        self._image_view.visibility = True
        self._sync_display_controls()
        self._image_view.reset_view()
        
        if not hasattr(self, 'srcwin'):
            self.srcwin = ao_source_window(self)
        self.srcwin.setMetaList(contours)
        self.srcwin.show()
        self.srcwin.activateWindow()
    #
    def onBCci(self, ci):
        self.push_color_undo(self._image_view.color_info)
        self._image_view.color_info = ci
    def onIWci(self, ci):
        if not hasattr(self, 'bcwin'):
            self.bcwin = ao_brightness_contrast(self, parent=self.vtkWinWidget, callback=self.onBCci)
            self.bcwin.color_info = self._image_view.color_info
            self.bcwin.manual = False
            self._mute = True
            self.bc_act.setChecked(True)
            self._mute = False
        else:
            self.bcwin.color_info = ci
        self.bcwin.show()
    def _toggle_brightness_contrast(self):
        if self._mute: return
        if self.bc_act.isChecked():
            if not hasattr(self, 'bcwin'):
                self.bcwin = ao_brightness_contrast(self, parent=self.vtkWinWidget, callback=self.onBCci)
            self.bcwin.color_info = self._image_view.color_info
            self.bcwin.show()
            self.bcwin.activateWindow()
        else:
            if hasattr(self, 'bcwin'):
                self.bcwin.close()
                del self.bcwin
    #
    def _on_smooth_act(self):
        self._display_settings_dlg.smoothAnnotations = self.smooth
        self.saveState()
    def _on_smooth_changed(self):
        self.smooth = self._display_settings_dlg.smoothAnnotations
        self.saveState()
    #
    def _save_stats(self):
        if len(self._input_data) == 0: return
        self._image_view.cancel_editing()
        try:
            try:
                sdir = self.saveDir.canonicalPath()
            except Exception:
                sdir = QtCore.QDir.homePath()
            dir_name = QtWidgets.QFileDialog.getExistingDirectory(self, \
                    'Select Export directory', sdir)
            if not dir_name:
                return
            
            cnt = self._file_io.write_annotation_stats(dir_name, self._input_data)
            self.status('%d Annotation Tracker Statistics file(s) exported to %s' % (cnt, dir_name))
            #self._update_listwidget(self._input_data['image file paths'], newlist=False)
            #self.saveDir = QtCore.QDir(dir_name)
            #self.saveState()
        except Exception as ex:
            display_error('Error annotation stats', ex)

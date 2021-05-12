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
import AOSettingsDialog
from AOSettingsDialog import ao_open_dialog, ao_parameter_dialog
from AOSettingsDialog import ao_progress_dialog, ao_loc_dialog
from AOSettingsDialog import display_error, display_warning
import AOConfig as cfg

BASE_DIR = os.path.dirname(__file__)
ICONS_DIR = os.path.join(BASE_DIR, 'Icons')
HELP_DIR = os.path.join(BASE_DIR, 'Help')
def qt_icon(name):
    return QtGui.QIcon(os.path.join(ICONS_DIR, name))

_big_icon = QtCore.QUrl.fromLocalFile(os.path.join(ICONS_DIR, 'ConeSegmentationML256.png'))
about_html = '''
<table><tr>
<td><img src="%s">&nbsp;&nbsp;</td>
<td><b>%s %s</b><div>
Tam lab<br>
National Eye Institute<br>
National Institutes of Health</div><div><br>
If any portion of this software is used, please<br>
cite the following paper in your publication:
</div></td></tr><tr><td colspan=2>
[Placeholder for IEEE TMI paper]
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
        #
        buttonbox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.close)
        #
        layout.addWidget(lbl)
        layout.addWidget(buttonbox)
        self.setLayout(layout)
#

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        
        self.setWindowIcon(qt_icon('ConeSegmentationML.png'))

        self._input_data = {
            'image file paths': [],
            'image names': [],
            'images': [],
            'contours': [],
        }
        self._cur_img_id = -1
        self.loadDir = QtCore.QDir.home()
        self.saveDir = QtCore.QDir.home()

        # State dir/file
        self.state_dir = os.path.join(os.path.expanduser('~'), '.ConeSegmentationML')
        if not os.path.exists(self.state_dir):
            os.mkdir(self.state_dir)
        self.state_file = os.path.join(self.state_dir, 'state.json')
        
        #create backup directory
        self.hist = cfg.HistoryManager(self.state_dir, suffix='_contours.csv', retention_days=365)
            
        self._undo_buf = []

        self.setWindowTitle(cfg.APP_NAME+' ver. '+cfg.APP_VERSION)
        geom = QtWidgets.QApplication.primaryScreen().geometry()
        self.setMinimumSize(geom.width()*60/100, geom.height()*65/100)

        self._setup_layout()
        self._setup_menu()
        self._setup_toolbar()

        self._status_bar = QtWidgets.QStatusBar()
        self._status_bar.setStyleSheet("QStatusBar{border-top: 1px outset grey;}")
        self.setStatusBar(self._status_bar)

        self._segmentation_para_dlg = ao_parameter_dialog(self)
        self._segmentation_para_dlg.setMinimumSize(geom.width()*24//100, geom.height()//4)
        self._progress_dlg = ao_progress_dialog(self)
        self._progress_dlg.setMinimumWidth(geom.width()/5)
        self._file_io = AOFileIO.ao_fileIO()
        self._segmentation = AOMethod.ao_method()
        self._segmentation_models = self._segmentation.create_segmentation_models('model_weights')
        self._segmentation_para_dlg.set_segmentation_weights(self._segmentation_models)
        #
        self._data_loc_dlg = ao_loc_dialog(self)
        self._data_loc_dlg.setMinimumWidth(geom.width()/2)
        #
        self._status_bar.showMessage('Press F1 for help.')
        self.loadState()
        self.setAcceptDrops(True)
    #
    def loadState(self):
        try:
            with open(self.state_file, 'r') as fi:
                jobj = json.load(fi)
            if 'interpolation' in jobj:
                self._image_view.interpolation = jobj['interpolation']
                self.toggle_interpolation.setChecked(self._image_view.interpolation)
            if 'contour_width' in jobj:
                self._contour_width_input.setValue(int(jobj['contour_width']))
            self._segmentation_para_dlg.set_state(jobj['segmentation_para'])
            if 'loadDir' in jobj:
                self.loadDir = QtCore.QDir(jobj['loadDir'])
            if 'saveDir' in jobj:
                self.saveDir = QtCore.QDir(jobj['saveDir'])
        except Exception:
            pass
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
                'segmentation_para': self._segmentation_para_dlg.get_state(),
                'contour_width': self._contour_width_input.value(),
                'interpolation': self._image_view.interpolation,
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
    def dragEnterEvent(self, e):
        e.acceptProposedAction()
    def dropEvent(self, e):
        flist = cfg.InputList([url.toLocalFile() for url in e.mimeData().urls()])
        img_filenames = flist.get_files(('.tif', '.tiff'))
        csv_filenames = flist.get_files('.csv')
        strict = False
        if len(img_filenames) > 0:
            self._open_image_list(img_filenames)
            strict = True
        if len(csv_filenames) > 0:
            self._open_contour_list(csv_filenames, strict)
    #
    def closeEvent(self, e):
        if hasattr(self, 'helpWindow'):
            self.helpWindow.close()
        self._image_view.cancel_editing()
        self.saveState()
        e.accept()
    #
    def _set_mouse_mode(self, m):
        self._image_view._style.mouse_mode = m
        self._image_view.cancel_editing()
        self.contour_pts_checkbox.setChecked(True)
    #
    def _initialize_input_data(self):
        self._image_view.abort_editing()
        self._input_data['image file paths'].clear()
        self._input_data['image names'].clear()
        self._input_data['images'].clear()
        self._input_data['contours'].clear()

    def _setup_layout(self):
        frame = Qt.QFrame()
        self._file_list = QtWidgets.QListWidget(self)
        self._file_list.currentRowChanged.connect(self._file_list_row_changed)

        vtkWidget = QVTKRenderWindowInteractor(frame)
        self._image_view = AOImageView.ao_visualization(vtkWidget, parent=self)

        flist_layout = Qt.QVBoxLayout()
        flist_layout.addWidget(self._file_list, 4)

        view_layout = Qt.QGridLayout()
        view_layout.addWidget(vtkWidget, 0, 0)
        view_layout.addLayout(flist_layout, 0, 1, QtCore.Qt.AlignRight)
        view_layout.setColumnStretch(0, 5)
        view_layout.setColumnStretch(1, 1)

        frame.setLayout(view_layout)
        self.setCentralWidget(frame)
        self.show()

    def _setup_menu(self):
        self.open_image_act = QtWidgets.QAction('Open...', self, shortcut=QtGui.QKeySequence.Open,
                    icon=qt_icon('open'),
                    toolTip='Open image(s) and (optionally) segmentation results (contours-annotations)',
                    triggered=self._open_images)

        self.save_data_act = QtWidgets.QAction('Save...', self, shortcut=QtGui.QKeySequence.Save,
                    icon=qt_icon('save'),
                    toolTip='Save segmentation results (contours-annotations)',
                    triggered=self._save_data)

        quit = QtWidgets.QAction('Exit', self, shortcut=QtGui.QKeySequence.Quit,
                     toolTip="Quit the application", triggered=self._quit)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.open_image_act)
        file_menu.addAction(self.save_data_act)
        file_menu.addSeparator()
        file_menu.addAction(quit)

        self.toggle_visibility = QtWidgets.QAction('Annotation Visibility', self, shortcut='F2',
                    checkable=True, checked=True,
                    statusTip='Toggle Annotation Visibility (F2)',
                    triggered=self._toggle_visibility)

        self.toggle_interpolation = QtWidgets.QAction('Image Interpolation', self, shortcut='Ctrl+I',
                    checkable=True, checked=True,
                    statusTip='Toggle Image Scale Pixel Interpolation (Ctrl+I)',
                    triggered=self._toggle_interpolation)

        self.reset_brightness_contrast = QtWidgets.QAction('Reset Image View', self, shortcut='F10',
                    statusTip='Reset Image View to the original size, position, brightness/contrast, etc.',
                    triggered=self._reset_brightness_contrast)

        self.data_loc_act = QtWidgets.QAction('Show data file locations', self, shortcut='Ctrl+L',
                    statusTip='Show data locations of the current image file',
                    triggered=self._show_data_locations)

        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self.toggle_visibility)
        view_menu.addAction(self.toggle_interpolation)
        view_menu.addSeparator()
        view_menu.addAction(self.reset_brightness_contrast)
        view_menu.addAction(self.data_loc_act)

        self.about_act = QtWidgets.QAction('About', self,
                    icon=qt_icon('about'),
                    triggered=self._display_about)
        self.help_act = QtWidgets.QAction('Keyboard Shortcuts...', self, shortcut='F1',
                    icon=qt_icon('help'),
                    toolTip='Display list of keyboard shortcuts',
                    triggered=self._display_help)
        
        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.about_act)
        help_menu.addAction(self.help_act)

        # Invisible actions, just to make Up/Down arrows scroll through image list
        self._next_image_act = QtWidgets.QAction('NextImage', self,
                    shortcut='Down', triggered=self.next_image)
        self._prev_image_act = QtWidgets.QAction('PreviousImage', self,
                    shortcut='Up', triggered=self.previous_image)
    #
    def _update_listwidget(self, image_paths, newlist=True):
        if len(image_paths) != self._file_list.count():
            newlist = True
        if newlist:
            self._file_list.clear()
            for img_path in image_paths:
                bn, _ = os.path.splitext(os.path.basename(img_path))
                self._file_list.addItem(self.hist.get_list_name(img_path))
        else:
            for row, img_path in enumerate(image_paths):
                self._file_list.item(row).setText(self.hist.get_list_name(img_path))

    def _setup_toolbar(self):
        settings_bar = self.addToolBar("Settings")
        settings_bar.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon);
        settings_bar.addAction(self.open_image_act)
        
        settings_bar.addAction(self.save_data_act)
        settings_bar.addSeparator()
        
        # Mouse Op button group
        mouse_group = QtWidgets.QActionGroup(self)
        default_act = QtWidgets.QAction('Default', mouse_group, shortcut='Ctrl+M',
                icon=qt_icon('mouse'), toolTip='Default Mouse Mode (Ctrl+M)',
                checkable=True, checked=True,
                triggered=lambda: self._set_mouse_mode(MouseOp.Normal))
        settings_bar.addAction(default_act)
        draw_act = QtWidgets.QAction('Draw', mouse_group, shortcut='Ctrl+C',
                icon=qt_icon('draw_contour'), toolTip='Draw Cone Contours (Ctrl+C)',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.DrawContour))
        settings_bar.addAction(draw_act)
        edit_act = QtWidgets.QAction('Edit', mouse_group, shortcut='Ctrl+E',
                icon=qt_icon('edit'), toolTip='Edit Cone Contours (Ctrl+E)',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.EditContour))
        settings_bar.addAction(edit_act)
        erase_multi_act = QtWidgets.QAction('Erase M', mouse_group, shortcut='Ctrl+D',
                icon=qt_icon('erase'), toolTip='Erase Cone Contours (Ctrl+D)',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.EraseMulti))
        settings_bar.addAction(erase_multi_act)
        erase_single_act = QtWidgets.QAction('Erase S', mouse_group, shortcut='Ctrl+W',
                icon=qt_icon('erase_contour'), toolTip='Erase Single Cone Contour (Ctrl+W)',
                checkable=True, checked=False,
                triggered=lambda: self._set_mouse_mode(MouseOp.EraseSingle))
        settings_bar.addAction(erase_single_act)
        settings_bar.addSeparator()
        
        self.undo_act = QtWidgets.QAction('Undo', shortcut='Ctrl+Z',
                icon=qt_icon('redo'), toolTip='Undo last operation (Ctrl+Z)',
                triggered=self._undo)
        settings_bar.addAction(self.undo_act)
        self.undo_act.setEnabled(False)
        settings_bar.addSeparator()
        #
        segmentation_setup_group = QtWidgets.QGroupBox()
        segmentation_setup_layout = QtWidgets.QGridLayout()
        self.contour_pts_checkbox = contour_pts_checkbox = QtWidgets.QCheckBox('Contour visibility')
        contour_pts_checkbox.setChecked(True)
        contour_pts_checkbox.stateChanged.connect(self._set_contour_points_visibility)
        #
        contour_size_label = QtWidgets.QLabel('Contour width: ')
        self._contour_width_input = QtWidgets.QSpinBox()
        self._contour_width_input.setMinimum(1)
        self._contour_width_input.setMaximum(100)
        self._contour_width_input.setValue(2)
        self._contour_width_input.valueChanged.connect(self._set_contour_width)
        segmentation_setup_layout.addWidget(contour_pts_checkbox, 0, 0, 1, 2)
        segmentation_setup_layout.addWidget(contour_size_label, 1, 0)
        segmentation_setup_layout.addWidget(self._contour_width_input, 1, 1)
        segmentation_setup_group.setLayout(segmentation_setup_layout)
        #
        settings_bar.addWidget(segmentation_setup_group)
        
        settings_bar.addSeparator()
        segment_button = QtWidgets.QToolButton()
        segment_button.setToolTip("Segment cones")
        segment_button.setIcon(qt_icon('segment'))
        segment_button.setText("Segment")
        segment_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
        segment_button.setShortcut('Ctrl+G')
        segment_button.clicked.connect(self._segment_cone_cells)
        settings_bar.addWidget(segment_button)
    #
    def _display_about(self):
        dlg = AboutDialog(self)
        dlg.exec()
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
    def _open_images(self):
        dlg = ao_open_dialog(self, self.hist)
        try:
            dlg.loadDir = self.loadDir.canonicalPath()
            dlg.annDir = self.saveDir.canonicalPath()
            dlg.setCheckedImages(self._input_data['image file paths'])
        except Exception:
            pass
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
    def _open_image_list(self, img_filenames, ann_filenames=None, no_ann=False):
        img_dir = None
        err_files = []
        if len(img_filenames) is not 0:
            self._initialize_input_data()
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self._progress_dlg.setWindowTitle('Open Images')
            self._progress_dlg.show()
            self._progress_dlg.set_progress(0)

            for idx, img_name in enumerate(img_filenames):
                itk_img = self._file_io.read_image(img_name)
                self._input_data['images'].append(itk_img)
                self._input_data['image file paths'].append(img_name)
                self._input_data['image names'].append(os.path.splitext(os.path.basename(img_name))[0])

                if img_dir is None:
                    img_dir = os.path.abspath(os.path.dirname(img_name))

                #extract annotation file
                history_file_name = self.hist.get_history_file(img_name)
                local_file_name = self.hist.get_local_file(img_name)

                contour_pts = []
                
                if not no_ann:
                    if not ann_filenames is None:
                        user_file_name = ann_filenames[idx]
                        # Read user-specified annotations file first
                        if user_file_name and os.path.isfile(user_file_name):
                            try:
                                contour_pts = self._file_io.read_contours(user_file_name, ignore_errors=False)
                            except Exception:
                                err_files.append(user_file_name)
                        elif os.path.isfile(history_file_name):
                            contour_pts = self._file_io.read_contours(history_file_name)
                    else:
                        # Read history first as it may contain more up to date info
                        if os.path.isfile(history_file_name):
                            contour_pts = self._file_io.read_contours(history_file_name)
                        elif os.path.isfile(local_file_name):
                            contour_pts = self._file_io.read_contours(local_file_name)
                
                self._input_data['contours'].append(contour_pts)

                self._file_io.write_contour(history_file_name, self._input_data['contours'][idx],
                                            itk_img.GetOrigin(), itk_img.GetSpacing())

                self._progress_dlg.set_progress((idx+1)/float(len(img_filenames))* 100)
                QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)

            self._update_listwidget(self._input_data['image file paths'], newlist=True)
            self._display_image(0)
            self._cur_img_id = 0
            self._file_list.setCurrentRow(self._cur_img_id)

            self._progress_dlg.set_progress(0);
            QtWidgets.QApplication.restoreOverrideCursor()
            self._progress_dlg.hide()
            #
            if img_dir is None:
                img_dir = ''
            self._status_bar.showMessage(img_dir)
        if len(err_files) > 0:
            if len(err_files) > 5:
                err_files = err_files[:4] + ['... +%d more.' % (len(err_files)-4,)]
            display_error('Failed to read the following file(s):', '\n'.join(err_files) + \
                '\n(do you attempt to open spreadsheet(s) generated by other applications?)')
    #
    def _get_data_index(self, csv_file_path, strict=True):
        fn = os.path.basename(csv_file_path)
        for id, img_name in enumerate(self._input_data['image names']):
            if strict:
                if fn == img_name + self.hist.suffix:
                    return id
            else:
                if fn.startswith(img_name):
                    return id
        return -1
    #        
    def _open_contour_list(self, csv_filenames, strict=True):
        err_files = []
        for csv_file in csv_filenames:
            id = self._get_data_index(csv_file, strict)
            if id != -1:
                try:
                    contour_pts = self._file_io.read_contours(csv_file, ignore_errors=False)
                except Exception:
                    err_files.append(os.path.basename(csv_file))
                    continue
                self._input_data['contours'][id] = contour_pts
                
                history_file_name = self.hist.get_history_file(self._input_data['image file paths'][id])
                self._file_io.write_contour(history_file_name, self._input_data['contours'][id],
                                             self._input_data['images'][id].GetOrigin(),
                                             self._input_data['images'][id].GetSpacing())
        if self._cur_img_id >= 0:
            self._display_image(self._cur_img_id)
        if len(err_files) > 0:
            if len(err_files) > 5:
                err_files = err_files[:4] + ['... +%d more.' % (len(err_files)-4,)]
            display_error('Failed to read the following file(s):', '\n'.join(err_files) + \
                '\n(do you attempt to open spreadsheet(s) generated by other applications?)')
    #
    def _show_data_locations(self):
        if self._cur_img_id < 0 or self._cur_img_id >= len(self._input_data['image file paths']):
            return
        img = self._input_data['images'][self._cur_img_id]
        img_path = os.path.abspath(self._input_data['image file paths'][self._cur_img_id])
        loc_path = self.hist.get_local_file(img_path)
        hist_path = self.hist.get_history_file(img_path, False)
        self._data_loc_dlg.setPaths(img, img_path, loc_path, hist_path)
        self._data_loc_dlg.exec()
    #
    def next_image(self):
        if self._file_list.currentRow() < self._file_list.count() - 1:
            self._file_list.setCurrentRow(self._file_list.currentRow() + 1)
    def previous_image(self):
        if self._file_list.currentRow() > 0:
            self._file_list.setCurrentRow(self._file_list.currentRow() - 1)
    def _file_list_row_changed(self, newrow):
        self._cur_img_id = newrow
        self._display_image(self._cur_img_id)
    #
    def _display_image(self, idx):
        self.clear_undo()
        self._image_view.initialization()
        if idx < 0 or idx >= len(self._input_data['images']):
            return
        self._image_view.set_image(self._input_data['images'][idx])
        self._image_view.set_contours(self._input_data['contours'][idx])
        self.contour_pts_checkbox.setChecked(True)
        self._image_view.reset_view(True)

    def _segment_cone_cells(self):
        #res = AOSettingsDialog.display_warning('Detecting cone cells', 'Do you really want to detect cells?')
        self._segmentation_para_dlg.SetImageList(self._input_data['image names'])
        c_rows = [row for row, ann in enumerate(self._input_data['contours']) if len(ann) == 0]
        self._segmentation_para_dlg.SetCheckedRows(c_rows)
        self._segmentation_para_dlg.SetHighlightedRow(self._cur_img_id)
        res = self._segmentation_para_dlg.exec()
        if res == QtWidgets.QDialog.Rejected:
            return
        
        c_rows = self._segmentation_para_dlg.checkedRows()
        self.saveState()
        if len(c_rows) == 0:
            display_error('Input error:', 'Nothing was checked.')
            return

        cur_segmentation_model = self._segmentation_models[self._segmentation_para_dlg.segmentation_method]
        if cur_segmentation_model['contours'] == None or cur_segmentation_model['regions'] == None\
                or cur_segmentation_model['centroids'] == None or len(self._input_data['images']) == 0:
            display_error('Input errors:', 'There are either no segmentation models or input data!')
            return

        self._image_view.cancel_editing()
        self.clear_undo()
        self.contour_pts_checkbox.setChecked(True)

        window_title = cfg.APP_NAME + ': ' + self._segmentation_para_dlg.segmentation_method
        self.setWindowTitle(window_title)

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        self._progress_dlg.setWindowTitle('Segment cones ...')
        self._progress_dlg.show()
        self._progress_dlg.set_progress(0)

        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
        for i, row in enumerate(c_rows):
            contours = self._input_data['contours'][row]
            img = self._input_data['images'][row]
            
            # res_img = self._detection.detect_cones(img)
            # plt.imshow(res_img, cmap='gray')
            # plt.show()
            self._input_data['contours'][row] = self._segmentation.segment_cones(
                    self._segmentation_models[\
                        self._segmentation_para_dlg.segmentation_method], img,
                    self._segmentation_para_dlg.get_image_fov(),
                    self._segmentation_para_dlg.get_iteration_number(),
                    self._segmentation_para_dlg.get_cell_contour_length())
            self.SaveHistory(row)

            self._progress_dlg.set_progress((i+1) / float(len(c_rows))* 100)
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)

        if not self._cur_img_id in c_rows:
            self._file_list.setCurrentRow(c_rows[0])
        else:
            self._image_view.set_contours(self._input_data['contours'][self._cur_img_id])
            self._image_view.reset_view()

        self._progress_dlg.set_progress(0);
        QtWidgets.QApplication.restoreOverrideCursor()
        self._progress_dlg.hide()
    #
    def SaveHistory(self, i=None):
        if i is None:
            i = self._cur_img_id
        if i < 0:
            return
        
        history_file_name = self.hist.get_history_file(self._input_data['image file paths'][i])
        contours = self._input_data['contours'][i]
        img = self._input_data['images'][i]
        self._file_io.write_contour(history_file_name, contours, img.GetOrigin(), img.GetSpacing())
    #
    def _undo(self, e):
        self._image_view.cancel_editing()
        self.contour_pts_checkbox.setChecked(True)
        self.do_undo()
    #
    def do_undo(self):
        if len(self._undo_buf) == 0:
            return
        if self._cur_img_id == -1:
            self.clear_undo()
            return
        contours = self._input_data['contours'][self._cur_img_id]
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
            if e.last: break
        if modified:
            self._image_view.set_contours(contours)
            self.SaveHistory()
        self.undo_act.setEnabled(len(self._undo_buf) > 0)
    #
    def push_undo(self, op, data, last=True):
        self._undo_buf.append(UndoEntry(op, last, data))
        self.undo_act.setEnabled(True)
    #
    def clear_undo(self):
        self._undo_buf.clear()
        self.undo_act.setEnabled(False)
    #
    def AddContour(self, contour_pts):
        if self._cur_img_id == -1:
            return
        contours = self._input_data['contours'][self._cur_img_id]
        c = optimizeContour(contour_pts)
        self.push_undo(UndoOp.Added, c)
        contours.append(c)
        self._image_view.set_contours(contours)
        self.SaveHistory()
    #
    def RemoveContoursInside(self, contour_pts):
        if self._cur_img_id == -1:
            return
        contour_pts = optimizeContour(contour_pts)
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        in_contours = self._input_data['contours'][self._cur_img_id]
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
            self._input_data['contours'][self._cur_img_id] = out_contours
            self._image_view.set_contours(out_contours)
            self.SaveHistory()
    #
    def RemoveContourAt(self, pt):
        if self._cur_img_id == -1:
            return
        in_contours = self._input_data['contours'][self._cur_img_id]
        out_contours = []
        last = True
        for c in in_contours:
            if isPointInside(pt, c):
                self.push_undo(UndoOp.Removed, c, last)
                last = False
            else:
                out_contours.append(c)
        if not last:
            self._input_data['contours'][self._cur_img_id] = out_contours
            self._image_view.set_contours(out_contours)
            self.SaveHistory()
    #
    def EditContourAt(self, pt):
        if self._cur_img_id == -1:
            return
        contours = self._input_data['contours'][self._cur_img_id]
        self._edited_contour_idx = idx = findContour(pt, contours)
        if idx < 0:
            idx = None
        else:
            contours[idx] = optimizeContour(contours[idx])
        self._image_view.set_contours(contours, idx)
    #
    def UpdateContour(self, idx, contour_pts):
        if self._cur_img_id == -1:
            return
        contours = self._input_data['contours'][self._cur_img_id]
        if contourChanged(contours[idx], contour_pts):
            self.push_undo(UndoOp.Added, contour_pts)
            self.push_undo(UndoOp.Removed, contours[idx], False)
            contours[idx] = contour_pts
            self.SaveHistory()
    #
    def _save_data(self):
        if len(self._input_data['images']) == 0: return
        try:
            try:
                sdir = self.saveDir.canonicalPath()
            except Exception:
                sdir = QtCore.QDir.homePath()
            dir_name = QtWidgets.QFileDialog.getExistingDirectory(self, \
                    'Select saving directory', sdir)
            if dir_name:
                cnt = self._file_io.write_contours(dir_name, self._input_data, suffix=self.hist.suffix)
                self._status_bar.showMessage('%d contour file(s) saved to %s' % (cnt, dir_name))
                self._update_listwidget(self._input_data['image file paths'], newlist=False)
                self.saveDir = QtCore.QDir(dir_name)
                self.saveState()
        except Exception as ex:
            display_error('Error saving data', ex)

    def _quit(self, event):
        self.close()

    def _set_contour_points_visibility(self, state):
        self._image_view.contour_visibility = state
        self._image_view.reset_view()
        self.toggle_visibility.setChecked(state)
    #
    def _toggle_visibility(self):
        state = 0 if self._image_view.contour_visibility else 1
        self.contour_pts_checkbox.setChecked(state)
    #
    def _toggle_interpolation(self):
        self._image_view.interpolation = self.toggle_interpolation.isChecked()
        self._image_view.reset_view()
        self.saveState()
    #
    def _reset_brightness_contrast(self):
        self._image_view.reset_color()
        self._image_view.reset_view(True)
    #
    def _set_contour_width(self):
        self._image_view.set_contour_width(self._contour_width_input.value())
        self._image_view.reset_view()
        self.saveState()

    def _show_settigns_dialog(self):
        self._settings.show()

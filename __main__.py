import multiprocessing as mp
import os
import sys


def main():
    # Keep application imports after freeze_support(). A child process created by
    # a frozen executable must not initialize Qt and open another main window.
    from PyQt5 import QtWidgets
    import AOConfig as cfg

    cfg.APP_NAME = 'Cone Segmentation (ML)'
    cfg.APP_VERSION = '1.3.2 (2026-05-12)'

    try:
        cdir = os.path.dirname(__file__)
        os.chdir(cdir)
        # print(cdir)
    except Exception:
        pass
    import AOMainWindow
    app = QtWidgets.QApplication([])
    app.setApplicationName(cfg.APP_NAME)
    window = AOMainWindow.MainWindow()
    window.show()
    if len(sys.argv) > 1:
        flist = cfg.InputList(sys.argv[1:])
        img_filenames = flist.get_files(('.tif', '.tiff'))
        if len(img_filenames) > 0:
            window._open_image_list(img_filenames, save_state=True)
            csv_filenames = flist.get_files('.csv')
            if len(csv_filenames) > 0:
                window._open_contour_list(csv_filenames)
    return app.exec_()


if __name__ == '__main__':
    mp.freeze_support()
    sys.exit(main())

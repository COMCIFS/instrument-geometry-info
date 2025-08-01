import json
import os.path
import re
import sys
from socket import socketpair, SHUT_RDWR

import requests
from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import Qt, QProcess
from PySide6.QtWidgets import QFileDialog

from imgcif_ui import Ui_MainWindow
from multi_archive_dlg_ui import Ui_MultiArchiveDialog
from archive_download_ui import Ui_ArchiveDownload

class BackendManager(QtCore.QObject):
    state_update = QtCore.Signal(dict)

    def __init__(self, parent):
        super().__init__(parent)

        self.read_buffer = []
        self.socket, sock_child = socketpair()
        self.socket_notifier = QtCore.QSocketNotifier(
            self.socket.fileno(), QtCore.QSocketNotifier.Type.Read, self
        )
        self.socket_notifier.activated.connect(self.read_ready)

        sock_child.set_inheritable(True)

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.ForwardedChannels)
        self.process.started.connect(self.process_started)
        self.process.finished.connect(self.process_exited)
        self.process.start(sys.executable, ['imgcif_backend.py', str(sock_child.fileno())])

        sock_child.close()

    def process_started(self):
        self.socket_notifier.setEnabled(True)

    def process_exited(self):
        self.socket_notifier.setEnabled(False)
        self.socket_notifier.deleteLater()
        self.socket.close()

    def stop(self):
        self.socket.shutdown(SHUT_RDWR)
        self.process.waitForFinished(1000)

    def send_message(self, command, opts=None):
        b = json.dumps([command, (opts or {})], indent=None).encode('utf-8') + b'\n'
        self.socket.sendall(b)

    def read_ready(self, _sock, _type):
        b = self.socket.recv(4096)
        while b'\n' in b:
            line_end, _, b = b.partition(b'\n')
            line = b''.join(self.read_buffer + [line_end])
            category, details = json.loads(line)
            if category == 'state':
                self.state_update.emit(details)
            self.read_buffer = []
        self.read_buffer.append(b)


class QLineEditDebounce(QtCore.QObject):
    changed = QtCore.Signal(str)

    def __init__(self, lineedit: QtWidgets.QLineEdit, delay=500):
        super().__init__(lineedit)
        self.lineedit = lineedit
        self.text_when_emitted = ''
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(delay)
        self.timer.timeout.connect(self.fire)
        lineedit.textChanged.connect(self.text_changed)
        lineedit.editingFinished.connect(self.editing_finished)

    def fire(self):
        self.changed.emit(self.lineedit.text())

    def text_changed(self):
        self.timer.start()

    def editing_finished(self):
        if self.timer.isActive():
            self.timer.stop()
            self.fire()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.preview.document().setDefaultFont(QtGui.QFont("monospace", 10))

        # Hook up the UI to the logic
        self.ui.files_btn.clicked.connect(self.add_data_files)
        self.ui.folder_btn.clicked.connect(self.add_data_folder)
        self.ui.expt_file_btn.clicked.connect(self.set_expt_file)
        self.ui.files_reset_btn.clicked.connect(self.reset_files)

        self.ui.archive_folder_btn.clicked.connect(self.pick_archive_dir)
        self.ui.download_files_rb.toggled.connect(self.set_download_details)
        self.ui.file_url.editingFinished.connect(self.set_download_details)
        AsyncValidator(self.ui.archive_url).changed_valid.connect(self.set_download_details)
        QLineEditDebounce(self.ui.archive_folder_path).changed.connect(self.set_download_details)
        self.ui.archive_folder_path.editingFinished.connect(self.set_download_details)
        self.ui.archive_format.currentTextChanged.connect(self.set_download_details)

        self.multi_archive_dialog = MultiArchiveDialog(self)
        self.ui.multi_archives_btn.clicked.connect(self.multi_archive_dialog.show)
        self.multi_archive_dialog.accepted.connect(self.configure_multi_archives)
        self.ui.save_btn.clicked.connect(self.save_cif)

        # Where fields can be filled manually or automatically, automatic input
        # shouldn't replace manual
        self.doi_entered = False
        self.ui.doi.textEdited.connect(self.set_doi)
        self.file_format_chosen = False
        self.ui.file_format.textActivated.connect(self.set_file_format)

        # Start the backend
        self.backend = BackendManager(self)
        self.backend.state_update.connect(self.state_update)
        self.backend.state_update.connect(self.multi_archive_dialog.state_update)

        adeqt_shortcut = QtGui.QShortcut(QtGui.QKeySequence(Qt.Key.Key_F12), self)
        adeqt_shortcut.activated.connect(self.show_adeqt)

    def closeEvent(self, event):
        self.backend.stop()
        event.accept()

    def add_data_files(self):
        paths = QFileDialog.getOpenFileNames(self, "Select data files")
        if paths:
            self.backend.send_message("add_paths", {"paths": paths})

    def add_data_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select data folder")
        if path:
            self.backend.send_message("add_paths", {"paths": [path]})

    def set_expt_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select DIALS experiment file", filter="DIALS experiment (*.expt)"
        )
        if path:
            self.backend.send_message("set_expt", {"path": path})

    def reset_files(self):
        self.backend.send_message("reset")

    def pick_archive_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select unpacked archive folder")
        if path:
            self.ui.archive_folder_path.setText(path)
            self.set_download_details()

    def configure_multi_archives(self):
        """Called when multi-archive dialog accepted"""
        self.set_download_details()

    def set_download_details(self):
        if self.ui.download_files_rb.isChecked():
            self.backend.send_message('set_download_files', {
                'url': self.ui.file_url.text()
            })
        elif self.ui.download_archive_rb.isChecked():
            self.backend.send_message('set_download_archives', {'details': [{
                'url': self.ui.archive_url.text(),
                'dir': self.ui.archive_folder_path.text(),
                'archive_type': self.ui.archive_format.currentText() or None,
            }]})
        else:  # download_multi_archives_rb
            self.backend.send_message('set_download_archives', {
                'details': self.multi_archive_dialog.get_download_details()
            })

    def set_doi(self, s):
        self.doi_entered = bool(s)
        self.backend.send_message('set_doi', {'doi': s})

    def set_file_format(self, s):
        self.file_format_chosen = bool(s)
        self.backend.send_message('set_file_type', {'file_type': s})

    def state_update(self, state):
        """New info from the backend"""
        if empty := state['n_expts'] == 0:
            descr = "No files selected"
        else:
            descr = f"{state['n_frames']} frames in {state['n_expts']} experiments"
        self.ui.files_status.setText(descr)
        self.ui.files_reset_btn.setEnabled(not empty)
        self.ui.expt_file_btn.setEnabled(empty)
        if not self.file_format_chosen:
            self.ui.file_format.setCurrentText(state['file_type'])
        if not self.doi_entered:
            self.ui.doi.setText(state['doi'])

        self.set_preview(state['cif_preview'] or '')

    def set_preview(self, contents):
        # Attempt to restore the scroll position, should work for small changes
        sb = self.ui.preview.verticalScrollBar()
        sb_min, sb_max = sb.minimum(), sb.maximum()
        sb_fract = (sb.value() - sb_min) / ((sb_max - sb_min) or 1)  # Avoid divide-by-zero
        self.ui.preview.setPlainText(contents)
        sb.setValue(int(sb_fract * (sb.maximum() - sb.minimum()) + sb.minimum()))

    def save_cif(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save CIF output",
                                              filter="CIF files (*.cif)")
        if path:
            if os.path.splitext(path)[1] == '':
                path += '.cif'
            self.backend.send_message("save", {'path': path})

    adeqt_window = None

    def show_adeqt(self):
        from adeqt import AdeqtWindow
        if self.adeqt_window is None:
            self.adeqt_window = AdeqtWindow({'window': self}, parent=self)
        self.adeqt_window.show()


class ArchiveDownloadGroup(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_ArchiveDownload()
        self.ui.setupUi(self)


class MultiArchiveDialog(QtWidgets.QDialog):
    def __init__(self, parent: MainWindow):
        super().__init__(parent)
        self.ui = Ui_MultiArchiveDialog()
        self.ui.setupUi(self)

    def _groupboxes(self):
        return [c for c in self.ui.scrollAreaWidgetContents.children()
                if isinstance(c, ArchiveDownloadGroup)]

    def state_update(self, state):
        gbs = self._groupboxes()

        # Remove any excess groupboxes
        for _ in range(len(gbs) - state['n_expts']):
            gbs.pop(-1).deleteLater()

        # Add new groupboxes as needed
        layout = self.ui.scrollAreaWidgetContents.layout()
        for i in range(state['n_expts'] - len(gbs)):
            gb = ArchiveDownloadGroup(self.ui.scrollAreaWidgetContents)
            layout.addWidget(gb)
            if len(gbs) + i < 2:
                gb.ui.archive_url.textChanged.connect(self.extrapolate_urls)
                gb.ui.archive_folder_path.textChanged.connect(self.extrapolate_folders)

        # Set titles from experiment summaries
        gbs = self._groupboxes()  # Refresh the list with newly added ones
        for i, (gb, descr) in enumerate(zip(gbs, state['expt_summaries'])):
            gb.setTitle(f"{i+1}: {descr}")

    def extrapolate_urls(self):
        gbs = self._groupboxes()
        if len(gbs) < 3:
            return

        matched0 = re.split(r"(\d+)", gbs[0].ui.archive_url.text())
        matched1 = re.split(r"(\d+)", gbs[1].ui.archive_url.text())
        if len(matched0) != len(matched1):
            return

        if len(diffs := [
            i for i, (p0, p1) in enumerate(zip(matched0, matched1)) if p0 != p1
        ]) != 1:
            return  # No difference, or >1 piece differs
        if (diff_ix := diffs[0]) % 2 == 0:
            return  # The difference is in a non-numeric part

        width = len(matched0[diff_ix])
        n0 = int(matched0[diff_ix])  # First number in sequence
        if int(matched1[diff_ix]) != n0 + 1:
            return  # Not increasing by 1

        for i, gb in enumerate(gbs[2:], start=2):
            if gb.ui.archive_url.text() == '':
                pieces = matched0.copy()
                pieces[diff_ix] = f"{n0 + i:0{width}}"
                gb.ui.archive_url.setText(''.join(pieces))

    def extrapolate_folders(self):
        ...

    def get_download_details(self) -> list[dict]:
        return [{
            'url': gb.ui.archive_url.text(),
            'dir': gb.ui.archive_folder_path.text(),
            'archive_type': gb.ui.archive_format.currentText() or None,
        } for gb in self._groupboxes()]


class AsyncValidator(QtCore.QObject):
    changed_valid = QtCore.Signal(str)

    def __init__(self, lineedit: QtWidgets.QLineEdit, delay=500):
        super().__init__(lineedit)
        self.lineedit = lineedit
        self.lineedit.textChanged.connect(self.reset_style)
        debounce = QLineEditDebounce(self.lineedit, delay=delay)
        debounce.changed.connect(self.check)

    def reset_style(self):
        self.lineedit.setStyleSheet("")

    def check(self):
        if not (t := self.lineedit.text()):
            return  # Field emptied, leave the default style
        thread = UrlCheckerThread(self.lineedit.text(), self)
        thread.check_result.connect(self.checked)
        thread.start()

    def checked(self, url, status_code):
        if url != self.lineedit.text():
            return  # It was edited while we were checking
        if status_code < 400:
            self.lineedit.setStyleSheet("QLineEdit {background: rgb(180, 255, 180);}")
            self.changed_valid.emit(url)
        else:
            self.lineedit.setStyleSheet("QLineEdit {background: rgb(255, 128, 128);}")

class UrlCheckerThread(QtCore.QThread):
    # url, status code
    check_result = QtCore.Signal(str, int)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            resp = requests.get(self.url, stream=True)
            resp.close()  # No need to read content
        except Exception:
            self.check_result.emit(self.url, 600)  # E.g. error parsing the URL
        else:
            self.check_result.emit(self.url, resp.status_code)


if __name__=="__main__":
    qapp = QtWidgets.QApplication([])
    window = MainWindow()
    window.show()
    qapp.exec()

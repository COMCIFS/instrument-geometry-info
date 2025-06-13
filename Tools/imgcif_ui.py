# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'imgcif_maker.ui'
##
## Created by: Qt User Interface Compiler version 6.9.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QComboBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMenuBar, QPlainTextEdit, QPushButton, QRadioButton,
    QSizePolicy, QSpacerItem, QSplitter, QStatusBar,
    QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1148, 666)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.horizontalLayout_7 = QHBoxLayout(self.centralwidget)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.splitter = QSplitter(self.centralwidget)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.verticalLayoutWidget = QWidget(self.splitter)
        self.verticalLayoutWidget.setObjectName(u"verticalLayoutWidget")
        self.verticalLayout_5 = QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.files_group = QGroupBox(self.verticalLayoutWidget)
        self.files_group.setObjectName(u"files_group")
        self.verticalLayout_3 = QVBoxLayout(self.files_group)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.files_btn = QPushButton(self.files_group)
        self.files_btn.setObjectName(u"files_btn")

        self.horizontalLayout_2.addWidget(self.files_btn)

        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer_3)

        self.folder_btn = QPushButton(self.files_group)
        self.folder_btn.setObjectName(u"folder_btn")

        self.horizontalLayout_2.addWidget(self.folder_btn)

        self.horizontalSpacer_2 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer_2)

        self.expt_file_btn = QPushButton(self.files_group)
        self.expt_file_btn.setObjectName(u"expt_file_btn")

        self.horizontalLayout_2.addWidget(self.expt_file_btn)


        self.verticalLayout_3.addLayout(self.horizontalLayout_2)

        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.files_status = QLabel(self.files_group)
        self.files_status.setObjectName(u"files_status")

        self.horizontalLayout_5.addWidget(self.files_status)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_5.addItem(self.horizontalSpacer)

        self.files_reset_btn = QPushButton(self.files_group)
        self.files_reset_btn.setObjectName(u"files_reset_btn")
        self.files_reset_btn.setEnabled(False)

        self.horizontalLayout_5.addWidget(self.files_reset_btn)


        self.verticalLayout_3.addLayout(self.horizontalLayout_5)

        self.download_group = QGroupBox(self.files_group)
        self.download_group.setObjectName(u"download_group")
        self.verticalLayout_4 = QVBoxLayout(self.download_group)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.download_files_rb = QRadioButton(self.download_group)
        self.download_files_rb.setObjectName(u"download_files_rb")
        self.download_files_rb.setChecked(True)

        self.verticalLayout_4.addWidget(self.download_files_rb)

        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(20, -1, -1, -1)
        self.label = QLabel(self.download_group)
        self.label.setObjectName(u"label")

        self.horizontalLayout_3.addWidget(self.label)

        self.file_url = QLineEdit(self.download_group)
        self.file_url.setObjectName(u"file_url")

        self.horizontalLayout_3.addWidget(self.file_url)


        self.verticalLayout_4.addLayout(self.horizontalLayout_3)

        self.download_archive_rb = QRadioButton(self.download_group)
        self.download_archive_rb.setObjectName(u"download_archive_rb")

        self.verticalLayout_4.addWidget(self.download_archive_rb)

        self.verticalLayout_6 = QVBoxLayout()
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.verticalLayout_6.setContentsMargins(20, -1, -1, -1)
        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.label_2 = QLabel(self.download_group)
        self.label_2.setObjectName(u"label_2")

        self.horizontalLayout_4.addWidget(self.label_2)

        self.archive_url = QLineEdit(self.download_group)
        self.archive_url.setObjectName(u"archive_url")
        self.archive_url.setEnabled(False)

        self.horizontalLayout_4.addWidget(self.archive_url)


        self.verticalLayout_6.addLayout(self.horizontalLayout_4)

        self.horizontalLayout_6 = QHBoxLayout()
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.label_3 = QLabel(self.download_group)
        self.label_3.setObjectName(u"label_3")

        self.horizontalLayout_6.addWidget(self.label_3)

        self.archive_folder_path = QLineEdit(self.download_group)
        self.archive_folder_path.setObjectName(u"archive_folder_path")
        self.archive_folder_path.setEnabled(False)

        self.horizontalLayout_6.addWidget(self.archive_folder_path)

        self.archive_folder_btn = QPushButton(self.download_group)
        self.archive_folder_btn.setObjectName(u"archive_folder_btn")
        self.archive_folder_btn.setEnabled(False)

        self.horizontalLayout_6.addWidget(self.archive_folder_btn)


        self.verticalLayout_6.addLayout(self.horizontalLayout_6)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.label_7 = QLabel(self.download_group)
        self.label_7.setObjectName(u"label_7")

        self.horizontalLayout.addWidget(self.label_7)

        self.archive_format = QComboBox(self.download_group)
        self.archive_format.addItem(u"")
        self.archive_format.addItem(u"ZIP")
        self.archive_format.addItem(u"TBZ")
        self.archive_format.addItem(u"TGZ")
        self.archive_format.addItem(u"TAR")
        self.archive_format.setObjectName(u"archive_format")
        self.archive_format.setEnabled(False)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.archive_format.sizePolicy().hasHeightForWidth())
        self.archive_format.setSizePolicy(sizePolicy)

        self.horizontalLayout.addWidget(self.archive_format)


        self.verticalLayout_6.addLayout(self.horizontalLayout)


        self.verticalLayout_4.addLayout(self.verticalLayout_6)

        self.horizontalLayout_8 = QHBoxLayout()
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.download_multi_archives_rb = QRadioButton(self.download_group)
        self.download_multi_archives_rb.setObjectName(u"download_multi_archives_rb")

        self.horizontalLayout_8.addWidget(self.download_multi_archives_rb)

        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_8.addItem(self.horizontalSpacer_4)

        self.multi_archives_btn = QPushButton(self.download_group)
        self.multi_archives_btn.setObjectName(u"multi_archives_btn")
        self.multi_archives_btn.setEnabled(False)

        self.horizontalLayout_8.addWidget(self.multi_archives_btn)


        self.verticalLayout_4.addLayout(self.horizontalLayout_8)


        self.verticalLayout_3.addWidget(self.download_group)


        self.verticalLayout_5.addWidget(self.files_group)

        self.groupBox_2 = QGroupBox(self.verticalLayoutWidget)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.formLayout_2 = QFormLayout(self.groupBox_2)
        self.formLayout_2.setObjectName(u"formLayout_2")
        self.label_4 = QLabel(self.groupBox_2)
        self.label_4.setObjectName(u"label_4")

        self.formLayout_2.setWidget(0, QFormLayout.ItemRole.LabelRole, self.label_4)

        self.doi = QLineEdit(self.groupBox_2)
        self.doi.setObjectName(u"doi")
        self.doi.setClearButtonEnabled(True)

        self.formLayout_2.setWidget(0, QFormLayout.ItemRole.FieldRole, self.doi)


        self.verticalLayout_5.addWidget(self.groupBox_2)

        self.extra_params_group = QGroupBox(self.verticalLayoutWidget)
        self.extra_params_group.setObjectName(u"extra_params_group")
        self.formLayout = QFormLayout(self.extra_params_group)
        self.formLayout.setObjectName(u"formLayout")
        self.label_5 = QLabel(self.extra_params_group)
        self.label_5.setObjectName(u"label_5")

        self.formLayout.setWidget(0, QFormLayout.ItemRole.LabelRole, self.label_5)

        self.label_6 = QLabel(self.extra_params_group)
        self.label_6.setObjectName(u"label_6")

        self.formLayout.setWidget(1, QFormLayout.ItemRole.LabelRole, self.label_6)

        self.file_format = QComboBox(self.extra_params_group)
        self.file_format.addItem(u"")
        self.file_format.addItem(u"CBF")
        self.file_format.addItem(u"HDF5")
        self.file_format.addItem(u"TIFF")
        self.file_format.addItem(u"SMV")
        self.file_format.setObjectName(u"file_format")

        self.formLayout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.file_format)

        self.overhead_value = QLineEdit(self.extra_params_group)
        self.overhead_value.setObjectName(u"overhead_value")
        self.overhead_value.setClearButtonEnabled(True)

        self.formLayout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.overhead_value)


        self.verticalLayout_5.addWidget(self.extra_params_group)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout_5.addItem(self.verticalSpacer)

        self.splitter.addWidget(self.verticalLayoutWidget)
        self.groupBox = QGroupBox(self.splitter)
        self.groupBox.setObjectName(u"groupBox")
        self.verticalLayout_2 = QVBoxLayout(self.groupBox)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.preview = QPlainTextEdit(self.groupBox)
        self.preview.setObjectName(u"preview")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.preview.sizePolicy().hasHeightForWidth())
        self.preview.setSizePolicy(sizePolicy1)
        self.preview.setMinimumSize(QSize(500, 0))
        self.preview.setReadOnly(True)

        self.verticalLayout_2.addWidget(self.preview)

        self.splitter.addWidget(self.groupBox)

        self.horizontalLayout_7.addWidget(self.splitter)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1148, 24))
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)
#if QT_CONFIG(shortcut)
        self.label.setBuddy(self.file_url)
        self.label_2.setBuddy(self.archive_url)
        self.label_3.setBuddy(self.archive_folder_path)
        self.label_7.setBuddy(self.archive_format)
        self.label_4.setBuddy(self.doi)
        self.label_5.setBuddy(self.overhead_value)
        self.label_6.setBuddy(self.file_format)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(MainWindow)
        self.download_files_rb.toggled.connect(self.file_url.setEnabled)
        self.download_archive_rb.toggled.connect(self.archive_url.setEnabled)
        self.download_archive_rb.toggled.connect(self.archive_folder_path.setEnabled)
        self.download_archive_rb.toggled.connect(self.archive_folder_btn.setEnabled)
        self.download_archive_rb.toggled.connect(self.archive_format.setEnabled)
        self.download_multi_archives_rb.toggled.connect(self.multi_archives_btn.setEnabled)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.files_group.setTitle(QCoreApplication.translate("MainWindow", u"Data files", None))
        self.files_btn.setText(QCoreApplication.translate("MainWindow", u"Add data files", None))
        self.folder_btn.setText(QCoreApplication.translate("MainWindow", u"Add data folder", None))
        self.expt_file_btn.setText(QCoreApplication.translate("MainWindow", u"Select DIALS .expt file", None))
        self.files_status.setText(QCoreApplication.translate("MainWindow", u"No files selected", None))
        self.files_reset_btn.setText(QCoreApplication.translate("MainWindow", u"Reset", None))
        self.download_group.setTitle(QCoreApplication.translate("MainWindow", u"Download source", None))
        self.download_files_rb.setText(QCoreApplication.translate("MainWindow", u"Download individual files", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"First file URL", None))
        self.download_archive_rb.setText(QCoreApplication.translate("MainWindow", u"Download one archive", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"Archive URL", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"Unpacked folder", None))
        self.archive_folder_btn.setText(QCoreApplication.translate("MainWindow", u"Select", None))
        self.label_7.setText(QCoreApplication.translate("MainWindow", u"Archive format", None))

        self.download_multi_archives_rb.setText(QCoreApplication.translate("MainWindow", u"Download per-scan archives", None))
        self.multi_archives_btn.setText(QCoreApplication.translate("MainWindow", u"Configure", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("MainWindow", u"Metadata (optional)", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"Data DOI", None))
        self.extra_params_group.setTitle(QCoreApplication.translate("MainWindow", u"Extra parameters", None))
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"Overload value", None))
        self.label_6.setText(QCoreApplication.translate("MainWindow", u"File format", None))

        self.groupBox.setTitle(QCoreApplication.translate("MainWindow", u"Preview", None))
        self.preview.setPlaceholderText(QCoreApplication.translate("MainWindow", u"CIF preview will appear here", None))
    # retranslateUi


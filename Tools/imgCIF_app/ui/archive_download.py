# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'archive_download.ui'
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
from PySide6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget)

class Ui_ArchiveDownload(object):
    def setupUi(self, ArchiveDownload):
        if not ArchiveDownload.objectName():
            ArchiveDownload.setObjectName(u"ArchiveDownload")
        ArchiveDownload.resize(400, 117)
        self.verticalLayout = QVBoxLayout(ArchiveDownload)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.horizontalLayout_4 = QHBoxLayout()
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.label_2 = QLabel(ArchiveDownload)
        self.label_2.setObjectName(u"label_2")

        self.horizontalLayout_4.addWidget(self.label_2)

        self.archive_url = QLineEdit(ArchiveDownload)
        self.archive_url.setObjectName(u"archive_url")

        self.horizontalLayout_4.addWidget(self.archive_url)


        self.verticalLayout.addLayout(self.horizontalLayout_4)

        self.horizontalLayout_6 = QHBoxLayout()
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.label_3 = QLabel(ArchiveDownload)
        self.label_3.setObjectName(u"label_3")

        self.horizontalLayout_6.addWidget(self.label_3)

        self.archive_folder_path = QLineEdit(ArchiveDownload)
        self.archive_folder_path.setObjectName(u"archive_folder_path")

        self.horizontalLayout_6.addWidget(self.archive_folder_path)

        self.archive_folder_btn = QPushButton(ArchiveDownload)
        self.archive_folder_btn.setObjectName(u"archive_folder_btn")

        self.horizontalLayout_6.addWidget(self.archive_folder_btn)


        self.verticalLayout.addLayout(self.horizontalLayout_6)

        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.label_7 = QLabel(ArchiveDownload)
        self.label_7.setObjectName(u"label_7")

        self.horizontalLayout.addWidget(self.label_7)

        self.archive_format = QComboBox(ArchiveDownload)
        self.archive_format.addItem(u"")
        self.archive_format.addItem(u"ZIP")
        self.archive_format.addItem(u"TBZ")
        self.archive_format.addItem(u"TGZ")
        self.archive_format.addItem(u"TAR")
        self.archive_format.setObjectName(u"archive_format")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.archive_format.sizePolicy().hasHeightForWidth())
        self.archive_format.setSizePolicy(sizePolicy)

        self.horizontalLayout.addWidget(self.archive_format)


        self.verticalLayout.addLayout(self.horizontalLayout)

#if QT_CONFIG(shortcut)
        self.label_2.setBuddy(self.archive_url)
        self.label_3.setBuddy(self.archive_folder_path)
        self.label_7.setBuddy(self.archive_format)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(ArchiveDownload)

        QMetaObject.connectSlotsByName(ArchiveDownload)
    # setupUi

    def retranslateUi(self, ArchiveDownload):
        ArchiveDownload.setWindowTitle(QCoreApplication.translate("ArchiveDownload", u"Form", None))
        self.label_2.setText(QCoreApplication.translate("ArchiveDownload", u"Archive URL", None))
        self.label_3.setText(QCoreApplication.translate("ArchiveDownload", u"Unpacked folder", None))
        self.archive_folder_btn.setText(QCoreApplication.translate("ArchiveDownload", u"Select", None))
        self.label_7.setText(QCoreApplication.translate("ArchiveDownload", u"Archive format", None))

    # retranslateUi


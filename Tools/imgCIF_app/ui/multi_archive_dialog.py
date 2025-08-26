# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'multi_archive_dialog.ui'
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QDialogButtonBox,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

class Ui_MultiArchiveDialog(object):
    def setupUi(self, MultiArchiveDialog):
        if not MultiArchiveDialog.objectName():
            MultiArchiveDialog.setObjectName(u"MultiArchiveDialog")
        MultiArchiveDialog.resize(545, 433)
        self.verticalLayout = QVBoxLayout(MultiArchiveDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.scrollArea = QScrollArea(MultiArchiveDialog)
        self.scrollArea.setObjectName(u"scrollArea")
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName(u"scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 525, 380))
        self.verticalLayout_2 = QVBoxLayout(self.scrollAreaWidgetContents)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.verticalLayout.addWidget(self.scrollArea)

        self.buttonBox = QDialogButtonBox(MultiArchiveDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.verticalLayout.addWidget(self.buttonBox)


        self.retranslateUi(MultiArchiveDialog)
        self.buttonBox.accepted.connect(MultiArchiveDialog.accept)
        self.buttonBox.rejected.connect(MultiArchiveDialog.reject)

        QMetaObject.connectSlotsByName(MultiArchiveDialog)
    # setupUi

    def retranslateUi(self, MultiArchiveDialog):
        MultiArchiveDialog.setWindowTitle(QCoreApplication.translate("MultiArchiveDialog", u"Dialog", None))
    # retranslateUi


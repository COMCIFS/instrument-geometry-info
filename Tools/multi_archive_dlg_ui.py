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
    QHeaderView, QSizePolicy, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)

class Ui_MultiArchiveDialog(object):
    def setupUi(self, MultiArchiveDialog):
        if not MultiArchiveDialog.objectName():
            MultiArchiveDialog.setObjectName(u"MultiArchiveDialog")
        MultiArchiveDialog.resize(400, 300)
        self.verticalLayout = QVBoxLayout(MultiArchiveDialog)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.table = QTableWidget(MultiArchiveDialog)
        if (self.table.columnCount() < 4):
            self.table.setColumnCount(4)
        __qtablewidgetitem = QTableWidgetItem()
        self.table.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.table.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.table.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.table.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        self.table.setObjectName(u"table")
        self.table.setRowCount(0)

        self.verticalLayout.addWidget(self.table)

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
        ___qtablewidgetitem = self.table.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("MultiArchiveDialog", u"Scan", None));
        ___qtablewidgetitem1 = self.table.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("MultiArchiveDialog", u"Archive URL", None));
        ___qtablewidgetitem2 = self.table.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("MultiArchiveDialog", u"Unpacked folder", None));
        ___qtablewidgetitem3 = self.table.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("MultiArchiveDialog", u"Archive format", None));
    # retranslateUi


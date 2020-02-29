import sys
import os
import re
from time import time

from PyQt5 import QtCore, QtWidgets, uic, QtGui

from interpreter import Interpreter

class PyRunner(QtWidgets.QMainWindow):

    LEFT_RIGHT = [
        QtCore.Qt.Key_Left,
        QtCore.Qt.Key_Right
    ]
    UP_DOWN = [
        QtCore.Qt.Key_Up,
        QtCore.Qt.Key_Down
    ]

    def __init__(self):
        QtWidgets.QDialog.__init__(self)

        # get ui
        self.ui = uic.loadUi('mainwindow.ui')
        self.ui.setWindowTitle('Python Runner')

        self.directory = QtCore.QDir()
        # self.directory.setCurrent('/')

        self.filemodel = QtWidgets.QFileSystemModel()
        self.filemodel.setNameFilters(['*.py'])

        self.ui.fileViewer.setModel(self.filemodel)

        self.directory.setPath(os.path.expanduser('~'))

        self.folderCompleter = QtWidgets.QCompleter()
        self.folderCompleter.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.folderCompleter.setCompletionMode(QtWidgets.QCompleter.InlineCompletion)
        self.folderCompleter.setModel(self.filemodel)
        self.ui.currentFolder.setCompleter(self.folderCompleter)


        self.interpreter = Interpreter()
        self.interpreter.silentImport('os')

        self.ui.cmdWindow.appendPlainText(self.interpreter.startinfo)

        self.history = ['']
        self.histIndex = 0

        self.ui.varViewer.setColumnCount(3)
        head = self.ui.varViewer.horizontalHeader()
        head.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.ui.varViewer.setHorizontalHeader(head)
        self.ui.varViewer.setHorizontalHeaderLabels(['Name', 'Value', 'Type'])
        
        self.updateFromDir()

        # self.filemodel.setRootPath(self.directory.currentPath())
        # self.ui.fileViewer.setRootIndex(self.filemodel.index(self.directory.currentPath()))
        # self.ui.currentFolder.setText(self.filemodel.rootPath())

        QtWidgets.qApp.processEvents()
        
        self.resizeCols()

        screenFrac = [0.8, 0.8]
        self.resizeWindow(screenFrac)
        
        self.start()

    # ---------- gui preparation (and start) function ----------

    def connectCallbacks(self):
        self.ui.upDirectoryButton.clicked.connect(self._cdUp)
        self.ui.fileViewer.doubleClicked.connect(self.dblClickFcn)
        self.ui.currentFolder.editingFinished.connect(self.lineEditChanged)

        self.keyFunction_builtin = self.ui.cmdWindow.keyPressEvent
        self.ui.cmdWindow.keyPressEvent = self.keyFilter

    def start(self):
        self.connectCallbacks()

        self.promptCmd()

        self.ui.cmdWindow.setFocus()

        # when everything is ready
        self.ui.show()
        self.ui.raise_()
        return

    def resizeWindow(self, screenFraction):
        desktop = QtWidgets.QDesktopWidget()
        geom = self.ui.geometry()
        geom.setWidth(int(screenFraction[0] * desktop.geometry().width()))
        geom.setHeight(int(screenFraction[1] * desktop.geometry().height()))
        geom.moveCenter(desktop.geometry().center())
        self.ui.setGeometry(geom)


    def _cdUp(self):
        if self.directory.cdUp():
            self.updateFromDir()

    def _cdFolder(self, path):
        self.directory.setPath(path)
        self.updateFromDir()

    def dblClickFcn(self, index):
        clickedFile = self.filemodel.fileInfo(index.siblingAtColumn(0))
        if clickedFile.isDir():
            self._cdFolder(clickedFile.filePath())

    def lineEditChanged(self):
        trialFolder = QtCore.QFileInfo(self.ui.currentFolder.text())
        if trialFolder.isDir():
            self._cdFolder(trialFolder.filePath())
        else:
            self.updateFromDir()

    def resizeCols(self):
        for i in range(self.filemodel.columnCount()-1, -1 ,-1):
            self.ui.fileViewer.resizeColumnToContents(i)

    def updateFromDir(self):
        print(self.directory.path())
        self.filemodel.setRootPath(self.directory.path())
        self.ui.fileViewer.setRootIndex(self.filemodel.index(self.directory.path()))
        self.ui.currentFolder.setText(self.filemodel.rootPath())

        r = self.interpreter.command("_os.chdir('{}')".format(self.directory.path()))

    # def printCmd(self, text):
    #     self.ui.cmdWindow.insertPlainText(text)

    def promptCmd(self):
        self.ui.cmdWindow.appendPlainText(self.interpreter.nextprompt)
        self.ui.cmdWindow.moveCursor(QtGui.QTextCursor.End)

    def sendCommand(self, command):
        self.logCommand(command)
        self.histIndex = 0
        response = self.interpreter.command(command)
        if len(response) > 0:
            self.ui.cmdWindow.appendPlainText(response)
        if self.interpreter.newPrompt():
            self.updateLocals()
            self.checkDir()

    def updateLocals(self):
        vardicts = self.interpreter.variables()
        self.ui.varViewer.setRowCount(len(vardicts))
        for i, v in enumerate(vardicts):
            for j, elem in enumerate([v['name'], v['value'], v['type']]):
                self.ui.varViewer.setItem(i, j, QtWidgets.QTableWidgetItem(elem))
        self.ui.varViewer.sortItems(0)

    def checkDir(self):
        wdir = self.interpreter.command('print(_os.getcwd())')
        if not wdir == self.directory.path():
            self._cdFolder(wdir)

    def getCommand(self):
        lastline = self.ui.cmdWindow.toPlainText().split(os.linesep)[-1]
        command = lastline[len(self.interpreter.PROMPT):]
        # print('Got command: "{}"'.format(command))
        return command

    def setCommand(self, command):
        allTextLines = self.ui.cmdWindow.toPlainText().split(os.linesep)
        allTextLines[-1] = allTextLines[-1][:len(self.interpreter.PROMPT)] + command
        self.ui.cmdWindow.setPlainText(os.linesep.join(allTextLines))
        self.cursorToEnd()

    def logCommand(self, command):
        self.history.insert(1, command)

    def cursorToEnd(self):
        cursor = self.ui.cmdWindow.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.ui.cmdWindow.setTextCursor(cursor)

    def keyFilter(self, event):
        if event.key() == QtCore.Qt.Key_Return:
            cmd = self.getCommand()
            self.sendCommand(cmd)
            self.promptCmd()
            
            return
        elif event.key() in self.LEFT_RIGHT:
            self.keyFunction_builtin(event)
        elif event.key() in self.UP_DOWN:
            if event.key() == QtCore.Qt.Key_Up:
                self.histIndex = min(self.histIndex + 1, len(self.history) - 1)
            elif event.key() == QtCore.Qt.Key_Down:
                self.histIndex = max(self.histIndex - 1, 0)
            self.setCommand(self.history[self.histIndex])
        else: # trying to enter text!
            cursor = self.ui.cmdWindow.textCursor()
            Nblocks = self.ui.cmdWindow.blockCount()
            if cursor.columnNumber() >= len(self.interpreter.PROMPT) and cursor.blockNumber() == Nblocks - 1:
                if event.key() == QtCore.Qt.Key_Tab:
                    self.ui.cmdWindow.insertPlainText(4 * ' ')
                else:
                    self.keyFunction_builtin(event)

            

        

        



app = QtWidgets.QApplication(sys.argv)
runner = PyRunner()

if __name__ == '__main__':
    'Executing app.'
    sys.exit(app.exec_())
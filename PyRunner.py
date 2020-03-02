import sys
import os
import re
import subprocess
from time import time

from PyQt5 import QtCore, QtWidgets, uic, QtGui

from interpreter import Interpreter

STARTDIR = '~/Documents/PythonScripts'

def customhook(errorclass, errorobj, traceback):
    print('{0}: {1}'.format(errorclass.name, repr(errorobj)))
    print(repr(traceback))

sys.exceptionhook = customhook

class StatusGetter(QtCore.QObject):
    doneSignal = QtCore.pyqtSignal(dict)

    def __init__(self, interpreter):
        QtCore.QObject.__init__(self)
        self.interpreter = interpreter

    @QtCore.pyqtSlot()
    def work(self):
        # print('Thread doing work.')
        vardicts = self.interpreter.variables()
        wd = self.interpreter.workingDir()

        results = {
            'vardicts': vardicts,
            'wd': wd,
        }
        self.doneSignal.emit(results)

class PyRunner(QtWidgets.QMainWindow):

    LEFT_RIGHT = [
        QtCore.Qt.Key_Left,
        QtCore.Qt.Key_Right
    ]
    UP_DOWN = [
        QtCore.Qt.Key_Up,
        QtCore.Qt.Key_Down
    ]

    def __init__(self, parent):
        QtWidgets.QDialog.__init__(self)

        self.parent = parent
        # get ui
        self.ui = uic.loadUi('mainwindow.ui')
        self.ui.setWindowTitle('PyDE')

        self.directory = QtCore.QDir()
        # self.directory.setCurrent('/')

        self.filemodel = QtWidgets.QFileSystemModel()
        # self.filemodel.setNameFilters(['*.py', '*.pickle'])

        self.ui.fileViewer.setModel(self.filemodel)

        self.directory.setPath(os.path.expanduser(STARTDIR))

        self.folderCompleter = QtWidgets.QCompleter()
        self.folderCompleter.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.folderCompleter.setCompletionMode(QtWidgets.QCompleter.InlineCompletion)
        self.folderCompleter.setModel(self.filemodel)
        self.ui.currentFolder.setCompleter(self.folderCompleter)

        self.interpreter = Interpreter()

        self.ui.cmdWindow.appendPlainText(self.interpreter.startinfo)

        self.statusWorker = StatusGetter(self.interpreter)
        self.bkgThread = QtCore.QThread()
        self.statusWorker.moveToThread(self.bkgThread)
        self.statusWorker.doneSignal.connect(self.consumeStatus)
        self.bkgThread.started.connect(self.statusWorker.work)

        # self.history = ['']
        # self.histIndex = 0

        self.ui.varViewer.setColumnCount(3)
        head = self.ui.varViewer.horizontalHeader()
        head.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.ui.varViewer.setHorizontalHeader(head)
        self.ui.varViewer.setHorizontalHeaderLabels(['Name', 'Value', 'Type'])

        # these take variable name as arg
        self.varActions = {
            'Save (Pickle)': self.interpreter.pickleVar,
            'Save as Text File': self.interpreter.saveTextFile,
            'Delete': self.interpreter.delVar,
            'Delete All': self.interpreter.delAllVars
        }

        # these take fileinfo object as arg
        self.genFileActions = {
            'Copy Path': self.copyFilePath,
            'Import as Text': self.importText,
            'Open Outisde': self.openFile
        }
        self.genDirActions = {
            'Copy Path': self.copyFilePath,
            'Open Outisde': self.openFile
        }
        self.fileExtActions  = {
            '': {
                'Open Directory': self.openFolder
            },
            'pickle': {
                'Load Object': self.loadPickled
            },
            'py': {
                'Run': self.runPythonFile
            }
        }
        # saveVar = QtWidgets.QAction('Save', self)
        # self.ui.varViewer.insertAction(QtWidgets.QAction(), saveVar)
        
        self.updateFromDir()

        # self.filemodel.setRootPath(self.directory.currentPath())
        # self.ui.fileViewer.setRootIndex(self.filemodel.index(self.directory.currentPath()))
        # self.ui.currentFolder.setText(self.filemodel.rootPath())

        self.clipboard = self.parent.clipboard()

        self.parent.processEvents()
        
        self.resizeCols()

        screenFrac = [0.8, 0.8]
        self.resizeWindow(screenFrac)
        
        self.start()

    # ---------- gui preparation (and start) function ----------

    def connectCallbacks(self):
        self.ui.upDirectoryButton.clicked.connect(self._cdUp)
        self.ui.fileViewer.doubleClicked.connect(self.dblClickFcn)
        self.ui.currentFolder.editingFinished.connect(self.lineEditChanged)

        self.ui.runButton.clicked.connect(self.attemptRunSelected)

        self.ui.varViewer.customContextMenuRequested.connect(self.varContextMenuFcn)
        self.ui.fileViewer.customContextMenuRequested.connect(self.fileContextMenuFcn)
        # remember what the callback was so it can be manually called
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
        desktop = self.parent.desktop()
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

    def varContextMenuFcn(self, point):
        item = self.ui.varViewer.itemAt(point)
        if item is not None:
            menu = QtWidgets.QMenu(self)
            for name in list(self.varActions):
                menu.addAction(name)
            action = menu.exec_(self.ui.varViewer.viewport().mapToGlobal(point))
            if action is not None:
                fcn = self.varActions[action.text()]
                fcn(self.ui.varViewer.item(item.row(), 0).text())
                self.fetchStatus()

    def fileContextMenuFcn(self, point):
        index = self.ui.fileViewer.indexAt(point)
        fileInfo = self.filemodel.fileInfo(index)
        # infoDict = {
        #     'Name': fileInfo.fileName(),
        #     'Path': fileInfo.filePath(),
        #     'IsDir': fileInfo.isDir(),
        #     'Suffix': fileInfo.suffix()
        # }
        suffix = fileInfo.suffix()
        if fileInfo.isDir():
            actions  = self.genDirActions.copy()
        else:
            actions  = self.genFileActions.copy()
        actions.update(self.fileExtActions.get(suffix, {}))
        menu = QtWidgets.QMenu(self)
        for name in list(actions):
            menu.addAction(name)
        choice = menu.exec_(self.ui.fileViewer.viewport().mapToGlobal(point))
        if choice is not None:
            fcn = actions[choice.text()]
            fcn(fileInfo)
            self.fetchStatus()

    def copyFilePath(self, fileinfo):
        self.clipboard.setText(fileinfo.filePath(), mode=self.clipboard.Clipboard)

    def openFolder(self, fileinfo):
        if fileinfo.isDir():
            self._cdFolder(fileinfo.filePath())

    def loadPickled(self, fileinfo):
        abspath = fileinfo.absoluteFilePath()
        self.interpreter.unpickleVar(abspath)

    def importText(self, fileinfo):
        abspath = fileinfo.absoluteFilePath()
        self.interpreter.loadTextFile(abspath)

    def openFile(self, fileinfo):
        abspath = fileinfo.absoluteFilePath()
        p = subprocess.run(['open', abspath], capture_output=True)
        errmsg = p.stderr.decode()

    def runPythonFile(self, fileinfo):
        abspath = fileinfo.absoluteFilePath()
        resp = self.interpreter.runFile(abspath)
        if len(resp) > 0:
            self.ui.cmdWindow.appendPlainText(resp)
        self.promptCmd()

    # ----------------------------------------

    def attemptRunSelected(self):
        selected = self.ui.fileViewer.currentIndex()
        fileinfo = self.filemodel.fileInfo(selected)
        if fileinfo.isDir() or not fileinfo.suffix() == 'py':
            return -1
        else:
            self.runPythonFile(fileinfo)
            self.fetchStatus()
            return 0

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
        self.filemodel.setRootPath(self.directory.path())
        self.ui.fileViewer.setRootIndex(self.filemodel.index(self.directory.path()))
        self.ui.currentFolder.setText(self.filemodel.rootPath())

        self.interpreter.changeDir(self.directory.path())

    def promptCmd(self):
        self.ui.cmdWindow.appendPlainText(self.interpreter.nextprompt)
        self.ui.cmdWindow.moveCursor(QtGui.QTextCursor.End)

    def sendCommand(self, command):
        response = self.interpreter.command(command)
        # if not self.interpreter.running:
        #     sys.exit()

        if len(response) > 0:
            self.ui.cmdWindow.appendPlainText(response)
        if self.interpreter.promptIsNew(): # only after block completes
            self.fetchStatus()
            # self.checkDir()

    def fetchStatus(self):
        self.bkgThread.start()

    @QtCore.pyqtSlot(dict)
    def consumeStatus(self, status: dict):
        # print(status)
        self.bkgThread.quit()
        self.updateLocals(status['vardicts'])
        self.checkDir(status['wd'])

    def updateLocals(self, vardicts):
        # vardicts = self.interpreter.variables()
        self.ui.varViewer.setRowCount(len(vardicts))
        for i, v in enumerate(vardicts):
            for j, elem in enumerate([v['name'], v['value'], v['type']]):
                item = QtWidgets.QTableWidgetItem(elem)
                item.setToolTip(elem)
                # item.setFlags(QtCore.Qt.ItemIsSelectable)
                self.ui.varViewer.setItem(i, j, item)
        self.ui.varViewer.sortItems(0)

    def checkDir(self, cwd):
        if not cwd == self.directory.path():
            self._cdFolder(cwd)

    def getCommand(self):
        lastline = self.ui.cmdWindow.toPlainText().split(os.linesep)[-1]
        command = lastline[len(self.interpreter.PROMPT):]
        return command

    def setCommand(self, command):
        allTextLines = self.ui.cmdWindow.toPlainText().split(os.linesep)
        allTextLines[-1] = allTextLines[-1][:len(self.interpreter.PROMPT)] + command
        self.ui.cmdWindow.setPlainText(os.linesep.join(allTextLines))
        self.cursorToEnd()

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
                self.interpreter.histBack()
            elif event.key() == QtCore.Qt.Key_Down:
                self.interpreter.histFwd()
            self.setCommand(self.interpreter.getHistoryCommand())
        else: # trying to enter text!
            cursor = self.ui.cmdWindow.textCursor()
            Nblocks = self.ui.cmdWindow.blockCount()
            if cursor.columnNumber() >= len(self.interpreter.PROMPT) and cursor.blockNumber() == Nblocks - 1:
                if event.key() == QtCore.Qt.Key_Tab:
                    self.ui.cmdWindow.insertPlainText(4 * ' ')
                else:
                    self.keyFunction_builtin(event)



app = QtWidgets.QApplication(sys.argv)
runner = PyRunner(app)

if __name__ == '__main__':
    'Executing app.'
    sys.exit(app.exec_())
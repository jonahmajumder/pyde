# secondary python instance
import os
import sys
import re
from keyword import iskeyword
import pexpect
from time import time

class Interpreter():
    PROMPT_RE = r'[\.>]{3} '
    PROMPT = '>>> '
    NEWLINE = '\r\n'

    def __init__(self, exe=sys.executable):
        self.process = pexpect.spawn(exe)
        self.running = True

        self.history = ['']
        self.histIndex = 0

        self.process.expect(self.PROMPT_RE)
        self.startinfo = self.process.before.decode().strip()

        self.nextprompt = self.process.after.decode()

        self.silentImport('os')
        self.silentImport('pickle')

    def exitFcn(self):
        sys.exit()
        self.running = False

    def logCommand(self, text):
        self.history.insert(1, text)

    def histBack(self):
        self.histIndex = min(self.histIndex + 1, len(self.history) - 1)

    def histFwd(self):
        self.histIndex = max(self.histIndex - 1, 0)

    def getHistoryCommand(self):
        return self.history[self.histIndex]

    def command(self, text, log=True):
        return self._command(text, log)

    def _command(self, text, log=False):


        self.process.sendline(text)

        if log:
            self.logCommand(text)
            self.histIndex = 0

        self.process.expect(self.NEWLINE)
        self.lastecho = self.process.before.decode()

        try:
            self.process.expect(self.PROMPT_RE)
            response = self.process.before.decode().strip()
            self.nextprompt = self.process.after.decode()
            return response
        except pexpect.exceptions.EOF:
            self.exitFcn()

    def silentImport(self, module):
        commandstring = 'import {0} as _{0}'.format(module)
        self._command(commandstring)

    def promptIsNew(self):
        return self.nextprompt == self.PROMPT

    def vardict(self, varname):
        info = {}
        info['name'] = varname
        info['value'] = self._command('print(repr({}))'.format(varname))
        info['type'] = self._command('print({}.__class__.__name__)'.format(varname))
        return info

    def varnames(self, includehidden=False):
        resp = self._command('dir()')
        allnames = eval(resp)
        if includehidden:
            names = allnames
        else:
            names = [var for var in allnames if not var.startswith('_')]
        return names

    def variables(self):
        names = self.varnames()
        dicts = [self.vardict(var) for var in names]
        return dicts

    def workingDir(self):
        cwd = self._command('print(_os.getcwd())')
        return cwd

    def changeDir(self, newDir):
        self._command("_os.chdir('{}')".format(newDir))

    def pickleVar(self, varname):
        allnames = self.varnames(True)
        if '_pickle' in allnames and varname in allnames:
            self._command("f = open('{}.pickle', 'wb')".format(varname))
            self._command("_pickle.dump({}, f)".format(varname))
            self._command("f.close(); del f")
            return 0
        else:
            return -1

    def unpickleVar(self, filename):
        loc, rel = os.path.split(filename)
        base, ext = os.path.splitext(rel)
        if not base.isidentifier() or iskeyword(base):
            return -1

        allnames = self.varnames(True)
        if '_pickle' in allnames:
            self._command("f = open('{}', 'rb')".format(filename))
            self._command("{0} = _pickle.load(f)".format(base))
            self._command("f.close(); del f")
            return 0
        else:
            return -1

    def loadTextFile(self, filename, varname='text'):
        loc, rel = os.path.split(filename)
        base, ext = os.path.splitext(rel)
        self._command("f = open('{}', 'r')".format(filename))
        self._command("{0} = f.read()".format(varname))
        self._command("f.close(); del f")

    def saveTextFile(self, varname):
        names = self.varnames()
        if varname in names:
            self._command("f = open('{}.txt', 'w')".format(varname))
            self._command("f.write('{{}}'.format({}))".format(varname))
            self._command("f.close(); del f")
            return 0
        else:
            return -1



    def delVar(self, varname):
        self._command("del {}".format(varname))

    def readFile(self, relpath):
        abspath = os.path.join(self.workingDir(), relpath)
        with open(abspath, 'r') as file:
            text = file.read()
        filelines = text.split(os.linesep)
        return filelines

    def runFile(self, filename):
        loc, rel = os.path.split(filename)
        base, ext = os.path.splitext(rel)
        assert ext == '.py'
        assert loc == self.workingDir() 
        commandstring = 'from {} import *'.format(base)
        resp = self._command(commandstring)
        return resp

    def debugFile(self, relpath):
        lines = self.readFile(relpath)
        codelines, deindents = self.filterLines(lines)
        responses = []
        for line, extraLineNeeded in zip(codelines, deindents):
            if not extraLineNeeded:
                responses.append(self._command(line))
            else:
                self._command(line)
                responses.append(self._command(''))
        return responses

    def filterLines(self, fileLines):
        codelines = [l for l in fileLines if len(l.strip()) and not l.strip().startswith('#')]
        indentlevels = [len(re.findall(4*' ', l)) for l in codelines]
        deindents = [a > 0 and b == 0 for a,b in zip(indentlevels,indentlevels[1:] + [0])]
        return codelines, deindents



if __name__ == '__main__':
    p = Interpreter()

    print(repr(p.startinfo))

    p.command('a = 2')
    p.variables()
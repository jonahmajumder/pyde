# secondary python instance
import sys
import pexpect
from time import time

class Interpreter():
    PROMPT_RE = r'[\.>]{3} '
    PROMPT = '>>> '
    NEWLINE = '\r\n'

    def __init__(self, exe=sys.executable):
        self.process = pexpect.spawn(exe)

        self.process.expect(self.PROMPT_RE)
        self.startinfo = self.process.before.decode().strip()

        self.nextprompt = self.process.after.decode()

    def command(self, text):
        self.process.sendline(text)

        self.process.expect(self.NEWLINE)
        self.lastecho = self.process.before.decode()

        self.process.expect(self.PROMPT_RE)
        response = self.process.before.decode().strip()

        self.nextprompt = self.process.after.decode()

        return response

    def silentImport(self, module):
        commandstring = 'import {0} as _{0}'.format(module)
        self.command(commandstring)

    def newPrompt(self):
        return self.nextprompt == self.PROMPT

    def vardict(self, varname):
        info = {}
        info['name'] = varname
        info['value'] = self.command('print(repr({}))'.format(varname))
        info['type'] = self.command('print({}.__class__.__name__)'.format(varname))
        return info

    def variables(self):
        resp = self.command('dir()')
        varnames = [var for var in eval(resp) if not var.startswith('_')]
        dicts = [self.vardict(var) for var in varnames]
        return dicts
        

if __name__ == '__main__':
    p = Interpreter()

    print(repr(p.startinfo))

    p.command('a = 2')
    p.variables()
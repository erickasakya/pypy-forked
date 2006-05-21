#!/bin/env python
import autopath
import sys
import py
from pypy.rpython.rarithmetic import r_int, r_uint, r_ulonglong, r_longlong, ovfcheck
from pypy.translator.test import snippet as s
from pypy.translator.cli import conftest
from pypy.translator.cli.test.runtest import compile_function

py.test.Config.parse(py.std.sys.argv[1:])

#conftest.option.view = True
#conftest.option.source = True
conftest.option.wd = True
#conftest.option.nostop = True
#conftest.option.stdout = True

def check(f, g, *args):
    x = f(*args)
    y = g(*args)
    if x != y:
        print x, '!=', y
    else:
        print 'OK'


class Foo:
    def __init__(self, x):
        self.x = x

def foo(a, b):
    pass

def bar(x, y):
    if x:
        return 1
    else:
        return None
    

f = compile_function(bar, [int, int])

try:
    check(bar, f, 42, 13)
except py.test.Item.Skipped:
    print 'Test skipped'


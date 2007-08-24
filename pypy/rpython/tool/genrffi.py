#!/usr/bin/env python

import ctypes
from pypy.rpython.lltypesystem import rffi
from pypy.rpython.lltypesystem import lltype
from pypy.rlib.unroll import unrolling_iterable

import py

#rffi.UINT = rffi.INT # XXX
#rffi.UCHAR = lltype.Char # XXX

# XXX any automatic stuff here?
_TYPE_MAPPING = {
    ctypes.c_ubyte     : rffi.UCHAR,
    ctypes.c_byte      : rffi.CHAR,
    ctypes.c_char      : rffi.CHAR,
    ctypes.c_int8      : rffi.CHAR,
    ctypes.c_ushort    : rffi.USHORT,
    ctypes.c_short     : rffi.SHORT,
    ctypes.c_uint16    : rffi.USHORT,
    ctypes.c_int16     : rffi.SHORT,
    ctypes.c_int       : rffi.INT,
    ctypes.c_uint      : rffi.UINT,
    ctypes.c_int32     : rffi.INT,
    ctypes.c_uint32    : rffi.UINT,
    #ctypes.c_long      : rffi.LONG, # same as c_int..
    #ctypes.c_ulong     : rffi.ULONG,
    ctypes.c_longlong  : rffi.LONGLONG,
    ctypes.c_ulonglong : rffi.ULONGLONG,
    ctypes.c_int64     : rffi.LONGLONG,
    ctypes.c_uint64    : rffi.ULONGLONG,
    ctypes.c_voidp     : rffi.VOIDP,
    None               : rffi.lltype.Void, # XXX make a type in rffi
    ctypes.c_char_p    : rffi.CCHARP,
    ctypes.c_double    : rffi.lltype.Float, # XXX make a type in rffi
}


def softwrapper(funcptr, arg_tps):
    # Here we wrap with a function that does some simple type coercion.
    unrolling_arg_tps = unrolling_iterable(enumerate(arg_tps))
    def softfunc(*args):
        real_args = ()
        for i, tp in unrolling_arg_tps:
            if tp == rffi.lltype.Float:
                real_args = real_args + (float(args[i]),)
            else:
                real_args = real_args + (args[i],)
        result = funcptr(*real_args)
        return result
    return softfunc


class RffiBuilder(object):
    def __init__(self, ns=None, includes=[], libraries=[], include_dirs=[]):
        if ns is None:
            # map name -> lltype object
            self.ns = {}
        else:
            self.ns = ns
        self.includes = includes
        self.libraries = libraries
        self.include_dirs = include_dirs

    def proc_struct(self, tp):
        name = tp.__name__
        struct = self.ns.get(name)
        if struct is None:
            fields = []
            if not hasattr(tp, '_fields_'):
                raise NotImplementedError("no _fields")
            for field in tp._fields_:
                if len(field) != 2:
                    raise NotImplementedError("field length")
                name_, field_tp = field
                fields.append((name_, self.proc_tp(field_tp)))
            struct = lltype.Struct(name, *fields, **{'hints':{'external':'C', 'c_name':name}})
            self.ns[name] = struct
        return struct

    def proc_tp(self, tp):
        try:
            return _TYPE_MAPPING[tp]
        except KeyError:
            pass
        if issubclass(tp, ctypes._Pointer):
            if issubclass(tp._type_, ctypes._SimpleCData):
                x = self.proc_tp(tp._type_)
                ll_tp = lltype.Ptr(lltype.Array(x, hints={'nolength': True}))
            else:
                ll_tp = lltype.Ptr(self.proc_tp(tp._type_))
        elif issubclass(tp, ctypes.Structure):
            ll_tp = self.proc_struct(tp)
        else:
            raise NotImplementedError("Not implemented mapping for %s" % tp)
        _TYPE_MAPPING[tp] = ll_tp
        return ll_tp

    def proc_func(self, func):
        name = func.__name__
        arg_tps = [self.proc_tp(arg) for arg in func.argtypes]
        ll_item = rffi.llexternal(
            name, arg_tps,
            self.proc_tp(func.restype), 
            includes=self.includes, libraries=self.libraries, 
            include_dirs=self.include_dirs)
        soft = softwrapper(ll_item, arg_tps)
        self.ns[name] = soft
        return soft

    def proc_namespace(self, ns):
        exempt = set(id(value) for value in ctypes.__dict__.values())
        for key, value in ns.items():
            if id(value) in exempt: 
                continue
            if isinstance(value, ctypes._CFuncPtr):
                try:    
                    self.proc_func(value)
                except NotImplementedError, e:
                    print "genrffi: skipped:", key, value, e
                except TypeError, e:
                    print "genrffi: skipped:", key, value, e







from rpython.rlib import rmpdec
from rpython.rlib.unroll import unrolling_iterable
from pypy.interpreter.error import oefmt

SIGNAL_MAP = unrolling_iterable([
    ('InvalidOperation', rmpdec.MPD_IEEE_Invalid_operation),
    ('FloatOperation', rmpdec.MPD_Float_operation),
    ('DivisionByZero', rmpdec.MPD_Division_by_zero),
    ('Overflow', rmpdec.MPD_Overflow),
    ('Underflow', rmpdec.MPD_Underflow),
    ('Subnormal', rmpdec.MPD_Subnormal),
    ('Inexact', rmpdec.MPD_Inexact),
    ('Rounded', rmpdec.MPD_Rounded),
    ('Clamped', rmpdec.MPD_Clamped),
    ])
# Exceptions that inherit from InvalidOperation
COND_MAP = unrolling_iterable([
    ('InvalidOperation', rmpdec.MPD_Invalid_operation),
    ('ConversionSyntax', rmpdec.MPD_Conversion_syntax),
    ('DivisionImpossible', rmpdec.MPD_Division_impossible),
    ('DivisionUndefined', rmpdec.MPD_Division_undefined),
    ('InvalidContext', rmpdec.MPD_Invalid_context),
    ])

def flags_as_exception(space, flags):
    w_exc = None
    err_list = []
    for name, flag in SIGNAL_MAP:
        if flags & flag:
            w_exc = getattr(get(space), 'w_' + name)
    if w_exc is None:
        raise oefmt(space.w_RuntimeError,
                    "invalid error flag")
    
        
    raise ValueError(hex(flags))


class SignalState:
    def __init__(self, space):
        self.w_DecimalException = space.call_function(
            space.w_type, space.wrap("DecimalException"),
            space.newtuple([space.w_ArithmeticError]),
            space.newdict())
        self.w_Clamped = space.call_function(
            space.w_type, space.wrap("Clamped"),
            space.newtuple([self.w_DecimalException]),
            space.newdict())
        self.w_Rounded = space.call_function(
            space.w_type, space.wrap("Rounded"),
            space.newtuple([self.w_DecimalException]),
            space.newdict())
        self.w_Inexact = space.call_function(
            space.w_type, space.wrap("Inexact"),
            space.newtuple([self.w_DecimalException]),
            space.newdict())
        self.w_Subnormal = space.call_function(
            space.w_type, space.wrap("Subnormal"),
            space.newtuple([self.w_DecimalException]),
            space.newdict())
        self.w_Underflow = space.call_function(
            space.w_type, space.wrap("Underflow"),
            space.newtuple([self.w_Inexact,
                            self.w_Rounded,
                            self.w_Subnormal]),
            space.newdict())
        self.w_Overflow = space.call_function(
            space.w_type, space.wrap("Overflow"),
            space.newtuple([self.w_Inexact,
                            self.w_Rounded]),
            space.newdict())
        self.w_DivisionByZero = space.call_function(
            space.w_type, space.wrap("DivisionByZero"),
            space.newtuple([self.w_DecimalException,
                            space.w_ZeroDivisionError]),
            space.newdict())
        self.w_InvalidOperation = space.call_function(
            space.w_type, space.wrap("InvalidOperation"),
            space.newtuple([self.w_DecimalException]),
            space.newdict())
        self.w_FloatOperation = space.call_function(
            space.w_type, space.wrap("FloatOperation"),
            space.newtuple([self.w_DecimalException,
                            space.w_TypeError]),
            space.newdict())

def get(space):
    return space.fromcache(SignalState)

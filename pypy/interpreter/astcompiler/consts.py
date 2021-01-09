"""
Various flags used during the compilation process.
"""

CO_OPTIMIZED = 0x0001
CO_NEWLOCALS = 0x0002
CO_VARARGS = 0x0004
CO_VARKEYWORDS = 0x0008
CO_NESTED = 0x0010
CO_GENERATOR = 0x0020
CO_NOFREE = 0x0040
CO_COROUTINE = 0x0080
CO_ITERABLE_COROUTINE = 0x0100    # set by @types.coroutine
CO_ASYNC_GENERATOR = 0x0200
CO_GENERATOR_ALLOWED = 0x1000
CO_FUTURE_DIVISION = 0x2000
CO_FUTURE_ABSOLUTE_IMPORT = 0x4000
CO_FUTURE_WITH_STATEMENT = 0x8000
CO_FUTURE_PRINT_FUNCTION = 0x10000
CO_FUTURE_UNICODE_LITERALS = 0x20000
CO_FUTURE_BARRY_AS_BDFL = 0x40000
CO_FUTURE_GENERATOR_STOP = 0x80000
CO_FUTURE_ANNOTATIONS     = 0x100000  # annotations become strings at runtime

#pypy specific:
CO_KILL_DOCSTRING = 0x200000
CO_YIELD_INSIDE_TRY = 0x400000

PyCF_MASK = (CO_FUTURE_DIVISION | CO_FUTURE_ABSOLUTE_IMPORT |
             CO_FUTURE_WITH_STATEMENT | CO_FUTURE_PRINT_FUNCTION |
             CO_FUTURE_UNICODE_LITERALS | CO_FUTURE_BARRY_AS_BDFL |
             CO_FUTURE_GENERATOR_STOP | CO_FUTURE_ANNOTATIONS)
PyCF_SOURCE_IS_UTF8 = 0x0100
PyCF_DONT_IMPLY_DEDENT = 0x0200
PyCF_ONLY_AST = 0x0400
PyCF_IGNORE_COOKIE = 0x0800
PyCF_ACCEPT_NULL_BYTES = 0x10000000   # PyPy only, for compile()
PyCF_FOUND_ENCODING = 0x20000000      # PyPy only, for pytokenizer

# Masks and values used by FORMAT_VALUE opcode
FVC_MASK      = 0x3
FVC_NONE      = 0x0
FVC_STR       = 0x1
FVC_REPR      = 0x2
FVC_ASCII     = 0x3
FVS_MASK      = 0x4
FVS_HAVE_SPEC = 0x4

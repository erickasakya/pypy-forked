from pypy.module._stackless.interp_coroutine import AbstractThunk, BaseCoState, Coroutine
from pypy.rlib.rgc import gc_swap_pool, gc_clone
from pypy.rlib.objectmodel import we_are_translated

from pypy.interpreter.error import OperationError

from pypy.tool import stdlib_opcode as pythonopcode


class InterpClonableMixin:
    local_pool = None
    _mixin_ = True

    def hello_local_pool(self):
        if we_are_translated():
            self.saved_pool = gc_swap_pool(self.local_pool)

    def goodbye_local_pool(self):
        if we_are_translated():
            self.local_pool = gc_swap_pool(self.saved_pool)

    def clone_into(self, copy):
        if not we_are_translated():
            raise NotImplementedError
        if self.local_pool is None:   # force it now
            self.local_pool = gc_swap_pool(gc_swap_pool(None))
        # cannot gc_clone() directly self, because it is not in its own
        # local_pool.  Moreover, it has a __del__, which cloning doesn't
        # support properly at the moment.
        copy.parent = self.parent
        copy.frame, copy.local_pool = gc_clone(self.frame, self.local_pool)


class InterpClonableCoroutine(Coroutine, InterpClonableMixin):

    def hello(self):
        self.hello_local_pool()

    def goodbye(self):
        self.goodbye_local_pool()

    def clone(self):
        # hack, this is overridden in AppClonableCoroutine
        if self.getcurrent() is self:
            raise RuntimeError("clone() cannot clone the current coroutine; "
                               "use fork() instead")
        copy = InterpClonableCoroutine(self.costate)
        self.clone_into(copy)
        return copy


class ForkThunk(AbstractThunk):
    def __init__(self, coroutine):
        self.coroutine = coroutine
        self.newcoroutine = None
    def call(self):
        oldcoro = self.coroutine
        self.coroutine = None
        self.newcoroutine = oldcoro.clone()

def fork():
    """Fork, as in the Unix fork(): the call returns twice, and the return
    value of the call is either the new 'child' coroutine object (if returning
    into the parent), or None (if returning into the child).  This returns
    into the parent first, which can switch to the child later.
    """
    current = InterpClonableCoroutine.getcurrent()
    if not isinstance(current, InterpClonableCoroutine):
        raise RuntimeError("fork() in a non-clonable coroutine")
    thunk = ForkThunk(current)
    coro_fork = InterpClonableCoroutine() 
    coro_fork.bind(thunk)
    coro_fork.switch()
    # we resume here twice.  The following would need explanations about
    # why it returns the correct thing in both the parent and the child...
    return thunk.newcoroutine

##    from pypy.rpython.lltypesystem import lltype, lloperation
##    lloperation.llop.debug_view(lltype.Void, current, thunk,
##        lloperation.llop.gc_x_size_header(lltype.Signed))


""" Tests for register allocation for common constructs
"""

import py
from pypy.jit.metainterp.history import ResOperation, BoxInt, ConstInt,\
     BoxPtr, ConstPtr, LoopToken
from pypy.jit.metainterp.resoperation import rop, ResOperation
from pypy.jit.backend.llsupport.descr import GcCache
from pypy.jit.backend.x86.runner import CPU
from pypy.jit.backend.x86.regalloc import RegAlloc, WORD, X86RegisterManager
from pypy.jit.metainterp.test.oparser import parse
from pypy.rpython.lltypesystem import lltype, llmemory, rffi
from pypy.rpython.annlowlevel import llhelper
from pypy.rpython.lltypesystem import rclass, rstr
from pypy.jit.backend.x86.ri386 import *

class MockGcDescr(GcCache):
    def get_funcptr_for_new(self):
        return 123
    get_funcptr_for_newarray = get_funcptr_for_new
    get_funcptr_for_newstr = get_funcptr_for_new
    get_funcptr_for_newunicode = get_funcptr_for_new
 
    def rewrite_assembler(self, cpu, operations):
        pass

class MockAssembler(object):
    gcrefs = None

    def __init__(self, cpu=None, gc_ll_descr=None):
        self.movs = []
        self.performs = []
        self.lea = []
        self.cpu = cpu or CPU(None, None)
        if gc_ll_descr is None:
            gc_ll_descr = MockGcDescr(False)
        self.cpu.gc_ll_descr = gc_ll_descr

    def dump(self, *args):
        pass

    def regalloc_mov(self, from_loc, to_loc):
        self.movs.append((from_loc, to_loc))

    def regalloc_perform(self, op, arglocs, resloc):
        self.performs.append((op, arglocs, resloc))

    def regalloc_perform_discard(self, op, arglocs):
        self.performs.append((op, arglocs))

    def load_effective_addr(self, *args):
        self.lea.append(args)

def fill_regs(regalloc, cls=BoxInt):
    allboxes = []
    for reg in X86RegisterManager.all_regs:
        box = cls()
        allboxes.append(box)
        regalloc.rm.try_allocate_reg()
    return allboxes
    
class RegAllocForTests(RegAlloc):
    position = 0
    def _compute_next_usage(self, v, _):
        return -1

class BaseTestRegalloc(object):
    cpu = CPU(None, None)

    def raising_func(i):
        if i:
            raise LLException(zero_division_error,
                              zero_division_value)
    FPTR = lltype.Ptr(lltype.FuncType([lltype.Signed], lltype.Void))
    raising_fptr = llhelper(FPTR, raising_func)
    zero_division_tp, zero_division_value = cpu.get_zero_division_error()
    zd_addr = cpu.cast_int_to_adr(zero_division_tp)
    zero_division_error = llmemory.cast_adr_to_ptr(zd_addr,
                                            lltype.Ptr(rclass.OBJECT_VTABLE))
    raising_calldescr = cpu.calldescrof(FPTR.TO, FPTR.TO.ARGS, FPTR.TO.RESULT)

    namespace = locals().copy()
    type_system = 'lltype'

    def parse(self, s, boxkinds=None, jump_target=None):
        return parse(s, self.cpu, self.namespace,
                     type_system=self.type_system,
                     jump_target=jump_target,
                     boxkinds=boxkinds)

    def interpret(self, ops, args, jump_target=None, run=True):
        loop = self.parse(ops, jump_target=jump_target)
        executable_token = self.cpu.compile_loop(loop.inputargs,
                                                 loop.operations)
        for i, arg in enumerate(args):
            if isinstance(arg, int):
                self.cpu.set_future_value_int(i, arg)
            else:
                assert isinstance(lltype.typeOf(arg), lltype.Ptr)
                llgcref = lltype.cast_opaque_ptr(llmemory.GCREF, arg)
                self.cpu.set_future_value_ref(i, llgcref)
        if run:
            self.cpu.execute_token(executable_token)
        loop_token = LoopToken()
        loop_token.executable_token = executable_token
        loop_token._loop = loop
        return loop_token

    def getint(self, index):
        return self.cpu.get_latest_value_int(index)

    def getints(self, end):
        return [self.cpu.get_latest_value_int(index) for
                index in range(0, end)]

    def getptr(self, index, T):
        gcref = self.cpu.get_latest_value_ref(index)
        return lltype.cast_opaque_ptr(T, gcref)

    def attach_bridge(self, ops, loop_token, guard_op_index, **kwds):
        guard_op = loop_token._loop.operations[guard_op_index]
        assert guard_op.is_guard()
        bridge = self.parse(ops, **kwds)
        faildescr = guard_op.descr
        self.cpu.compile_bridge(faildescr, bridge.inputargs, bridge.operations)
        return bridge

    def run(self, loop_token):
        return self.cpu.execute_token(loop_token.executable_token)

class TestRegallocSimple(BaseTestRegalloc):
    def test_simple_loop(self):
        ops = '''
        [i0]
        i1 = int_add(i0, 1)
        i2 = int_lt(i1, 20)
        guard_true(i2) [i1]
        jump(i1)
        '''
        self.interpret(ops, [0])
        assert self.getint(0) == 20

    def test_two_loops_and_a_bridge(self):
        ops = '''
        [i0, i1, i2, i3]
        i4 = int_add(i0, 1)
        i5 = int_lt(i4, 20)
        guard_true(i5) [i4, i1, i2, i3]
        jump(i4, i1, i2, i3)
        '''
        loop = self.interpret(ops, [0, 0, 0, 0])
        ops2 = '''
        [i5]
        i1 = int_add(i5, 1)
        i3 = int_add(i1, 1)
        i4 = int_add(i3, 1)
        i2 = int_lt(i4, 30)
        guard_true(i2) [i4]
        jump(i4)
        '''
        loop2 = self.interpret(ops2, [0])
        bridge_ops = '''
        [i4]
        jump(i4, i4, i4, i4)
        '''
        bridge = self.attach_bridge(bridge_ops, loop2, 4, jump_target=loop)
        self.cpu.set_future_value_int(0, 0)
        self.run(loop2)
        assert self.getint(0) == 31
        assert self.getint(1) == 30
        assert self.getint(2) == 30
        assert self.getint(3) == 30

    def test_pointer_arg(self):
        ops = '''
        [i0, p0]
        i1 = int_add(i0, 1)
        i2 = int_lt(i1, 10)
        guard_true(i2) [p0]
        jump(i1, p0)
        '''
        S = lltype.GcStruct('S')
        ptr = lltype.malloc(S)
        self.interpret(ops, [0, ptr])
        assert self.getptr(0, lltype.Ptr(S)) == ptr
        assert not self.cpu.assembler.fail_boxes_ptr[0]
        assert not self.cpu.assembler.fail_boxes_ptr[1]

    def test_exception_bridge_no_exception(self):
        ops = '''
        [i0]
        i1 = same_as(1)
        call(ConstClass(raising_fptr), i0, descr=raising_calldescr)
        guard_exception(ConstClass(zero_division_error)) [i1]
        finish(0)
        '''
        bridge_ops = '''
        [i3]
        i2 = same_as(2)
        guard_no_exception() [i2]
        finish(1)
        '''
        loop = self.interpret(ops, [0])
        assert self.getint(0) == 1
        bridge = self.attach_bridge(bridge_ops, loop, 2)
        self.cpu.set_future_value_int(0, 0)
        self.run(loop)
        assert self.getint(0) == 1

    def test_inputarg_unused(self):
        ops = '''
        [i0]
        finish(1)
        '''
        self.interpret(ops, [0])
        # assert did not explode

    def test_nested_guards(self):
        ops = '''
        [i0, i1]
        guard_true(i0) [i0, i1]
        finish(4)
        '''
        bridge_ops = '''
        [i0, i1]
        guard_true(i0) [i0, i1]
        finish(3)
        '''
        loop = self.interpret(ops, [0, 10])
        assert self.getint(0) == 0
        assert self.getint(1) == 10
        bridge = self.attach_bridge(bridge_ops, loop, 0)
        self.cpu.set_future_value_int(0, 0)
        self.cpu.set_future_value_int(1, 10)
        self.run(loop)
        assert self.getint(0) == 0
        assert self.getint(1) == 10

    def test_nested_unused_arg(self):
        ops = '''
        [i0, i1]
        guard_true(i0) [i0, i1]
        finish(1)
        '''
        loop = self.interpret(ops, [0, 1])
        assert self.getint(0) == 0
        bridge_ops = '''
        [i0, i1]
        finish(1, 2)
        '''
        self.attach_bridge(bridge_ops, loop, 0)
        self.cpu.set_future_value_int(0, 0)
        self.cpu.set_future_value_int(1, 1)
        self.run(loop)

    def test_spill_for_constant(self):
        ops = '''
        [i0, i1, i2, i3]
        i4 = int_add(3, i1)
        i5 = int_lt(i4, 30)
        guard_true(i5) [i0, i4, i2, i3]
        jump(1, i4, 3, 4)
        '''
        self.interpret(ops, [0, 0, 0, 0])
        assert self.getints(4) == [1, 30, 3, 4]

    def test_spill_for_constant_lshift(self):
        ops = '''
        [i0, i2, i1, i3]
        i4 = int_lshift(1, i1)
        i5 = int_add(1, i1)
        i6 = int_lt(i5, 30)
        guard_true(i6) [i4, i5, i2, i3]
        jump(i4, 3, i5, 4)
        '''
        self.interpret(ops, [0, 0, 0, 0])
        assert self.getints(4) == [1<<29, 30, 3, 4]
        ops = '''
        [i0, i1, i2, i3]
        i4 = int_lshift(1, i1)
        i5 = int_add(1, i1)
        i6 = int_lt(i5, 30)
        guard_true(i6) [i4, i5, i2, i3]
        jump(i4, i5, 3, 4)
        '''
        self.interpret(ops, [0, 0, 0, 0])
        assert self.getints(4) == [1<<29, 30, 3, 4]
        ops = '''
        [i0, i3, i1, i2]
        i4 = int_lshift(1, i1)
        i5 = int_add(1, i1)
        i6 = int_lt(i5, 30)
        guard_true(i6) [i4, i5, i2, i3]
        jump(i4, 4, i5, 3)
        '''
        self.interpret(ops, [0, 0, 0, 0])
        assert self.getints(4) == [1<<29, 30, 3, 4]

    def test_result_selected_reg_via_neg(self):
        ops = '''
        [i0, i1, i2, i3]
        i6 = int_neg(i2)
        i7 = int_add(1, i1)
        i4 = int_lt(i7, 10)
        guard_true(i4) [i0, i6, i7]
        jump(1, i7, i2, i6)
        '''
        self.interpret(ops, [0, 0, 3, 0])
        assert self.getints(3) == [1, -3, 10]
        
    def test_compare_memory_result_survives(self):
        ops = '''
        [i0, i1, i2, i3]
        i4 = int_lt(i0, i1)
        i5 = int_add(i3, 1)
        i6 = int_lt(i5, 30)
        guard_true(i6) [i4]
        jump(i0, i1, i4, i5)
        '''
        self.interpret(ops, [0, 10, 0, 0])
        assert self.getint(0) == 1

    def test_jump_different_args(self):
        ops = '''
        [i0, i15, i16, i18, i1, i2, i3]
        i4 = int_add(i3, 1)
        i5 = int_lt(i4, 20)
        guard_true(i5) [i2, i1]
        jump(i0, i18, i15, i16, i2, i1, i4)
        '''
        self.interpret(ops, [0, 1, 2, 3])

    def test_op_result_unused(self):
        ops = '''
        [i0, i1]
        i2 = int_add(i0, i1)
        finish(0)
        '''
        self.interpret(ops, [0, 0])

    def test_guard_value_two_boxes(self):
        ops = '''
        [i0, i1, i2, i3, i4, i5, i6, i7]
        guard_value(i6, i1) [i0, i2, i3, i4, i5, i6]
        finish(i0, i2, i3, i4, i5, i6)
        '''
        self.interpret(ops, [0, 0, 0, 0, 0, 0, 0, 0])
        assert self.getint(0) == 0

    def test_bug_wrong_stack_adj(self):
        ops = '''
        [i0, i1, i2, i3, i4, i5, i6, i7, i8]
        i9 = same_as(0)
        guard_true(i0) [i9, i0, i1, i2, i3, i4, i5, i6, i7, i8]
        finish(1, i0, i1, i2, i3, i4, i5, i6, i7, i8)
        '''
        loop = self.interpret(ops, [0, 1, 2, 3, 4, 5, 6, 7, 8])
        assert self.getint(0) == 0
        bridge_ops = '''
        [i9, i0, i1, i2, i3, i4, i5, i6, i7, i8]
        call(ConstClass(raising_fptr), 0, descr=raising_calldescr)
        finish(i0, i1, i2, i3, i4, i5, i6, i7, i8)
        '''
        self.attach_bridge(bridge_ops, loop, 1)
        for i in range(9):
            self.cpu.set_future_value_int(i, i)
        self.run(loop)
        assert self.getints(9) == range(9)

class TestRegallocCompOps(BaseTestRegalloc):
    
    def test_cmp_op_0(self):
        ops = '''
        [i0, i3]
        i1 = same_as(1)
        i2 = int_lt(i0, 100)
        guard_true(i3) [i1, i2]
        finish(0, i2)
        '''
        self.interpret(ops, [0, 1])
        assert self.getint(0) == 0

class TestRegallocMoreRegisters(BaseTestRegalloc):

    cpu = BaseTestRegalloc.cpu

    S = lltype.GcStruct('S', ('field', lltype.Char))
    fielddescr = cpu.fielddescrof(S, 'field')

    A = lltype.GcArray(lltype.Char)
    arraydescr = cpu.arraydescrof(A)

    namespace = locals().copy()

    def test_int_is_true(self):
        ops = '''
        [i0, i1, i2, i3, i4, i5, i6, i7]
        i10 = int_is_true(i0)
        i11 = int_is_true(i1)
        i12 = int_is_true(i2)
        i13 = int_is_true(i3)
        i14 = int_is_true(i4)
        i15 = int_is_true(i5)
        i16 = int_is_true(i6)
        i17 = int_is_true(i7)
        finish(i10, i11, i12, i13, i14, i15, i16, i17)
        '''
        self.interpret(ops, [0, 42, 12, 0, 13, 0, 0, 3333])
        assert self.getints(8) == [0, 1, 1, 0, 1, 0, 0, 1]

    def test_comparison_ops(self):
        ops = '''
        [i0, i1, i2, i3, i4, i5, i6]
        i10 = int_lt(i0, i1)
        i11 = int_le(i2, i3)
        i12 = int_ge(i4, i5)
        i13 = int_eq(i5, i6)
        i14 = int_gt(i6, i2)
        i15 = int_ne(i2, i6)
        finish(i10, i11, i12, i13, i14, i15)
        '''
        self.interpret(ops, [0, 1, 2, 3, 4, 5, 6])
        assert self.getints(6) == [1, 1, 0, 0, 1, 1]

    def test_nullity(self):
        ops = '''
        [i0, i1, i2, i3, i4, i5, i6]
        i10 = oononnull(i0)
        i11 = ooisnull(i1)
        i12 = oononnull(i2)
        i13 = oononnull(i3)
        i14 = ooisnull(i6)
        i15 = ooisnull(i5)
        finish(i10, i11, i12, i13, i14, i15)
        '''
        self.interpret(ops, [0, 1, 2, 3, 4, 5, 6])
        assert self.getints(6) == [0, 0, 1, 1, 0, 0]

    def test_strsetitem(self):
        ops = '''
        [p0, i]
        strsetitem(p0, 1, i)
        finish()
        '''
        llstr  = rstr.mallocstr(10)
        self.interpret(ops, [llstr, ord('a')])
        assert llstr.chars[1] == 'a'

    def test_setfield_char(self):
        ops = '''
        [p0, i]
        setfield_gc(p0, i, descr=fielddescr)
        finish()
        '''
        s = lltype.malloc(self.S)
        self.interpret(ops, [s, ord('a')])
        assert s.field == 'a'

    def test_setarrayitem_gc(self):
        ops = '''
        [p0, i]
        setarrayitem_gc(p0, 1, i, descr=arraydescr)
        finish()
        '''
        s = lltype.malloc(self.A, 3)
        self.interpret(ops, [s, ord('a')])
        assert s[1] == 'a'

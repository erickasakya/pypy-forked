import py

from pypy.objspace.std.celldict import (
    ModuleDictStrategy, init_celldict_cache, _finditem_with_cache)
from pypy.objspace.std.dictmultiobject import W_DictObject, W_ModuleDictObject
from pypy.objspace.std.test.test_dictmultiobject import (
    BaseTestRDictImplementation, BaseTestDevolvedDictImplementation, FakeSpace,
    FakeString)

space = FakeSpace()

class TestCellDict(object):
    FakeString = FakeString

    def test_basic_property_cells(self):
        strategy = ModuleDictStrategy(space)
        storage = strategy.get_empty_storage()
        d = W_ModuleDictObject(space, strategy, storage)

        v1 = strategy.version
        key = "a"
        w_key = self.FakeString(key)
        d.setitem(w_key, 1)
        v2 = strategy.version
        assert v1 is not v2
        assert d.getitem(w_key) == 1
        assert d.get_strategy().getdictvalue_no_unwrapping(d, key) == 1

        d.setitem(w_key, 2)
        v3 = strategy.version
        assert v2 is not v3
        assert d.getitem(w_key) == 2
        assert d.get_strategy().getdictvalue_no_unwrapping(d, key).w_value == 2

        d.setitem(w_key, 3)
        v4 = strategy.version
        assert v3 is v4
        assert d.getitem(w_key) == 3
        assert d.get_strategy().getdictvalue_no_unwrapping(d, key).w_value == 3

        d.delitem(w_key)
        v5 = strategy.version
        assert v5 is not v4
        assert d.getitem(w_key) is None
        assert d.get_strategy().getdictvalue_no_unwrapping(d, key) is None

    def test_same_key_set_twice(self):
        strategy = ModuleDictStrategy(space)
        storage = strategy.get_empty_storage()
        d = W_ModuleDictObject(space, strategy, storage)

        v1 = strategy.version
        x = object()
        d.setitem("a", x)
        v2 = strategy.version
        assert v1 is not v2
        d.setitem("a", x)
        v3 = strategy.version
        assert v2 is v3

    def test_global_cache(self):
        class FakePycode(object):
            co_names_w = ['a', 'b']
        class FakeFrame(object):
            def getname_u(self, i):
                return FakePycode.co_names_w[i]
        pycode = FakePycode()
        frame = FakeFrame()
        init_celldict_cache(pycode)
        assert pycode._celldict_cache

        strategy = ModuleDictStrategy(space)
        storage = strategy.get_empty_storage()
        d = W_ModuleDictObject(space, strategy, storage)

        v1 = strategy.version

        # fill cache
        assert _finditem_with_cache(space, frame, 0, pycode, d, None, None) == None
        assert pycode._celldict_cache[0].version is v1
        assert pycode._celldict_cache[0].value is None
        assert pycode._celldict_cache[1].version is None
        assert pycode._celldict_cache[1].value is None
        # does not need the pycode any more
        assert _finditem_with_cache(space, frame, 0, None, d, v1, None) == None

        # insert a key
        key = "a"
        w_key = self.FakeString(key)
        d.setitem(w_key, 1)
        v2 = strategy.version

        # fill cache
        assert _finditem_with_cache(space, frame, 0, pycode, d, v1, None) == 1
        assert pycode._celldict_cache[0].version is v2
        assert pycode._celldict_cache[0].value == 1
        assert pycode._celldict_cache[1].version is None
        assert pycode._celldict_cache[1].value is None
        # does not need the pycode any more
        assert _finditem_with_cache(space, frame, 0, None, d, v2, 1) == 1

        # overwrite key, now it's a cell
        d.setitem(w_key, 2)
        v3 = strategy.version
        # the cell is cached
        cell = _finditem_with_cache(space, frame, 0, pycode, d, v2, None)
        assert cell.w_value == 2
        assert pycode._celldict_cache[0].version is v3
        assert pycode._celldict_cache[0].value is cell
        # does not need the pycode any more
        assert _finditem_with_cache(space, frame, 0, None, d, v3, 2) == 2

        d.setitem(w_key, 3)
        v4 = strategy.version
        assert v3 is v4
        assert d.getitem(w_key) == 3
        assert d.mstrategy.getdictvalue_no_unwrapping(d, key).w_value == 3

        d.delitem(w_key)
        v5 = strategy.version
        assert v5 is not v4
        assert d.getitem(w_key) is None
        assert d.mstrategy.getdictvalue_no_unwrapping(d, key) is None


class AppTestModuleDict(object):

    def setup_class(cls):
        cls.w_runappdirect = cls.space.wrap(cls.runappdirect)

    def w_impl_used(self, obj):
        if self.runappdirect:
            skip("__repr__ doesn't work on appdirect")
        import __pypy__
        assert "ModuleDictStrategy" in __pypy__.internal_repr(obj)

    def test_check_module_uses_module_dict(self):
        m = type(__builtins__)("abc")
        self.impl_used(m.__dict__)

    def test_key_not_there(self):
        d = type(__builtins__)("abc").__dict__
        raises(KeyError, "d['def']")

    def test_fallback_evil_key(self):
        class F(object):
            def __hash__(self):
                return hash("s")
            def __eq__(self, other):
                return other == "s"
        d = type(__builtins__)("abc").__dict__
        d["s"] = 12
        assert d["s"] == 12
        assert d[F()] == d["s"]

        d = type(__builtins__)("abc").__dict__
        x = d.setdefault("s", 12)
        assert x == 12
        x = d.setdefault(F(), 12)
        assert x == 12

        d = type(__builtins__)("abc").__dict__
        x = d.setdefault(F(), 12)
        assert x == 12

        d = type(__builtins__)("abc").__dict__
        d["s"] = 12
        del d[F()]

        assert "s" not in d
        assert F() not in d

    def test_copy(self):
        m = type(__builtins__)("abc")
        m.s = 12
        m.s = 123 # int cell
        m.x = object
        d = m.__dict__
        d["s"] = 12
        d1 = d.copy()
        assert d1 == {"__name__": "abc", "__doc__": None, "s": 12, "x": object}


class TestModuleDictImplementation(BaseTestRDictImplementation):
    StrategyClass = ModuleDictStrategy
    setdefault_hash_count = 2

class TestDevolvedModuleDictImplementation(BaseTestDevolvedDictImplementation):
    StrategyClass = ModuleDictStrategy
    setdefault_hash_count = 2


class AppTestCellDict(object):

    def setup_class(cls):
        if cls.runappdirect:
            py.test.skip("__repr__ doesn't work on appdirect")
        strategy = ModuleDictStrategy(cls.space)
        storage = strategy.get_empty_storage()
        cls.w_d = W_ModuleDictObject(cls.space, strategy, storage)

    def test_popitem(self):
        import __pypy__

        d = self.d
        assert "ModuleDict" in __pypy__.internal_repr(d)
        raises(KeyError, d.popitem)
        d["a"] = 3
        x = d.popitem()
        assert x == ("a", 3)

    def test_degenerate(self):
        import __pypy__

        d = self.d
        assert "ModuleDict" in __pypy__.internal_repr(d)
        d["a"] = 3
        del d["a"]
        d[object()] = 5
        assert d.values() == [5]

# specialization support
import types, inspect, new

from pypy.tool.sourcetools import valid_identifier, func_with_new_name

def decide_callable(bookkeeper, position, func, args, mono=True, unpacked=False):
    from pypy.objspace.flow.model import SpaceOperation
    from pypy.annotation.model import SomeObject

    key = None
    ismeth, im_class, im_self, func, args = unpack_method(bookkeeper, func, args)


    if position is None or isinstance(position, SpaceOperation):
        spaceop = position
    else:
        fn, block, i = position
        spaceop = block.operations[i]

    key, new_args = bookkeeper.annotator.policy.specialize(bookkeeper, spaceop, func, args, mono)
    if key is not None:
        if isinstance(key, SomeObject): 
            # direct computation
            return None, key
        assert mono, "not-static call to specialized %s" % func
        args = new_args
        if isinstance(key, tuple): 
            # cache specialization
            try:
                newfunc = bookkeeper.cachespecializations[key]
            except KeyError:
                if key[0] is func:
                    postfix = key[1:]
                else:
                    postfix = key
                newfunc = clone(func, postfix)
                if key[0] is func:
                    bookkeeper.cachespecializations[(newfunc,) + postfix] = newfunc
                bookkeeper.cachespecializations[key] = newfunc
        elif isinstance(key, str): 
            # specialization explicit in operation annotation
            postfix = key
            newfunc = clone(func, postfix)
        else: 
            # specialization already retrieved
            newfunc = key
        newfunc._specializedversionof_ = func
        func = newfunc
    
    if unpacked:
        func = func, args
    else:
        func = repack_method(ismeth, im_class, im_self, func)

    return func, key

def default_specialize(funcdesc, args_s):
    argnames, vararg, kwarg = funcdesc.signature
    assert not kwarg, "functions with ** arguments are not supported"
    if vararg:
        from pypy.annotation import model as annmodel
        # calls to *arg functions: create one version per number of args
        assert len(args_s) == len(argnames) + 1
        s_tuple = args_s[-1]
        assert isinstance(s_tuple, annmodel.SomeTuple), (
            "calls f(..., *arg) require 'arg' to be a tuple")
        s_len = s_tuple.len()
        assert s_len.is_constant(), "calls require known number of args"
        nb_extra_args = s_len.const
        return funcdesc.cachedgraph(nb_extra_args)
    else:
        return funcdesc.cachedgraph(None)

# helpers

def unpack_method(bookkeeper, func, args):
    if not hasattr(func, 'im_func'):
        return False, None, None, func, args
    if func.im_self is not None:
        s_self = bookkeeper.immutablevalue(func.im_self)
        args = args.prepend(s_self)        
    # for debugging only, but useful to keep anyway:
    try:
        func.im_func.class_ = func.im_class
    except AttributeError:
        # probably a builtin function, we don't care to preserve
        # class information then
        pass
    return True, func.im_class, func.im_self, func.im_func, args

def repack_method(ismeth, im_class, im_self, func):
    if not ismeth:
        return func
    return new.instancemethod(func, im_self, im_class)


def clone(callb, postfix):
    if not isinstance(postfix, str):
        postfix = '_'.join([getattr(comp, '__name__', str(comp)) for comp in postfix])
    
    name = valid_identifier(callb.__name__ + "__" + postfix)

    if isinstance(callb, types.FunctionType):
        newcallb = func_with_new_name(callb, name)
    elif isinstance(callb, (type, types.ClassType)):
        superclasses = iter(inspect.getmro(callb))
        superclasses.next() # skip callb itself
        for cls in superclasses:
            assert not hasattr(cls, "_annspecialcase_"), "for now specialization only for leaf classes"
                
        newdict = {}
        for attrname,val in callb.__dict__.iteritems():
            if attrname == '_annspecialcase_': # don't copy the marker
                continue
            if isinstance(val, types.FunctionType):
                fname = val.func_name
                fname = "%s_for_%s" % (fname, name)
                newval = func_with_new_name(val, fname)
                # xxx more special cases
            else: 
                newval  = val
            newdict[attrname] = newval

        newcallb = type(callb)(name or callb.__name__, (callb,), newdict)
    else:
        raise Exception, "specializing %r?? why??" % callb

    return newcallb

# ____________________________________________________________________________
# specializations

def memo(funcdesc, arglist_s):
    """NOT_RPYTHON"""
    from pypy.annotation.model import unionof
    # call the function now, and collect possible results
    func = funcdesc.pyobj
    if func is None:
        raise Exception("memo call: no Python function object to call (%r)" %
                        (funcdesc,))
    possible_results = []
    for arglist in possible_arguments(arglist_s):
        result = func(*arglist)
        possible_results.append(funcdesc.bookkeeper.immutablevalue(result))
    return unionof(*possible_results)

def possible_values_of(s):
    from pypy.annotation.model import SomeBool, SomePBC
    if s.is_constant():
        return [s.const]
    elif isinstance(s, SomePBC):
        result = []
        for desc in s.descriptions:
            if desc.pyobj is None:
                raise Exception("memo call with a PBC that has no "
                                "corresponding Python object (%r)" % (desc,))
            result.append(desc.pyobj)
        return result
    elif isinstance(s, SomeBool):
        return [False, True]
    else:
        raise ValueError, "memo call with a non-constant arg %r" % (s,)

def possible_arguments(args):
    # enumerate all tuples (x1,..xn) of concrete values that are contained
    # in a tuple args=(s1,..sn) of SomeXxx.  Requires that each s be either
    # a constant or SomePBC.
    return cartesian_product([possible_values_of(s) for s in args])

def cartesian_product(lstlst):
    if not lstlst:
        yield ()
        return
    for tuple_tail in cartesian_product(lstlst[1:]):
        for value in lstlst[0]:
            yield (value,) + tuple_tail

#def argtypes(bookkeeper, spaceop, func, args, mono):
#    """NOT_RPYTHON"""
#    from pypy.annotation.model import SomeInstance
#    l = []
#    shape, args_w = args.flatten()
#    for x in args_w:
#        if isinstance(x, SomeInstance) and hasattr(x, 'knowntype'):
#            name = "SI_" + x.knowntype.__name__
#        else:
#            name = x.__class__.__name__
#        l.append(name)
#    return func, "__".join(l)

def ctr_location(bookkeeper, mod, spaceop, orig_cls, args, mono):
    """NOT_RPYTHON"""
    from pypy.annotation.model import SomeInstance
    v = spaceop.result
    s_ins = bookkeeper.annotator.binding(v, extquery=True)
    if s_ins is None:
        return "Giving_"+v.name, args
    else:
        assert isinstance(s_ins, SomeInstance)
        cls = s_ins.classdef.cls
        assert issubclass(cls, orig_cls)
        return cls, args

def argvalue(i):
    def specialize_argvalue(funcdesc, args_s):
        key = args_s[i].const
        return funcdesc.cachedgraph(key)        
    return specialize_argvalue

def argtype(i):
    def specialize_argtype(funcdesc, args_s):
        key = args_s[i].knowntype
        return funcdesc.cachedgraph(key)        
    return specialize_argtype

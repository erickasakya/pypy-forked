#include "common_header.h"
#ifdef PYPY_STANDALONE
#include "structdef.h"
#include "forwarddecl.h"
#include "preimpl.h"
#include <src/entrypoint.h>
#include <src/commondefs.h>
#include <src/mem.h>
#include <src/instrument.h>
#include <src/rtyper.h>
#include <src/exception.h>
#include <src/debug_traceback.h>

#include <stdlib.h>
#include <stdio.h>

#ifdef __GNUC__
/* Hack to prevent this function from being inlined.  Helps asmgcc
   because the main() function has often a different prologue/epilogue. */
int pypy_main_function(int argc, char *argv[]) __attribute__((__noinline__));
#endif

# ifdef PYPY_USE_ASMGCC
#  include "structdef.h"
#  include "forwarddecl.h"
# endif

int pypy_main_function(int argc, char *argv[])
{
    char *errmsg;
    int i, exitcode;
    RPyListOfString *list;
    char *saved_r15;

#ifdef PYPY_USE_ASMGCC
    pypy_g_rpython_rtyper_lltypesystem_rffi_StackCounter.sc_inst_stacks_counter++;
#endif
    saved_r15 = pypy_r15;
    //pypy_asm_stack_bottom();
#ifdef PYPY_X86_CHECK_SSE2_DEFINED
    pypy_r15 = (char *)-1;
    pypy_x86_check_sse2();
#endif
    pypy_r15 = (char *)-1;
    instrument_setup();

#ifndef MS_WINDOWS
    /* this message does no longer apply to win64 :-) */
    if (sizeof(void*) != SIZEOF_LONG) {
        errmsg = "only support platforms where sizeof(void*) == sizeof(long),"
                 " for now";
        goto error;
    }
#endif

    pypy_r15 = (char *)-1;
    errmsg = RPython_StartupCode();
    if (errmsg) goto error;

    pypy_r15 = (char *)-1;
    list = _RPyListOfString_New(argc);
    if (RPyExceptionOccurred()) goto memory_out;
    for (i=0; i<argc; i++) {
        pypy_r15 = (char *)-1;
        RPyString *s = RPyString_FromString(argv[i]);
        if (RPyExceptionOccurred()) goto memory_out;
        pypy_r15 = (char *)-1;
        _RPyListOfString_SetItem(list, i, s);
    }

    pypy_r15 = (char *)-1;
    exitcode = STANDALONE_ENTRY_POINT(list);

    pypy_r15 = (char *)-1;
    pypy_debug_alloc_results();

    pypy_r15 = (char *)-1;
    if (RPyExceptionOccurred()) {
        /* print the RPython traceback */
        pypy_debug_catch_fatal_exception();
    }

    pypy_r15 = (char *)-1;
    pypy_malloc_counters_results();

    pypy_r15 = saved_r15;
    return exitcode;

 memory_out:
    errmsg = "out of memory";
 error:
    fprintf(stderr, "Fatal error during initialization: %s\n", errmsg);
    abort();
    return 1;   /* not actually reachable */
}

int PYPY_MAIN_FUNCTION(int argc, char *argv[])
{
    return pypy_main_function(argc, argv);
}

#endif  /* PYPY_STANDALONE */

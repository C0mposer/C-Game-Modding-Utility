#ifndef _NEWLIB_STDIO_H
#define _NEWLIB_STDIO_H

/* Internal locking macros, used to protect stdio functions.  In the
   general case, expand to nothing. */
#if !defined(_flockfile)
#  if !defined(__SINGLE_THREAD__)
#    define _flockfile(fp) { ((fp)->_flags&__SSTR) ? 0 : __flockfile(fp); }
     extern void __flockfile(FILE *fp);
#  else
#    define _flockfile(fp)
#  endif
#endif /* __SINGLE_THREAD__ */

#if !defined(_funlockfile)
#  if !defined(__SINGLE_THREAD__)
#    define _funlockfile(fp) { ((fp)->_flags&__SSTR) ? 0 : __funlockfile(fp); }
     extern void __funlockfile(FILE *fp);
#  else
#    define _funlockfile(fp)
#  endif
#endif /* __SINGLE_THREAD__ */

#endif /* _NEWLIB_STDIO_H */


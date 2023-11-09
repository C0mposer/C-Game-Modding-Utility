#ifndef __SYS_LOCK_H__
#define __SYS_LOCK_H__

typedef int _LOCK_T;
typedef int _LOCK_RECURSIVE_T;

#define __LOCK_INIT(CLASS,NAME)				CLASS _LOCK_T NAME = 0
#define __LOCK_INIT_RECURSIVE(CLASS,NAME)	CLASS _LOCK_RECURSIVE_T NAME = 0

#define __lock_init(NAME) \
	__libc_lock_init(&(NAME),0)

#define __lock_init_recursive(NAME) \
	__libc_lock_init(&(NAME),1)

#define __lock_close(NAME) \
	__libc_lock_close(&(NAME))

#define __lock_close_recursive(NAME) \
	__libc_lock_close(&(NAME))

#define __lock_acquire(NAME) \
	if(!(NAME)) __libc_lock_init(&(NAME),0);	\
	__libc_lock_acquire(&(NAME))

#define __lock_acquire_recursive(NAME) \
	if(!(NAME)) __libc_lock_init(&(NAME),1);	\
	__libc_lock_acquire(&(NAME))

#define __lock_try_acquire(NAME) \
	if(!(NAME)) __libc_lock_init(&(NAME),0);	\
	__libc_lock_try_acquire(&(NAME))

#define __lock_try_acquire_recursive(NAME) \
	if(!(NAME)) __libc_lock_init(&(NAME),1);	\
	__libc_lock_try_acquire(&(NAME))

#define __lock_release(NAME) \
	__libc_lock_release(&(NAME))

#define __lock_release_recursive(NAME) \
	__libc_lock_release(&(NAME))


extern int __libc_lock_init(int*,int);
extern int __libc_lock_close(int*);
extern int __libc_lock_acquire(int*);
extern int __libc_lock_try_acquire(int*);
extern int __libc_lock_release(int*);

#endif /* __SYS_LOCK_H__ */

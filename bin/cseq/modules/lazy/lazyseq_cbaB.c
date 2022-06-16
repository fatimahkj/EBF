unsigned int __cs_active_thread[THREADS+1]={1};
unsigned int __cs_pc[THREADS+1];
unsigned int __cs_pc_cs[THREADS+1];
unsigned int __cs_last_thread;
unsigned int __cs_thread_lines[] = {<insert-threadsizes-here>};

void __cs_init_scalar(void *__cs_var, unsigned int __cs_size) {
	if (__cs_size == sizeof(int))
		*(int *)__cs_var = __CSEQ_nondet_int();
	else {
		__cs_var = malloc(__cs_size);
	}
}

void __CSEQ_message(char *__cs_message) { ; }

typedef int __cs_t;

void *__cs_threadargs[THREADS+1];

int __cs_create(__cs_t *__cs_new_thread_id, void *__cs_attr, void *(*__cs_t)(void*), void *__cs_arg, int __cs_threadID) {
	if (__cs_threadID > THREADS) return 0;
	*__cs_new_thread_id = __cs_threadID;
	__cs_active_thread[__cs_threadID] = 1;
	__cs_threadargs[__cs_threadID] = __cs_arg;
	__CSEQ_message("thread spawned");
	return 0;
}

int __cs_join(__cs_t __cs_id, void **__cs_value_ptr) {
	__CSEQ_assume(__cs_pc[__cs_id] == __cs_thread_lines[__cs_id]);
	return 0;
}

int __cs_exit(void *__cs_value_ptr) { return 0; }

int __cs_self(void) { return 1; }

typedef int __cs_mutex_t;

int __cs_mutex_init (__cs_mutex_t *__cs_m, int __cs_val) {
	*__cs_m = -1;
	return 0;
}

int __cs_mutex_destroy(__cs_mutex_t *__cs_mutex_to_destroy) {
	__CSEQ_assertext(*__cs_mutex_to_destroy!=0,"attempt to destroy an uninitialized mutex");
	__CSEQ_assertext(*__cs_mutex_to_destroy!=-2,"attempt to destroy a previously destroyed mutex");
	__CSEQ_assertext(*__cs_mutex_to_destroy==-1,"attempt to destroy a locked mutex");
	*__cs_mutex_to_destroy = -2;
	__CSEQ_message("lock destroyed");
	return 0;
}

int __cs_mutex_lock(__cs_mutex_t *__cs_mutex_to_lock, unsigned int __cs_thread_index) {
	__CSEQ_assertext(*__cs_mutex_to_lock!=0,"attempt to lock an uninitialized mutex");
	__CSEQ_assertext(*__cs_mutex_to_lock!=-2,"attempt to lock a destroyed mutex");
	__CSEQ_assume(*__cs_mutex_to_lock==-1);
	*__cs_mutex_to_lock = __cs_thread_index+1;
	__CSEQ_message("lock acquired");
	return 0;
}

int __cs_mutex_unlock(__cs_mutex_t *__cs_mutex_to_unlock, unsigned int __cs_thread_index) {
	__CSEQ_assertext(*__cs_mutex_to_unlock!=0,"attempt to unlock an uninitialized mutex");
	__CSEQ_assertext(*__cs_mutex_to_unlock!=-2,"attempt to unlock a destroyed mutex");
	__CSEQ_assume(*__cs_mutex_to_unlock==(__cs_thread_index+1));
	*__cs_mutex_to_unlock = -1;
	__CSEQ_message("lock released");
	return 0;
}

typedef int __cs_cond_t;

int __cs_cond_init(__cs_cond_t *__cs_cond_to_init, void *__cs_attr) {
	*__cs_cond_to_init = -1;
	return 0;
}

int __cs_cond_destroy(__cs_cond_t *__cs_cond_to_destroy) {
	*__cs_cond_to_destroy = -2;
	return 0;
}

int __cs_cond_wait_1(__cs_cond_t *__cs_cond_to_wait_for, __cs_mutex_t *__cs_m, unsigned int __cs_thread_index) {
	__CSEQ_assertext(*__cs_cond_to_wait_for!=0,"attempt to use an uninitialized conditional variable");
	__CSEQ_assertext(*__cs_cond_to_wait_for!=-2,"attempt to use a destroyed conditional variable");
	__cs_mutex_unlock(__cs_m, __cs_thread_index);
	return 0;
}

int __cs_cond_wait_2(__cs_cond_t *__cs_cond_to_wait_for, __cs_mutex_t *__cs_m, unsigned int __cs_thread_index) {
	__CSEQ_assume(*__cs_cond_to_wait_for == 1);
	__cs_mutex_lock(__cs_m, __cs_thread_index);
	return 0;
}

int __cs_cond_signal(__cs_cond_t *__cs_cond_to_signal) {
	*__cs_cond_to_signal = 1;
	__CSEQ_message("conditional variable signal");
	return 0;
}

int __cs_cond_broadcast(__cs_cond_t *__cs_cond_to_broadcast) {
	*__cs_cond_to_broadcast = 1;
	__CSEQ_message("conditional variable broadcast");
	return 0;
}

typedef struct __cs_barrier_t{
	unsigned int init;
	unsigned int current;
} __cs_barrier_t;

int __cs_barrier_init(__cs_barrier_t *__cs_barrier_to_init, void * __cs_attr, unsigned int count){
	__CSEQ_assertext(count > 0, "count must be greater than 0");
	__cs_barrier_to_init->current = count;
	__cs_barrier_to_init->init = count;
	return 0;
}

int __cs_barrier_destroy(__cs_barrier_t *__cs_barrier_to_destroy) {
	__cs_barrier_to_destroy->init = -1;
	__cs_barrier_to_destroy->current = -1;
	return 0;
}


int __cs_barrier_wait_1(__cs_barrier_t *__cs_barrier_to_wait){
	__CSEQ_assertext(__cs_barrier_to_wait->init > 0, "attempt to use an uninitialized barrier variable");
	__cs_barrier_to_wait->current--;
	return 0;
}

int __cs_barrier_wait_2(__cs_barrier_t *__cs_barrier_to_wait){
	__CSEQ_assertext(__cs_barrier_to_wait->init > 0, "attempt to use an uninitialized barrier variable");
	__CSEQ_assume(__cs_barrier_to_wait->current == 0);
	__cs_barrier_to_wait->current = __cs_barrier_to_wait->init;
	return 0;
}

typedef int __cs_attr_t;
struct sched_param {
   int sched_priority;
};
int   __cs_attr_init(__cs_attr_t *) { return 0;}
int   __cs_attr_destroy(__cs_attr_t *) { return 0;}
int   __cs_attr_getdetachstate(const __cs_attr_t *, int * s) { return 0;}
int   __cs_attr_getguardsize(const __cs_attr_t *, unsigned int * s) { return 0;}
int   __cs_attr_getinheritsched(const __cs_attr_t *, int * s) { return 0;}
int   __cs_attr_getschedparam(const __cs_attr_t *, struct sched_param * s) { return 0;}
int   __cs_attr_getschedpolicy(const __cs_attr_t *, int * s) { return 0;}
int   __cs_attr_getscope(const __cs_attr_t *, int * s) { return 0;}
int   __cs_attr_getstackaddr(const __cs_attr_t *, void ** s) { return 0;}
int   __cs_attr_getstacksize(const __cs_attr_t *, unsigned int *s) { return 0;}
int   __cs_attr_setdetachstate(__cs_attr_t *, int s) { return 0;}
int   __cs_attr_setguardsize(__cs_attr_t *, unsigned int s) { return 0;}
int   __cs_attr_setinheritsched(__cs_attr_t *, int s) { return 0;}
int   __cs_attr_setschedparam(__cs_attr_t *, const struct sched_param * s) { return 0;}
int   __cs_attr_setschedpolicy(__cs_attr_t *, int s) { return 0;}
int   __cs_attr_setscope(__cs_attr_t *, int s) { return 0;}
int   __cs_attr_setstackaddr(__cs_attr_t *, void * s) { return 0;}
int   __cs_attr_setstacksize(__cs_attr_t *, unsigned int s) { return 0;}

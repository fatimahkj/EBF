#include <stdlib.h>

#include <time.h>

#include <stdio.h>

size_t active_threads;

void add_thread(uint thread_id) {
    active_threads++;
}

void join_thread(uint thread_id) {
    active_threads--;
}

void _delay_function(int i)
{
    if(!active_threads) return;
    
    struct timespec r, rem;
    
    r.tv_sec = i;
    
    r.tv_nsec = random() % 1000000000/10000;
    
    //printf("Waiting %ld s %ld ns\n", r.tv_sec, r.tv_nsec);
    
   nanosleep(&r, &rem);
    
}

/* Get target function name: https://github.com/hbgit/Map2Check/blob/master/modules/backend/pass/TargetPass.cpp#L36-L51
 * Look for `targetFunctionName` e.g. pthread_create and pthread_join
 */

// Iterate over all instructions of a function: https://github.com/hbgit/Map2Check/blob/master/modules/backend/pass/TargetPass.cpp#L25-L33

/* Instrument a function with arguments of a function call: https://github.com/hbgit/Map2Check/blob/master/modules/backend/pass/MemoryTrackPass.cpp#L107-L119
 * This is for extracting the size of a malloc call with a cast operation as well.
 */

/*        nanosleep() suspends the execution of the calling thread until either
 at least the time specified in *req has elapsed, or the delivery of a
 signal that triggers the invocation of a handler in the calling
 thread or that terminates the process.*/

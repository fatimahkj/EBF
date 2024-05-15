#include <stdlib.h>
#include <time.h>
#include <stdio.h>
#include <pthread.h>
#include "myDelaylib.h"
extern void __VERIFIER_assume(int expr);
extern pthread_t Global_refrence;
extern unsigned int __VERIFIER_delay_uint();
extern unsigned int __VERIFIER_nondet_uint();
extern pthread_mutex_t __VERIFIER_EBF_mutex;
extern void __VERIFIER_atomic_end();

size_t active_threads;
pthread_mutex_t __VERIFIER_EBF_lock_thread = PTHREAD_MUTEX_INITIALIZER;

void add_thread()
{
  pthread_mutex_lock(&__VERIFIER_EBF_lock_thread);
  active_threads++;
  pthread_mutex_unlock(&__VERIFIER_EBF_lock_thread);
}

void join_thread()
{
  pthread_mutex_lock(&__VERIFIER_EBF_lock_thread);
  active_threads--;
  pthread_mutex_unlock(&__VERIFIER_EBF_lock_thread);
}

void __Initialize_random()
{
  static char initialized = 0;
  time_t t;
  if (!initialized)
    srand((unsigned)time(&t));
  initialized = 1;
}

int __VERIFIER_nondet_delay()
{
  __Initialize_random();
  return rand();
}

struct timespec createTimer(unsigned second, unsigned nsecond)
{
  struct timespec wait;
  int ret;
  wait.tv_sec = second;
  wait.tv_nsec = nsecond;
  return wait;
}

void _delay_function()
{ 
  __VERIFIER_assume(active_threads < 1000);
  __VERIFIER_assume(__VERIFIER_nondet_delay() % 10000);
  /**=-=-===-=-==-*=-=-==-*=-=-==-*=-=-==-*=-=-==-*-*/
  /**Fix the starvation problem */
  struct timespec wait = createTimer(15,0);

  while (pthread_mutex_timedlock(&__VERIFIER_EBF_mutex, &wait ))
 {   printf("we are inside\n");
      __VERIFIER_assume(__VERIFIER_nondet_delay() % 10000);
  }
      printf("we are outside\n");

     pthread_mutex_unlock(&__VERIFIER_EBF_mutex);
    
  /**=-=-===-=-==-*=-=-==-*=-=-==-*=-=-==-*=-=-==-*-*/

  struct timespec r=createTimer(0,(__VERIFIER_nondet_delay() % 100) * 1000);
  nanosleep(&r, NULL);
}
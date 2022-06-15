#include <time.h>
#include<pthread.h>


pthread_mutex_t __VERIFIER_EBF_mutex;




void __VERIFIER_atomic_begin()
{
     pthread_mutex_lock(&__VERIFIER_EBF_mutex);

}

void __VERIFIER_atomic_end()
{
  pthread_mutex_unlock(&__VERIFIER_EBF_mutex);

}


//void _delay_function()
//{
   // if(!active_threads) return;
    
    //struct timespec r, rem;
    
   // r.tv_sec = 2;
    
   // r.tv_nsec = 2* 1000000000;

    
   // printf("Waiting %ld s %ld ns\n", r.tv_sec, r.tv_nsec);
  // __VERIFIER_atomic_begin();
   //nanosleep(&r, &rem);
   //__VERIFIER_atomic_end();
    
//}


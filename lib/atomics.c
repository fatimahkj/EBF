
#include <pthread.h>
#include <errno.h>

pthread_mutex_t mutex;

int __VERIFIER_atomic_begin()
{
    pthread_mutex_lock(&mutex);
    return 0;
}

int __VERIFIER_atomic_end()
{
    pthread_mutex_unlock(&mutex);
    return 0;
}

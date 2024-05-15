#include <stdio.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <stdint.h>
#include <pthread.h>
#include <signal.h>
#include <errno.h>
#include <sys/types.h>
#include <unistd.h>
#include <semaphore.h>
#include <assert.h>
#include <sys/time.h>
#include <sys/resource.h>
#include "myFunctionslib.h"
#define MAX_STR_SIZE 30
#define NONDET_FILE_NAME_PREFIX "nondetInputs"
#define SEED_FILE_NAME_PREFIX "witnessInfoAFL"
FILE *Nondet = NULL;
FILE *winfo = NULL;
char nondetFileName[MAX_STR_SIZE];
char seedFileName[MAX_STR_SIZE];
int currentProccess;
pthread_mutex_t __VERIFIER_EBF_mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_mutex_t __EBF_mutex_var = PTHREAD_MUTEX_INITIALIZER;


void clean_memory(void);
void openOut(void) __attribute__((constructor));
void closeOut(void) __attribute__((destructor));
 void clean_memory(void) __attribute__((destructor));

void openOut(void)
{
  // Get Unique ID for the file
  currentProccess = getpid();
  sprintf(nondetFileName, "%s-%d", NONDET_FILE_NAME_PREFIX, currentProccess);
  sprintf(seedFileName, "%s-%d", SEED_FILE_NAME_PREFIX, currentProccess);
  Nondet = fopen(nondetFileName, "w");

  if (Nondet == NULL)
  {
    printf(" Unable to open the outfile to write %s\n", nondetFileName);
    exit(1);
  }
  winfo = fopen(seedFileName, "w");
  if (winfo == NULL)
  {
    printf(" Unable to open the outfile to write %s\n", seedFileName);
    exit(1);
  }
  fprintf(Nondet, "BEGIN\n");
  fprintf(winfo, "BEGIN\n");
}

/** This function is instrumented before any reached error in the PUT and it will close the file created and abort
 * In this case the fuzzer will consider it as a crash */
void EBF_closing()
{
  printf("we are reaching an error");
  fprintf(Nondet, "REACH_ERROR END\n");
  fprintf(winfo, "REACH_ERROR END\n");
  fflush(Nondet);
  fflush(winfo);
  fclose(Nondet);
  fclose(winfo);
  clean_memory();
  abort();
}

/** This function is destructor which will close the files normally
 * when it exit normally.
 */
void closeOut(void)
{
  printf("Closing files\n");
  fflush(Nondet);
  fflush(winfo);
  if (Nondet != NULL)
  {
    fprintf(Nondet, "END\n");
    fclose(Nondet);
    Nondet = NULL;
  }
  if (winfo != NULL)
  {
    fprintf(winfo, "END Information\n");
    fclose(winfo);
    winfo = NULL;
  }
}

/** This function is instrumented before any abort in the PUT and normally exit.
So, the fuzzer will not consider it as a crash*/
void __VERIFIER_exit()
{
  exit(0);
}

void __VERIFIER_assume(int expr)

{
  if (!expr)
  {
    __VERIFIER_exit();
  }
}

/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/
/** Beginning of SV-COMP functions
/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/
/** This function reads integer from stdin and print the values in seedValue file */
int __VERIFIER_nondet_int()
{
  printf("\n[__VERIFIER_nondet_int]\n");
  int val;
  //fscanf(stdin,"%d",&val);
  fread(&val, sizeof(int), 1, stdin);
  fprintf(Nondet, "%d\n", val);
  return val;
}

unsigned int __VERIFIER_nondet_uint()
{
  printf("\n[__VERIFIER_nondet_uint]\n");
  unsigned int val;
  // fscanf(stdin,"%u",&val);
  fread(&val, sizeof(unsigned int), 1, stdin);
  fprintf(Nondet, "%u\n", val);
  return val;
}

/** This function reads char from stdin and print the values in seedValue file (will only read one char per time!)*/
char __VERIFIER_nondet_char()
{
  printf("\n[__VERIFIER_nondet_char]\n");
  char str;
  // fscanf(stdin, "%c", &str);
  fread(&str, sizeof(unsigned char), 1, stdin);
  fprintf(Nondet, "%c\n", str);
  return str;
}

/** This function return bool number reads from stdin 0 or 1 and print the values in seedValue file */
_Bool __VERIFIER_nondet_bool()
{
  printf("\n[__VERIFIER_nondet_bool]\n");
  char val;
  fread(&val, sizeof(char), 1, stdin);
  //fscanf(stdin, "%d", &val);
  fprintf(Nondet, "%c\n", val % 2);
  return val % 2;
}

/** This function will return float number reads from stdin and print the values in seedValue file
**TODO: fuzzer took 5 min to find 2.5!* For SV-COMP 2022, all the concurrency benchmarks does not have this function */

float __VERIFIER_nondet_float()
{
  printf("\n[__VERIFIER_nondet_float\n");
  float val;
  // fscanf(stdin, "%f", &val);
  fread(&val, sizeof(float), 1, stdin);
  fprintf(Nondet, "%f\n", val);
  return val;
}

/** This function will return double number reads from stdin and print the values in seedValue file
**TODO:  fuzzer will only scan the first half and any values after. will be 0 !*/
double __VERIFIER_nondet_double()
{
  printf("\n[__VERIFIER_nondet_double\n");
  double val;
  // fscanf(stdin, "%lf", &val);
  fread(&val, sizeof(double), 1, stdin);
  fprintf(Nondet, "%lf\n", val);
  return val;
}

/** This function will return long number reads from stdin and print the values in seedValue file
 */
long int __VERIFIER_nondet_long()
{
  printf("\n[__VERIFIER_nondet_long\n");
  long int val;
  // fscanf(stdin, "%ld ", &val);
  fread(&val, sizeof(long int), 1, stdin);
  fprintf(Nondet, "%ld\n", val);
  return val;
}

/** This function will return unsigned long number reads from stdin and print the values in seedValue file
 */
unsigned long __VERIFIER_nondet_ulong()
{
  printf("\n[__VERIFIER_nondet_unsigned_long\n");
  unsigned long int val;
  fread(&val, sizeof(unsigned long int), 1, stdin);
  //fscanf(stdin, "%lu ", &val);
  fprintf(Nondet, "%lu\n", val);
  return val;
}

/** This function will return short int  number reads from stdin and print the values in seedValue file */

short __VERIFIER_nondet_short()
{
  printf("\n[__VERIFIER_nondet_short]\n");
  short val;
  fread(&val, sizeof(short), 1, stdin);
  //fscanf(stdin, "%hd ", &val);
  fprintf(Nondet, "%hd\n", val);
  return val;
}

/** This function reads unsigned char from stdin and print the values in seedValue file (will only read one char per time!)*/
unsigned char __VERIFIER_nondet_uchar()
{
  printf("\n[__VERIFIER_nondet_uchar]\n");
  unsigned char str;
  fread(&str, sizeof(unsigned char), 1, stdin);
  //fscanf(stdin, "%c", &str);
   fprintf(Nondet, "%c\n", str);
  return str;
}

/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/
/** END of SV-COMP functions
/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/

/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/
/** Start dynamic Data structure to print the variable name with its value for the same address 
/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/

// Data Types
/** 
 * DEFINE A STRUCT with variable name, function and address of the variable
*/
typedef struct list_item
{
  char name[MAX_STR_SIZE];
  char function[MAX_STR_SIZE];
  void *ptr;
} LIST_ITEM;
/**
 * Define a Linked list struct
*/
typedef struct list
{
  struct list *next;
  LIST_ITEM *item;
} LIST;

// Globals
/**
 * This variable to store the information
*/
LIST *global_list = NULL;

/**
 * This function first will tranvers the list looking for an address,returning the variable name (if found ) or NULL. if the current item matches the
 * address we are searching for, we return the name. Lastly, if its not Null and not the
 * address we are looking for we are recursevly search for the next element 
*/
const char *get_var_name_from_list(LIST *L, void *ptr)
{
  pthread_mutex_lock(&__EBF_mutex_var);
  while (L != NULL)
  {
    if (L->item->ptr == ptr){
       pthread_mutex_unlock(&__EBF_mutex_var);
       return L->item->name;
    }
    L = L->next; 
  }
  pthread_mutex_unlock(&__EBF_mutex_var);
  return NULL;
}

/**
 * We allocate memory and initialize it ans return the address
*/
LIST_ITEM *new_list_node(const char *name, const char *function_name, void *ptr)
{
  LIST_ITEM *item = (LIST_ITEM *)malloc(sizeof(LIST_ITEM));
  strncpy(item->name, name, MAX_STR_SIZE);
  strncpy(item->function, function_name, MAX_STR_SIZE);
  item->ptr = ptr;
  return item;
}

#ifndef NDEBUG
void print_list_item(LIST_ITEM *item)
{
 //fprintf(fpp, "Adding %s in address: %p\n", item->name, item->ptr);
}
#else
void print_list_item(LIST_ITEM *item)
{
}
#endif


/**
 * we allocate and initialize the list with node and return the allocated list
*/
LIST *intialize_list(const char *name, const char *function_name, void *ptr)
{
  LIST *result = (LIST *)malloc(sizeof(LIST *));
  result->next = NULL;
  result->item = new_list_node(name, function_name, ptr);
  print_list_item(result->item);
  return result;
}

/**
 * Go through the list an free the dynamic allocation
*/
void free_list(LIST *L)
{
  while (L != NULL)
  {
    LIST *aux = L;
    L = L->next;
    free(aux->item);
    free(aux);
  }
}

/**
 * add a new node to the list with given values
*/
void append_to_list(const char *name, const char *function_name, void *ptr)
{

  if (name == NULL || name[0]=='\0')
   return;
   pthread_mutex_lock(&__EBF_mutex_var);
  if (global_list == NULL)
  {
    global_list = intialize_list(name, function_name, ptr);
    pthread_mutex_unlock(&__EBF_mutex_var);
    return;
  }
  LIST *aux = global_list;
  while (aux->next != NULL)
    aux = aux->next;
  aux->next = intialize_list(name, function_name, ptr);
pthread_mutex_unlock(&__EBF_mutex_var);
}

// Clean Up
void clean_memory(void)
{
    free_list(global_list);
}

/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/
/** END dynamic Data structure
/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/


/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/
/** witness information collection
/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/

/** This function will save the 1) -a- the variable address, 2) -b- line number, 3)-function_name-, 4) -ptr- value 5) thread id
The only difference is the type of the pointer.*/

void EBF_add_store_pointer(int *a, int b, int *function_name, int ptr)
{
  const char *variable_name=get_var_name_from_list(global_list, a);
  if (variable_name!= NULL){
  fprintf(winfo, "Setting variable: %s in Line number %d with value: %d running from thread: %ld in function: %s with address: %p\n", variable_name, b, ptr, pthread_self(), (char *)function_name, a);
  }
}

void EBF_add_store_pointer_fp(int *a, int b, int *function_name, double ptr)
{
  const char *variable_name=get_var_name_from_list(global_list, a);
  if (variable_name!= NULL){
  fprintf(winfo, "Setting variable: %s in Line number %d with value: %f running from thread: %ld in function: %s with address: %p\n", variable_name, b, ptr, pthread_self(), (char *)function_name, a);
  }
}

void EBF_add_store_pointer_ptr(int *a, int b, int *function_name, void *ptr) // variable_address
  {
  const char *variable_name=get_var_name_from_list(global_list, a);
  if (variable_name!= NULL){
  fprintf(winfo, "Setting variable: %s in Line number %d with value: %p running from thread: %ld in function: %s with address: %p\n", variable_name, b, ptr, pthread_self(), (char *)function_name, a);
  }
}
void EBF_alloca(const char *var_name, const char *function_name, void *ptr)
{
  //fprintf(winfo, "Allocating variable: %s, function: %s, address %p\n", var_name, function_name, ptr);
  append_to_list(var_name, function_name, ptr);
}

/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/
/** END of witness information collection
/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/

/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/
/** Atomic Functions
/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/

void __VERIFIER_atomic_begin(void)
{
  pthread_mutex_lock(&__VERIFIER_EBF_mutex);
}

void __VERIFIER_atomic_end(void)
{
  pthread_mutex_unlock(&__VERIFIER_EBF_mutex);
}

/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/
/** END of Atomic Functions
/**=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-*/




/**
 * If this function reached it will exit the program and report a crash
*/
void EBF_closing();


/** 
 * This function will exit the program normally.
*/
void __VERIFIER_exit();


/**
 * This function will exit the program if the condition is not true.
*/
void __VERIFIER_assume(int expr);


/**
 * This function will generate an integer number from stdin and write the value in a file.
*/
int __VERIFIER_nondet_int();


/**
 * This function will generate an unsigned integer number from stdin and write the value in a file.
*/
unsigned int __VERIFIER_nondet_uint();


/**
 * This function will generate a char string from stdin and write the value in a file.
*/
char __VERIFIER_nondet_char();


/**
 * This function will generate a boolean from stdin and write the value in a file.
*/
_Bool __VERIFIER_nondet_bool();


/**
 * This function will generate a float number from stdin and write the value in a file.
*/
float __VERIFIER_nondet_float();


/**
 * This function will generate a double number from stdin and write the value in a file.
*/
double __VERIFIER_nondet_double();


/**
 * This function will generate a long number from stdin and write the value in a file.
*/
long int __VERIFIER_nondet_long();


/**
 * This function will generate unsigned long number from stdin and write the value in a file.
*/
unsigned long  __VERIFIER_nondet_ulong();


/**
 * This function will generate a short number from stdin and write the value in a file.
*/
short __VERIFIER_nondet_short();


/**
 * This function will generate unsigned char string from stdin and write the value in a file.
*/
unsigned char __VERIFIER_nondet_uchar();

/**
 * This function will get some arguments' value and save them in file.
 * It will get 1) -a- the variable address, 2) -b- line number, 3)-function_name-, 4) -ptr- value 5) thread id 
 *  The only difference is the type of the pointer.
*/
void EBF_add_store_pointer(int *a, int b, int *function_name, int ptr);
void EBF_add_store_pointer_fp(int *a, int b, int *function_name, double ptr);
void EBF_add_store_pointer_ptr(int *a, int b, int *function_name, void *ptr);


/**
 * This function will get some arguments' value and save them in file.
 * Specifically, it will collect the variable name. 
*/
void EBF_alloca(const char *var_name, const char *function_name, void *ptr);


/**
 * This function will get the thread ID which acquire the lock. Then use pthread_lock to lock the block.
*/
void __VERIFIER_atomic_begin(void);


/**
 * This function will set the thread ID back to -1. Then use pthread_unlock to unlock the block.
*/
void __VERIFIER_atomic_end(void);




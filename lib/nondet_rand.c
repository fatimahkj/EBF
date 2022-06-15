#include <time.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>

void __Initialize_random(){
static char initialized =0;
if (!initialized )srand((time(0)));

initialized =1;

}

int __VERIFIER_nondet_int(){
__Initialize_random();
int max=sizeof(int);
int r = rand()%max;
return r;
//abort();

}


unsigned int __VERIFIER_nondet_uint(){
//unsigned int r;
  // __Initialize_random();
   //r = rand() % sizeof(unsigned int);
  //return r;
  abort();
}

void __VERIFIER_assume(int cont){
if (!cont){
abort();
}
}

char __VERIFIER_nondet_char()
{
abort();
//__Initialize_random();
//char a =(rand()%(90-65))+65; //65 is ASCII for capital A, 90 is ASCII for capital Z
//printf("char is %c",a);
//return a;

}

double __VERIFIER_nondet_double(){
abort();
}

float __VERIFIER_nondet_float(){

abort();
}


_Bool __VERIFIER_nondet_bool()
{
  return __VERIFIER_nondet_char();
}


long __VERIFIER_nondet_long(){

abort();
}


short __VERIFIER_nondet_short(){

abort();
}


uint32_t __VERIFIER_nondet_U32(){
abort();
}



unsigned char __VERIFIER_nondet_uchar()
{

abort();

}



unsigned long __VERIFIER_nondet_ulong()
{
abort();
}


unsigned short __VERIFIER_nondet_ushort()
{
abort();
}


unsigned short __VERIFIER_nondet_size_t()
{

abort();
}


unsigned long __VERIFIER_nondet_loff_t()
{
  return __VERIFIER_nondet_ulong();
}

unsigned long __VERIFIER_nondet_sector_t()
{
  return __VERIFIER_nondet_ulong();
}
char *__VERIFIER_nondet_pchar()
{
abort();
}


void *__VERIFIER_nondet_pointer()
{
abort();
}

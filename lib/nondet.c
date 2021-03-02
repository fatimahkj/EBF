#include<stdio.h>
#include<stdlib.h>
#include<stdint.h>
#include<string.h>
#include<limits.h>
#include<unistd.h>
#include<stdbool.h>
#include<fcntl.h>
#include <pthread.h>

typedef uint8_t  u8;
typedef uint16_t u16;
typedef uint32_t u32;

typedef int8_t   s8;
typedef int16_t  s16;
typedef int32_t  s32;
typedef int64_t  s64;
typedef unsigned long sector_t;

#ifdef __x86_64__
typedef unsigned long long u64;
#else
typedef uint64_t u64;
#endif /* ^__x86_64__ */

#define likely(_x)   __builtin_expect(!!(_x), 1)
#define unlikely(_x)  __builtin_expect(!!(_x), 0)
#define RESEED_RNG  10000

/* Variables used in the routine */

#define CHAR_UCHAR_BYTESIZE 1
#define BOOL_BYTESIZE 1
#define SHORT_USHORT_BYTESIZE 2
#define INT_UINT_BYTESIZE 4
#define LONG_ULONG_BYTESIZE 4
#define LONGLONG_ULONGLONG_BYTESIZE 8

#define FLOAT_BYTESIZE 4
#define DOUBLE_BYTESIZE 8

#define POINTER_BYTESIZE 8

FILE *fp  = NULL;
FILE *rangeAnalP = NULL ;
short state = -1;
short rangeAnalState = -1 ;
int   ival = 0;
static int dev_urandom_fd = -1;
static int rand_cnt;
static int byteTracker = -1 ;
char *default_fname = "t1_default";
char *rangeAnalDumpFile = "rangeAnalDumpFile.txt" ;

void openOut(void)  __attribute__ ((constructor));
void closeOut(void) __attribute__ ((destructor));

void openOut(void){
  char *outFileName = getenv("SVCOMP_SEED_FILENAME");
#ifdef DEBUG
   
  printf("Entered the open file ....\n");
#endif
      //printf("LINE: %u", __LINE__);
  if(outFileName == NULL)
    outFileName = default_fname;
  //printf("LINE: %u", __LINE__);
  printf("its an empty %s", outFileName);
  fp = fopen(outFileName,"wb");
  if(fp == NULL){
      //  printf("LINE: %u", __LINE__);
#ifdef DEBUG
    printf(" Unable to open the outfile to write %s\n",outFileName);
#endif
  }else{
        //printf("LINE: %u\n", __LINE__);
    dev_urandom_fd = open("/dev/urandom", O_RDONLY);
    if (dev_urandom_fd < 0){
     // printf("LINE: %u\n", __LINE__);
#ifdef DEBUG
      printf("Unable to open /dev/urandom");
#endif
      abort();
    }
   // printf("LINE: %u\n", __LINE__);
    state = 0;
  }

  rangeAnalP = fopen(rangeAnalDumpFile,"wb") ;
  //printf("LINE: %u\n", __LINE__);
  if(rangeAnalP == NULL){
#ifdef DEBUG
	 printf(" Unable to open the Range Analysis file to write %s\n", rangeAnalP);
#endif
	 return ;
  }
  else
  {
    //printf("LINE: %u\n", __LINE__);
	  fprintf(rangeAnalP,"startByteLocation,endByteLocation,referenceNumber,Function\n");
          //printf("LINE: %u\n", __LINE__);
  }
  
  rangeAnalState = 0 ;
  //printf("LINE: %u\n", __LINE__);

}
void closeOut(void){
#ifdef DEBUG
  printf("Entered the close file ....\n");
#endif
  if(fp != NULL){
    fclose(fp);
  }else{
#ifdef DEBUG
    printf("Closed output file");
#endif
  }
  close(dev_urandom_fd);
  if(rangeAnalP != NULL)
	  fclose(rangeAnalP) ;
}

static inline unsigned UR(const char * fn, int line, unsigned limit) {
#ifdef DEBUG
  printf("Randomzier called from %s @ line %d, with Limit %d\n", fn,line, limit);
#endif

  //printf("LINE: %u\n", __LINE__);
  if (1) {
      
    unsigned seed[2];

    unsigned l = read(dev_urandom_fd, &seed, sizeof(seed));
    //printf("LINE: %u\n", __LINE__);
    if(l != sizeof(seed)){
#ifdef DEBUG
      printf("The seed reading is failed");
#endif
      //printf("LINE: %u\n", __LINE__);
      abort();
    }
    //printf("LINE: %u\n", __LINE__);
    srandom(seed[0]);
    rand_cnt = (RESEED_RNG / 2) + (seed[1] % RESEED_RNG);
    //printf("LINE: %u\n", __LINE__);

  }
  //printf("LINE: %u with %u\n", __LINE__, (unsigned)random() % limit);
  return random() % limit;
}

short __VERIFIER_nondet_short(int refNo,char* fn){
  short val = 0;
  if(state == 0){
    val = UR(__FUNCTION__,__LINE__,SHRT_MAX);
    fwrite(&val, sizeof(short),1,fp);
  }
   if(rangeAnalState == 0)
  {
	//fprintf(rangeAnalP,"%d;%d;%d;%s\n",byteTracker+1,byteTracker+SHORT_USHORT_BYTESIZE,refNo,fn);
	byteTracker = byteTracker + SHORT_USHORT_BYTESIZE ;
  }
  return val;
}


unsigned short __VERIFIER_nondet_ushort(int refNo,char* fn){
  unsigned short val = 0;
  if(state == 0){
    val = UR(__FUNCTION__,__LINE__,USHRT_MAX);
    fwrite(&val, sizeof(unsigned short),1,fp);
  }
  if(rangeAnalState == 0)
  {
	//fprintf(rangeAnalP,"%d;%d;%d;%s\n",byteTracker+1,byteTracker+SHORT_USHORT_BYTESIZE,refNo,fn);
	byteTracker = byteTracker + SHORT_USHORT_BYTESIZE ;
  }
  return val;
}

u16 __VERIFIER_nondet_u16(int refNo,char* fn){
	return __VERIFIER_nondet_ushort(refNo,fn);

}

int __VERIFIER_nondet_int(int refNo,char* fn){
  int val = 0;
  if(state == 0){
    val = UR(__FUNCTION__,__LINE__,INT_MAX);;
   // printf("LINE: %u\n", __LINE__);
    fwrite(&val, sizeof(int),1,fp);
       // printf("LINE: %u\n", __LINE__);
  }
  if(rangeAnalState == 0)
  {
           // printf("LINE: %u\n", __LINE__);
	fprintf(rangeAnalP,"%d;%d;\n",byteTracker+1,byteTracker+INT_UINT_BYTESIZE);
	byteTracker = byteTracker + INT_UINT_BYTESIZE ;
               // printf("LINE: %u\n", __LINE__);
  }
  printf("LINE: %u\n", __LINE__);
  return val;
}

unsigned int __VERIFIER_nondet_uint(int refNo,char* fn){
  unsigned int val = 0;
  if(state == 0){
    val = UR(__FUNCTION__,__LINE__,UINT_MAX);
    fwrite(&val, sizeof(unsigned),1,fp);
  }
  if(rangeAnalState == 0)
  {
	/*fprintf(rangeAnalP,"%d;%d;%d;%s\n",byteTracker+1,byteTracker+INT_UINT_BYTESIZE,refNo,fn);*/
	byteTracker = byteTracker + INT_UINT_BYTESIZE ;
  }
  return val;
}

unsigned int __VERIFIER_nondet_U32(int refNo,char* fn){
  return __VERIFIER_nondet_uint(refNo,fn);
}

unsigned int __VERIFIER_nondet_u32(int refNo,char* fn){
  return (u32)__VERIFIER_nondet_uint(refNo,fn);
}

unsigned __VERIFIER_nondet_unsigned(int refNo,char* fn){
  return (unsigned)__VERIFIER_nondet_uint(refNo,fn);
}

long __VERIFIER_nondet_long(int refNo,char* fn){
  long val  = 0;
  if(state == 0){
    ival = UR(__FUNCTION__,__LINE__,UINT_MAX);
    val = (long)ival;
    fwrite(&val, sizeof(long),1,fp);
  }
  if(rangeAnalState == 0)
  {
	/*fprintf(rangeAnalP,"%d;%d;%d;%s\n",byteTracker+1,byteTracker+LONG_ULONG_BYTESIZE,refNo,fn);*/
	byteTracker = byteTracker + LONG_ULONG_BYTESIZE ;
  }
  return val;
}

unsigned long __VERIFIER_nondet_ulong(int refNo,char* fn){
  unsigned long val = 0;
  if(state == 0){
    ival = UR(__FUNCTION__,__LINE__,UINT_MAX);
    val = (long)ival;
    fwrite(&val, sizeof(unsigned long),1,fp);
  }
  if(rangeAnalState == 0)
  {
	//fprintf(rangeAnalP,"%d;%d;%d;%s\n",byteTracker+1,byteTracker+LONG_ULONG_BYTESIZE,refNo,fn);
	byteTracker = byteTracker + LONG_ULONG_BYTESIZE ;
  }
  return val;
}

double __VERIFIER_nondet_double(int refNo,char* fn){
  double val = 0;
  if(state == 0){
    ival = UR(__FUNCTION__,__LINE__,UINT_MAX);
    val = (double)ival;
    fwrite(&val, sizeof(double),1,fp);
  }
  if(rangeAnalState == 0)
  {
	//fprintf(rangeAnalP,"%d;%d;%d;%s\n",byteTracker+1,byteTracker+DOUBLE_BYTESIZE,refNo,fn);
	byteTracker = byteTracker + DOUBLE_BYTESIZE ;
  }
  return val;
}

float __VERIFIER_nondet_float(int refNo,char* fn){
  float val = 0;
  if(state == 0){
    ival = UR(__FUNCTION__,__LINE__,UINT_MAX);
    val = (float)ival;
    fwrite(&val, sizeof(float),1,fp);
  }
  if(rangeAnalState == 0)
  {
	//fprintf(rangeAnalP,"%d;%d;%d;%s\n",byteTracker+1,byteTracker+FLOAT_BYTESIZE,refNo,fn);
	byteTracker = byteTracker + FLOAT_BYTESIZE ;	
  }
  return val;
}

char __VERIFIER_nondet_char(int refNo,char* fn){
  char  val = '\0';
  if(state == 0){
    ival = UR(__FUNCTION__,__LINE__,SCHAR_MAX);
    val = (char)ival;
    fwrite(&val, sizeof(char),1,fp);
  }
  if(rangeAnalState == 0)
  {
	//fprintf(rangeAnalP,"%d;%d;%d;%s\n",byteTracker+1,byteTracker+CHAR_UCHAR_BYTESIZE,refNo,fn);
	byteTracker = byteTracker + CHAR_UCHAR_BYTESIZE ;
  }
  	return val;
}

char __VERIFIER_nondet_S8(int refNo,char* fn){
  return __VERIFIER_nondet_char(refNo,fn);
}


unsigned char __VERIFIER_nondet_uchar(int refNo,char* fn){
  unsigned char val = '\0';
  if(state == 0){
    ival = UR(__FUNCTION__,__LINE__,UCHAR_MAX);
    val = (unsigned char)ival;
    fwrite(&val, sizeof(unsigned char),1,fp);
  }
  if(rangeAnalState == 0)
  {
	//fprintf(rangeAnalP,"%d;%d;%d;%s\n",byteTracker+1,byteTracker+CHAR_UCHAR_BYTESIZE,refNo,fn);
	byteTracker = byteTracker + CHAR_UCHAR_BYTESIZE ;
  }
  return val;
}

unsigned char __VERIFIER_nondet_U8(int refNo,char* fn){
  return  (unsigned char)__VERIFIER_nondet_uchar(refNo,fn);
}

u8 __VERIFIER_nondet_u8(int refNo,char* fn){
  return  (u8)__VERIFIER_nondet_uchar(refNo,fn);
}

unsigned char __VERIFIER_nondet_unsigned_char(int refNo,char* fn){
  return  (unsigned char)__VERIFIER_nondet_uchar(refNo,fn);
}

_Bool __VERIFIER_nondet_bool(int refNo,char* fn){
  /* For bool, we will always return true */
  /*
  unsigned char val = 128;
  if(state == 0){
    fwrite(&val, sizeof(unsigned char),1,fp);
  }*/
  unsigned char uc = __VERIFIER_nondet_uchar(refNo,fn);
  
  if(uc < 128) return false; 
#ifdef DEBUG
  printf("Boolean value called from %s @ line %d, with value  true\n", __FUNCTION__,__LINE__);
#endif
  return true;
}

_Bool __VERIFIER_nondet__Bool(int refNo,char* fn){
  return (_Bool)__VERIFIER_nondet_bool(refNo,fn);
}

size_t __VERIFIER_nondet_size_t(int refNo,char* fn){
  if(sizeof(size_t) == 64){
    return (size_t) __VERIFIER_nondet_long(refNo,fn);
  }else{
    return (size_t) __VERIFIER_nondet_int(refNo,fn);
  }
}

/* This is a danegerous fuzzing operation */
void * __VERIFIER_nondet_pointer(int refNo,char* fn){
  void *val;
  //val = NULL;
  val = malloc(1000);
  if(state == 0){
    fwrite(&val, sizeof(void *),1,fp);
  }
  if(rangeAnalState == 0)
  {
	//fprintf(rangeAnalP,"%d;%d;%d;%s\n",byteTracker+1,byteTracker+POINTER_BYTESIZE,refNo,fn);
	byteTracker = byteTracker + POINTER_BYTESIZE ;
  }
  return val;
}

char * __VERIFIER_nondet_pchar(int refNo,char* fn){
  return (char *)__VERIFIER_nondet_pointer(refNo,fn);
}

loff_t __VERIFIER_nondet_loff_t(int refNo,char* fn){
  return (loff_t)__VERIFIER_nondet_ulong(refNo,fn);
}

void __VERIFIER_error(void){
  /** Tolarate errors .. don't block them **/
  exit(0);
}

void __VERIFIER_assume(int expression){
  /** Tolarate assumes .. don't block them **/
  return;
}

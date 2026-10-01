/* pfi.c - flat entry points over pf_instrument for language bindings (WebAssembly,
 * Python ctypes): plain functions on one block of host memory instead of a table of
 * function pointers. Usage: n = pfi_size("guitar"); mem = <n bytes, 8-aligned>;
 * pfi_init(mem, "guitar", 44100); pfi_load(mem, &score); pfi_render(mem, L, R, frames). */
#include "pf_instrument.h"
#include <string.h>

typedef struct { const pf_instrument *in; double align; } pfi_head;
#define STATE(m) ((char *)(m)+sizeof(pfi_head))
#define IN(m) (((pfi_head *)(m))->in)

unsigned long pfi_size(const char *id){const pf_instrument *in=pf_instrument_find(id);return in?sizeof(pfi_head)+in->size():0;}
int pfi_init(void *m,const char *id,double sr)
{
    const pf_instrument *in=pf_instrument_find(id);if(!in)return 1;
    ((pfi_head *)m)->in=in;in->init(STATE(m),sr);return 0;
}
const char *pfi_id(const void *m){return IN(m)->id;}
int pfi_param_count(const void *m){return IN(m)->param_count();}
const char *pfi_param_name(const void *m,int i){const pf_param_info *p=IN(m)->param_info(i);return p?p->name:"";}
const char *pfi_param_unit(const void *m,int i){const pf_param_info *p=IN(m)->param_info(i);return p?p->unit:"";}
const char *pfi_param_group(const void *m,int i){const pf_param_info *p=IN(m)->param_info(i);return p?p->group:"";}
double pfi_param_min(const void *m,int i){const pf_param_info *p=IN(m)->param_info(i);return p?p->min:0;}
double pfi_param_max(const void *m,int i){const pf_param_info *p=IN(m)->param_info(i);return p?p->max:0;}
double pfi_param_default(const void *m,int i){const pf_param_info *p=IN(m)->param_info(i);return p?p->def:0;}
int pfi_param_integer(const void *m,int i){const pf_param_info *p=IN(m)->param_info(i);return p?p->integer:0;}
int pfi_param_find(const void *m,const char *name){return pf_param_find(IN(m),name);}
double pfi_get(const void *m,int i){return IN(m)->get(STATE(m),i);}
void pfi_set(void *m,int i,double v){IN(m)->set(STATE(m),i,v);}
int pfi_load(void *m,const pf_score *s){return IN(m)->load(STATE(m),s);}
void pfi_seek(void *m,double t){IN(m)->seek(STATE(m),t);}
int pfi_render(void *m,float *l,float *r,int frames){return IN(m)->render(STATE(m),l,r,frames);}
double pfi_time(const void *m){return IN(m)->time(STATE(m));}
int pfi_sounding(const void *m,pf_sounding *out,int max){return IN(m)->sounding(STATE(m),out,max);}
int pfi_note_size(void){return (int)sizeof(pf_note);}
int pfi_score_size(void){return (int)sizeof(pf_score);}
int pfi_sounding_size(void){return (int)sizeof(pf_sounding);}

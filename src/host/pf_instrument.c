/* pf_instrument.c - registry of the instruments behind pf_instrument.h. */
#include "pf_instrument.h"
#include <string.h>
static const pf_instrument *ALL[]={&pf_instrument_piano,&pf_instrument_guitar};
const pf_instrument *pf_instrument_find(const char *id)
{
    for(unsigned i=0;i<sizeof ALL/sizeof *ALL;i++)if(!strcmp(ALL[i]->id,id))return ALL[i];
    return 0;
}
int pf_param_find(const pf_instrument *in,const char *name)
{
    for(int i=0;i<in->param_count();i++)if(!strcmp(in->param_info(i)->name,name))return i;
    return -1;
}

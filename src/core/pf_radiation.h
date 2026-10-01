/* Analytic prototype body colours, not ERA fits or measured instruments. */
#ifndef PF_RADIATION_H
#define PF_RADIATION_H
#define PF_RADIATION_MODES 8
typedef struct {double a1[8],a2[8],g[8],z1[8],z2[8];int count;double direct;} pf_radiation;
void pf_radiation_init(pf_radiation *r,double sr,int violin);
void pf_radiation_process(pf_radiation *r,float *x,int n);
#endif

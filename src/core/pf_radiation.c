#include "pf_radiation.h"
#include <math.h>
#include <string.h>
void pf_radiation_init(pf_radiation *r,double sr,int violin)
{
    static const double f[2][8]={{95,190,315,490,760,1180,2100,3600},{275,460,560,1050,1650,2450,3100,4200}};
    static const double bw[2][8]={{35,65,85,110,180,260,450,700},{50,65,85,250,330,450,600,900}};
    static const double gain[2][8]={{.6,1,.7,.45,.35,.3,.22,.12},{.55,.85,1,.45,.4,.7,.45,.2}};
    memset(r,0,sizeof *r);r->count=8;r->direct=violin?.15:.3;
    for(int j=0;j<8;j++){double decay=exp(-3.141592653589793*bw[violin][j]/sr),w=6.283185307179586*f[violin][j]/sr;r->a1[j]=2*decay*cos(w);r->a2[j]=-decay*decay;r->g[j]=gain[violin][j]*(1-decay);}
}
void pf_radiation_process(pf_radiation *r,float *x,int n)
{
    for(int i=0;i<n;i++){double in=x[i],out=r->direct*in;for(int j=0;j<r->count;j++){double z=in+r->a1[j]*r->z1[j]+r->a2[j]*r->z2[j];out+=r->g[j]*(z-r->z2[j]);r->z2[j]=r->z1[j];r->z1[j]=z;}x[i]=(float)out;}
}

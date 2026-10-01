#include "pf_motion.h"
#include <math.h>
#include <string.h>
void pf_motion_init(pf_motion *m,const pf_partial *v,double cents,double seconds)
{
    memset(m,0,sizeof *m);
    if(cents>18)cents=18;if(cents<0)cents=0;
    if(seconds<.02)seconds=.02;if(seconds>1)seconds=1;
    m->shift=pow(2,cents/1200)-1;m->decay=exp(-1/(v->sr*seconds));
    for(int k=0;k<v->count;k++)for(int u=0;u<2;u++)m->radians[k][u]=atan2(v->ci[k][u],v->cr[k][u]);
}
void pf_motion_process(pf_motion *m,pf_partial *v,float *out,int frames)
{
    /* Exact bypass preserves the current synth, including its block behavior. */
    if(m->shift==0){pf_partial_process(v,out,frames);return;}
    for(int i=0;i<frames;i++){
        pf_partial_process(v,out+i,1);
        for(int k=0;k<v->count;k++)for(int u=0;u<2;u++){
            double w=m->radians[k][u]*m->shift,c=cos(w),s=sin(w),r=v->re[k][u],im=v->im[k][u];
            v->re[k][u]=r*c-im*s;v->im[k][u]=r*s+im*c;
        }
        m->shift*=m->decay;
    }
}

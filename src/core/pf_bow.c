#include "pf_bow.h"
#include <math.h>
#include <string.h>
static double read_delay(const double *d,int head,double delay)
{
    if(delay<1)delay=1;if(delay>PF_BOW_DELAY-2)delay=PF_BOW_DELAY-2;
    int n=(int)delay;double a=delay-n;
    return (1-a)*d[(head-n+PF_BOW_DELAY)%PF_BOW_DELAY]+a*d[(head-n-1+PF_BOW_DELAY)%PF_BOW_DELAY];
}
void pf_bow_note(pf_bow *s,double midi,double velocity){s->target=440*pow(2,(midi-69)/12);s->velocity=.06+.22*velocity;s->released=0;s->age=0;}
void pf_bow_init(pf_bow *s,double sr,double midi,double velocity,int expressive)
{
    memset(s,0,sizeof *s);s->sr=sr;s->expressive=expressive;s->rng=7201;
    pf_bow_note(s,midi,velocity);s->freq=s->target;s->lp=exp(-6.283185307179586*7000/sr);
}
void pf_bow_release(pf_bow *s){s->released=1;}
void pf_bow_pitch(pf_bow *s,double midi){s->target=440*pow(2,(midi-69)/12);}
void pf_bow_controls(pf_bow *s,int string,int stopped,double contact,double pressure,double attack,double speed)
{
    if(string<0)string=0;if(string>3)string=3;
    if(contact<.05)contact=.05;if(contact>.3)contact=.3;
    s->controlled=1;s->contact=contact;s->friction_scale=pressure;
    s->attack_time=attack;s->velocity=speed;
    s->neck_loss=stopped?.996:.999;
    s->lp=exp(-6.283185307179586*(4500+string*1000)/s->sr);
    s->contour_slew=.0015;
}
void pf_bow_process(pf_bow *s,float *out,int frames)
{
    for(int i=0;i<frames;i++,s->age++){
        double t=s->age/s->sr;s->freq+=(s->target-s->freq)*(1-exp(-1/(s->sr*(s->controlled?s->contour_slew:.025))));
        double vibr=s->expressive?.0035*(1-exp(-t/.3))*sin(6.283185307179586*5.3*t):0;
        double period=s->sr/(s->freq*(1+vibr))-s->lp/(1-s->lp),pos=s->controlled?s->contact:.12;
        double a=read_delay(s->neck,s->cursor,period*(1-pos)),b=read_delay(s->bridge,s->cursor,period*pos);
        double target=s->released?0:1;s->env+=(target-s->env)*(1-exp(-1/(s->sr*(s->released?.07:s->controlled?s->attack_time:.055))));
        double speed=s->velocity*s->env*(s->expressive?(1+.06*sin(6.283185307179586*1.1*t)):1);
        double rel=speed-(a+b),friction=pow(fabs(rel*(s->controlled?s->friction_scale:3))+.75,-4);if(friction>1)friction=1;
        double dv=rel*friction;
        s->z=s->lp*s->z+(1-s->lp)*(a+dv);
        /* Reflections reverse displacement velocity at both fixed ends. */
        s->bridge[s->cursor]=-.995*s->z;s->neck[s->cursor]=-(s->controlled?s->neck_loss:.998)*(b+dv);
        s->cursor=(s->cursor+1)%PF_BOW_DELAY;
        s->rng=s->rng*1664525u+1013904223u;
        double noise=(((s->rng>>8)/16777216.0)*2-1)*.0006*s->env;
        double y=s->z+noise;
        s->hp=.995*(s->hp+y-s->previous);s->previous=y;
        out[i]+=(float)(s->hp*.7);
    }
}

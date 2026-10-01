/* pf_piano_instrument.c - the partial-model piano as a pf_instrument: an adapter over
 * pf_player (pfplayer.h), which is unchanged. The score's notes and pedal controls are
 * turned back into the MIDI-style event list pf_player reads. */
#include "pf_instrument.h"
#include "pfplayer.h"
#include <math.h>
#include <string.h>

#define PF_PIANO_MAX_EVENTS 131072

typedef struct {
    pf_player pl; pf_player_options opt;
    const pf_score *score;
    pf_midi_event ev[PF_PIANO_MAX_EVENTS]; int nev;
    float mono[4096];
} pf_piano;

enum { P_GAIN, P_TONE, P_ATTACK, P_PEDAL_MODE, P_UNA_CORDA, P_BODY, P_KNOCK, P_NOISE, P_TREBLE,
       P_TOP_T60, P_TOP_DB, P_TOP_LO, P_LIMITER, P_RESONANCE, P_RESONANCE_DB, P_N };
static const pf_param_info PARAMS[P_N]={
    {"Output gain","x","Output",0,16,4,0},
    {"Tone","0 Salamander-fitted, 1 Pianoteq-fitted","Tone",0,1,1,1},
    {"Onset","1 = soundboard thump and noise","Onset",0,1,1,1},
    {"Pedal mode","0 switch, 1 continuous damper","Pedals",0,1,1,1},
    {"Una corda","1 = soft pedal shifts the hammer","Pedals",0,1,1,1},
    {"Body","dB","Onset",-40,12,-18,0},
    {"Knock","dB","Onset",-40,12,-22,0},
    {"Noise","dB","Onset",-40,12,-17,0},
    {"Treble onset","dB","Onset",-24,12,0,0},
    {"Top knock decay","x","Onset",.05,3,.25,0},
    {"Top knock level","dB","Onset",-24,12,0,0},
    {"Top knock from","x fundamental","Onset",.1,1,.5,0},
    {"Limiter","1 = lookahead peak limiter","Output",0,1,1,1},
    {"Sympathetic resonance","1 = on","Resonance",0,1,1,1},
    {"Resonance level","dB","Resonance",-24,12,0,0},
};
static double *field(pf_player_options *o,int i)
{
    switch(i){case P_GAIN:return &o->gain;case P_BODY:return &o->body_db;case P_KNOCK:return &o->knock_db;case P_NOISE:return &o->noise_db;
        case P_TREBLE:return &o->treble_db;case P_TOP_T60:return &o->top_knock_t60;case P_TOP_DB:return &o->top_knock_db;case P_TOP_LO:return &o->top_knock_lo;
        case P_RESONANCE_DB:return &o->resonance_db;default:return 0;}
}
static int *ifield(pf_player_options *o,int i)
{
    switch(i){case P_TONE:return &o->tone;case P_ATTACK:return &o->attack;case P_PEDAL_MODE:return &o->pedal_mode;case P_UNA_CORDA:return &o->una_corda;
        case P_LIMITER:return &o->limiter;case P_RESONANCE:return &o->resonance;default:return 0;}
}
static size_t psize(void){return sizeof(pf_piano);}
static void pinit(void *self,double sr)
{
    pf_piano *p=self;memset(p,0,sizeof *p);pf_player_defaults(&p->opt);pf_player_init(&p->pl,sr,&p->opt);
}
static int pcount(void){return P_N;}
static const pf_param_info *pinfo(int i){return i>=0&&i<P_N?&PARAMS[i]:0;}
static double pget(const void *self,int i)
{
    pf_piano *p=(pf_piano *)self;double *d=field(&p->opt,i);int *n=ifield(&p->opt,i);
    return d?*d:n?*n:0;
}
static void pset(void *self,int i,double v)
{
    pf_piano *p=self;if(i<0||i>=P_N)return;
    if(v<PARAMS[i].min)v=PARAMS[i].min;if(v>PARAMS[i].max)v=PARAMS[i].max;
    double *d=field(&p->opt,i);int *n=ifield(&p->opt,i);
    if(d)*d=v;else if(n)*n=(int)floor(v+.5);
    pf_player_set_options(&p->pl,&p->opt);
}
static int ev_order(const pf_midi_event *a,const pf_midi_event *b)
{
    if(a->t!=b->t)return a->t<b->t?-1:1;
    int ra=a->type==PF_EV_NOTE_OFF?0:a->type==PF_EV_NOTE_ON?2:1,rb=b->type==PF_EV_NOTE_OFF?0:b->type==PF_EV_NOTE_ON?2:1;
    return ra-rb;                  /* releases, then pedals, then strikes at the same instant */
}
static int pload(void *self,const pf_score *sc)
{
    pf_piano *p=self;p->score=sc;int e=0;
    if(2*sc->n_notes+sc->n_controls>PF_PIANO_MAX_EVENTS)return 1;
    for(int i=0;i<sc->n_notes;i++){
        const pf_note *N=&sc->notes[i];int key=(int)lrintf(N->pitch),vel=(int)lrintf(N->velocity);
        if(key<0||key>127)continue;if(vel<1)vel=1;if(vel>127)vel=127;
        p->ev[e++]=(pf_midi_event){N->start,PF_EV_NOTE_ON,(unsigned char)key,(unsigned char)vel};
        p->ev[e++]=(pf_midi_event){N->end,PF_EV_NOTE_OFF,(unsigned char)key,0};
    }
    for(int i=0;i<sc->n_controls;i++){
        const pf_control *C=&sc->controls[i];int v=(int)lrintf(C->value*127);if(v<0)v=0;if(v>127)v=127;
        unsigned char type=C->kind==PF_CTL_SUSTAIN?PF_EV_PEDAL:C->kind==PF_CTL_SOSTENUTO?PF_EV_SOSTENUTO:PF_EV_SOFT;
        p->ev[e++]=(pf_midi_event){C->t,type,0,(unsigned char)v};
    }
    for(int i=1;i<e;i++){pf_midi_event x=p->ev[i];int j=i-1;while(j>=0&&ev_order(&p->ev[j],&x)>0){p->ev[j+1]=p->ev[j];j--;}p->ev[j+1]=x;}
    p->nev=e;pf_player_load(&p->pl,p->ev,e,sc->duration);return 0;
}
static void pseek(void *self,double t){pf_piano *p=self;pf_player_seek(&p->pl,t);}
static int prender(void *self,float *left,float *right,int frames)
{
    pf_piano *p=self;int active=0,done=0;
    while(done<frames){
        int n=frames-done>4096?4096:frames-done;
        active=pf_player_render(&p->pl,p->mono,n);
        memcpy(left+done,p->mono,sizeof(float)*(size_t)n);if(right)memcpy(right+done,p->mono,sizeof(float)*(size_t)n);
        done+=n;
    }
    return active;
}
static double ptime(const void *self){const pf_piano *p=self;return pf_player_time(&p->pl);}
static int psounding(const void *self,pf_sounding *out,int max)
{
    const pf_piano *p=self;unsigned char keys[128];pf_player_sounding(&p->pl,keys);
    double t=pf_player_time(&p->pl);int c=0;
    for(int k=0;k<128&&c<max;k++){
        if(!keys[k])continue;int idx=-1;double best=-1;
        if(p->score)for(int i=0;i<p->score->n_notes;i++){const pf_note *N=&p->score->notes[i];if(N->start>t)break;if((int)lrintf(N->pitch)==k&&N->start>best){best=N->start;idx=i;}}
        out[c++]=(pf_sounding){idx,(float)k,keys[k]/127.f,-1,-1};
    }
    return c;
}
const pf_instrument pf_instrument_piano={"piano",psize,pinit,pcount,pinfo,pget,pset,pload,pseek,prender,ptime,psounding};

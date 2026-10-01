/* Experiment harness only. Keeps the established player's pedal, attack,
 * voice stealing and sympathetic resonance unchanged around a motion hook. */
#include "pfplayer.h"
#include "../core/pf_motion.h"
#include "../core/pf_pluck.h"
#include "../core/pf_bow.h"
#include "../core/pf_radiation.h"
#include <math.h>
#include <string.h>
#include <stddef.h>
#include "../../experiments/string-motion/motion_patch.h"
static pf_player lab_player;
static pf_motion motions[PF_PLAYER_VOICES];
static double motion_amount;
static void motion_hook(pf_partial *p,float *out,int n)
{
    if(motion_amount==0){pf_partial_process(p,out,n);return;}
    for(int j=0;j<PF_PLAYER_VOICES;j++)if(p==&lab_player.v[j].p){
        if(p->age==0){
            double key=(lab_player.v[j].note-36)/12.0;if(key<0)key=0;if(key>3)key=3;
            int a=(int)key,b=a<3?a+1:a;double t=key-a,vel=(lab_player.v[j].vel-48)/52.0;if(vel<0)vel=0;if(vel>1)vel=1;
            double cents=(1-t)*((1-vel)*motion_cents[a][0]+vel*motion_cents[a][1])+t*((1-vel)*motion_cents[b][0]+vel*motion_cents[b][1]);
            double tau=(1-t)*((1-vel)*motion_tau[a][0]+vel*motion_tau[a][1])+t*((1-vel)*motion_tau[b][0]+vel*motion_tau[b][1]);
            pf_motion_init(&motions[j],p,cents*motion_amount,tau);
        }
        pf_motion_process(&motions[j],p,out,n);return;
    }
    pf_partial_process(p,out,n);
}
/* Compile the unchanged player implementation with only the tonal processing
 * call substituted. The production player and app retain their original ABI. */
#define pf_partial_process motion_hook
#include "pfplayer.c"
#undef pf_partial_process

int pf_lab_piano(const char *midi,float *out,int n,double amount,int block)
{
    pf_song song;if(pf_midi_load(&song,midi))return -1;
    pf_player_options o;pf_player_defaults(&o);o.gain=1;o.limiter=0;
    motion_amount=amount;memset(motions,0,sizeof motions);
    pf_player_init(&lab_player,44100,&o);pf_player_load(&lab_player,song.ev,song.n,n/44100.0);
    for(int i=0;i<n;i+=block){int m=n-i<block?n-i:block;pf_player_render(&lab_player,out+i,m);}
    pf_midi_free(&song);return 0;
}
void pf_lab_pluck(float *out,int n,double midi,double vel,int release,int nonlinear,int block)
{
    pf_pluck s;pf_pluck_init(&s,44100,midi,vel,nonlinear);
    for(int i=0;i<n;){if(i==release)pf_pluck_release(&s);int m=n-i<block?n-i:block;if(i<release&&i+m>release)m=release-i;pf_pluck_process(&s,out+i,m);i+=m;}
}
double pf_lab_pluck_energy(double midi,double vel,int nonlinear,int frames)
{
    pf_pluck s;pf_pluck_init(&s,44100,midi,vel,nonlinear);double start=pf_pluck_energy(&s);float buf[64];
    for(int i=0;i<frames;i+=64){int m=frames-i<64?frames-i:64;memset(buf,0,sizeof buf);pf_pluck_process(&s,buf,m);}
    return pf_pluck_energy(&s)/start;
}
size_t pf_lab_bow_size(void){return sizeof(pf_bow);}
void pf_lab_bow_init(void *p,double midi,double vel,int expressive){pf_bow_init(p,44100,midi,vel,expressive);}
void pf_lab_bow_note(void *p,double midi,double vel){pf_bow_note(p,midi,vel);}
void pf_lab_bow_release(void *p){pf_bow_release(p);}
void pf_lab_bow_process(void *p,float *out,int n){pf_bow_process(p,out,n);}
void pf_lab_body(float *x,int n,int violin){pf_radiation r;pf_radiation_init(&r,44100,violin);pf_radiation_process(&r,x,n);}
size_t pf_lab_string_size(void){return sizeof(pf_pluck);}
void pf_lab_string_init(void *p,double midi,double vel,int string,double pos){pf_pluck_string(p,44100,midi,vel,string,pos);}
void pf_lab_string_material(void *p,double midi,double vel,int string,double pos,int material){pf_pluck_material(p,44100,midi,vel,string,pos,material);}
void pf_lab_string_loading(void *p,const double *loss){pf_pluck *s=p;for(int j=0;j<PF_PLUCK_MODES;j++)s->body_loss[j]=loss[j]>0?loss[j]:0;s->pitch_ready=0;}
/* Maximum post-pluck energy ratio; opt-in material stability check. */
double pf_lab_material_energy(double midi,int string,int material,int frames)
{
    pf_pluck s;pf_pluck_material(&s,44100,midi,.8,string,.19,material);
    double initial=pf_pluck_energy(&s),maximum=0;float out[64];
    for(int i=0;i<frames;i+=64){memset(out,0,sizeof out);pf_pluck_process(&s,out,frames-i<64?frames-i:64);
        double ratio=pf_pluck_energy(&s)/initial;if(!isfinite(ratio))return -1;if(ratio>maximum)maximum=ratio;}
    return maximum;
}
void pf_lab_string_pitch(void *p,double midi,int string,double damp){pf_pluck_pitch(p,midi,string,damp);}
void pf_lab_string_release(void *p){pf_pluck_release(p);}
void pf_lab_string_touch(void *p,double position,double rho){pf_pluck_touch(p,position,rho);}
void pf_lab_string_touch_width(void *p,double position,double rho,double width){pf_pluck_touch_width(p,position,rho,width);}
void pf_lab_string_legato(void *p,double midi,int string,double amount,double contact){pf_pluck_legato(p,midi,string,amount,contact);}
void pf_lab_string_process(void *p,float *out,int n){pf_pluck_process(p,out,n);}
void pf_lab_string_hammer(void *p,double midi,int string,double vel)
{
    pf_pluck *s=p,kick;pf_pluck_pitch(s,midi,string,0);
    pf_pluck_string(&kick,44100,midi,vel,string,.08);
    for(int j=0;j<s->count;j++)s->q[j]+=.16*kick.q[j];
    s->release=1;pf_pluck_pitch(s,midi,string,0);
}
void pf_lab_bow_controls(void *p,int string,int stopped,double contact,double pressure,double attack,double speed){pf_bow_controls(p,string,stopped,contact,pressure,attack,speed);}
void pf_lab_bow_pitch(void *p,double midi){pf_bow_pitch(p,midi);}

/* Tone-only path for exact bypass / block-equivalence checks, including release. */
void pf_lab_partial(float *out,int n,double midi,double vel,double cents,int block)
{
    pf_partial p;pf_motion m;pf_partial_init(&p,pf_player_patch(1),44100,midi,vel);pf_motion_init(&m,&p,cents,.2);
    for(int i=0;i<n;i+=block){int k=n-i<block?n-i:block;pf_motion_process(&m,&p,out+i,k);}
}

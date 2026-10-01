/* Two travelling-wave string segments joined at a nonlinear bow junction.
 * Analytic friction table (STK-style), not a measured violin reproduction. */
#ifndef PF_BOW_H
#define PF_BOW_H
#define PF_BOW_DELAY 4096
typedef struct {
    double neck[PF_BOW_DELAY],bridge[PF_BOW_DELAY];
    int cursor,age,released,expressive;
    double sr,freq,target,velocity,env,lp,z,hp,previous;
    unsigned rng;
    int controlled;
    double contact,friction_scale,attack_time,neck_loss,contour_slew;
} pf_bow;
void pf_bow_controls(pf_bow *s,int string,int stopped,double contact,double pressure,double attack,double speed);
void pf_bow_pitch(pf_bow *s,double midi);
void pf_bow_init(pf_bow *s,double sr,double midi,double velocity,int expressive);
void pf_bow_note(pf_bow *s,double midi,double velocity);
void pf_bow_release(pf_bow *s);
void pf_bow_process(pf_bow *s,float *out,int frames);
#endif

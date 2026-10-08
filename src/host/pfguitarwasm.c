/* Guitar-only web binding. Keeps the shared pfi.wasm and its consumers unchanged. */
#include "pf_guitar.h"
#include <string.h>
#define EXPORT(name) __attribute__((export_name(#name))) name
#define MAX_LOADING 256
static pf_guitar guitar;
static pf_note notes[PF_GUITAR_MAX_NOTES];
static pf_guitar_note_input inputs[PF_GUITAR_MAX_NOTES];
static float loading[MAX_LOADING][PF_PLUCK_MODES];
static signed char tuning[6];static pf_score score;
static float left[4096],right[4096];static pf_sounding sounding[6];
#define I pf_instrument_guitar
int EXPORT(pfiw_init)(int which,double sr){if(which!=1||sr<8000||sr>192000)return 1;I.init(&guitar,sr);return 0;}
int EXPORT(pfiw_param_count)(void){return I.param_count();}
const char *EXPORT(pfiw_param_name)(int i){const pf_param_info *p=I.param_info(i);return p?p->name:"";}
const char *EXPORT(pfiw_param_unit)(int i){const pf_param_info *p=I.param_info(i);return p?p->unit:"";}
const char *EXPORT(pfiw_param_group)(int i){const pf_param_info *p=I.param_info(i);return p?p->group:"";}
double EXPORT(pfiw_param_min)(int i){const pf_param_info *p=I.param_info(i);return p?p->min:0;}
double EXPORT(pfiw_param_max)(int i){const pf_param_info *p=I.param_info(i);return p?p->max:0;}
double EXPORT(pfiw_param_default)(int i){const pf_param_info *p=I.param_info(i);return p?p->def:0;}
int EXPORT(pfiw_param_integer)(int i){const pf_param_info *p=I.param_info(i);return p?p->integer:0;}
double EXPORT(pfiw_get)(int i){return I.get(&guitar,i);}
void EXPORT(pfiw_set)(int i,double v){I.set(&guitar,i,v);}
pf_note *EXPORT(pfiw_notes)(void){return notes;}
signed char *EXPORT(pfiw_tuning)(void){return tuning;}
int EXPORT(pfiw_max_notes)(void){return PF_GUITAR_MAX_NOTES;}
int EXPORT(pfiw_note_size)(void){return sizeof(pf_note);}
int EXPORT(pfiw_sounding_size)(void){return sizeof(pf_sounding);}
pf_guitar_note_input *EXPORT(pfiw_guitar_inputs)(void){return inputs;}
int EXPORT(pfiw_guitar_input_size)(void){return sizeof(pf_guitar_note_input);}
float *EXPORT(pfiw_guitar_loading)(void){return &loading[0][0];}
int EXPORT(pfiw_guitar_max_loading)(void){return MAX_LOADING;}
int EXPORT(pfiw_guitar_set_loading)(int count){if(count<0||count>MAX_LOADING)return 1;guitar.loading=loading;guitar.loading_count=count;return 0;}
int EXPORT(pfiw_load)(int n,int nc,int nb,int ns,double duration){
    if(n<0||n>PF_GUITAR_MAX_NOTES||nc||nb||ns!=6||duration<=0)return 1;
    score=(pf_score){.notes=notes,.n_notes=n,.tuning=tuning,.n_strings=6,.duration=duration};
    guitar.note_inputs=inputs;return I.load(&guitar,&score);
}
void EXPORT(pfiw_seek)(double t){I.seek(&guitar,t);}
double EXPORT(pfiw_time)(void){return I.time(&guitar);}
int EXPORT(pfiw_render)(int n){if(n<0)return 0;if(n>4096)n=4096;return I.render(&guitar,left,right,n);}
float *EXPORT(pfiw_left)(void){return left;}
float *EXPORT(pfiw_right)(void){return right;}
int EXPORT(pfiw_sounding)(void){return I.sounding(&guitar,sounding,6);}
pf_sounding *EXPORT(pfiw_sounding_buffer)(void){return sounding;}

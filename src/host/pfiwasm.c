/* pfiwasm.c - WebAssembly entry points for the instrument-independent API (pfi.c):
 * docs/pfi.wasm, used by the guitar page. The piano page keeps docs/pfsynth.wasm and
 * its pfw_* exports unchanged. Static memory only: one instrument at a time, score
 * arrays the page fills in place (layouts in API.md; sizes exported for checks). */
#include "pf_instrument.h"
#define EXPORT(name) __attribute__((export_name(#name))) name
#define MAX_NOTES 16384
#define MAX_CONTROLS 65536
#define MAX_BENDS 65536
#define ARENA (24<<20)

unsigned long pfi_size(const char *id);int pfi_init(void *m,const char *id,double sr);
int pfi_param_count(const void *m);const char *pfi_param_name(const void *m,int i);const char *pfi_param_unit(const void *m,int i);
const char *pfi_param_group(const void *m,int i);double pfi_param_min(const void *m,int i);double pfi_param_max(const void *m,int i);
double pfi_param_default(const void *m,int i);int pfi_param_integer(const void *m,int i);double pfi_get(const void *m,int i);
void pfi_set(void *m,int i,double v);int pfi_load(void *m,const pf_score *s);void pfi_seek(void *m,double t);
int pfi_render(void *m,float *l,float *r,int frames);double pfi_time(const void *m);int pfi_sounding(const void *m,pf_sounding *out,int max);

static double arena[ARENA/8];
static pf_note notes[MAX_NOTES];static pf_control controls[MAX_CONTROLS];static pf_bend_point bends[MAX_BENDS];
static signed char tuning[8];static pf_score score;
static float left[4096],right[4096];static pf_sounding sounding[16];
static const char *ids[]={"piano","guitar"};
static int ready;

int EXPORT(pfiw_count)(void){return 2;}
const char *EXPORT(pfiw_id)(int i){return i>=0&&i<2?ids[i]:"";}
int EXPORT(pfiw_init)(int which,double sr)
{
    if(which<0||which>1||pfi_size(ids[which])>sizeof arena)return 1;
    ready=!pfi_init(arena,ids[which],sr);return !ready;
}
int EXPORT(pfiw_param_count)(void){return ready?pfi_param_count(arena):0;}
const char *EXPORT(pfiw_param_name)(int i){return pfi_param_name(arena,i);}
const char *EXPORT(pfiw_param_unit)(int i){return pfi_param_unit(arena,i);}
const char *EXPORT(pfiw_param_group)(int i){return pfi_param_group(arena,i);}
double EXPORT(pfiw_param_min)(int i){return pfi_param_min(arena,i);}
double EXPORT(pfiw_param_max)(int i){return pfi_param_max(arena,i);}
double EXPORT(pfiw_param_default)(int i){return pfi_param_default(arena,i);}
int EXPORT(pfiw_param_integer)(int i){return pfi_param_integer(arena,i);}
double EXPORT(pfiw_get)(int i){return pfi_get(arena,i);}
void EXPORT(pfiw_set)(int i,double v){pfi_set(arena,i,v);}
pf_note *EXPORT(pfiw_notes)(void){return notes;}
pf_control *EXPORT(pfiw_controls)(void){return controls;}
pf_bend_point *EXPORT(pfiw_bends)(void){return bends;}
signed char *EXPORT(pfiw_tuning)(void){return tuning;}
int EXPORT(pfiw_max_notes)(void){return MAX_NOTES;}
int EXPORT(pfiw_max_controls)(void){return MAX_CONTROLS;}
int EXPORT(pfiw_max_bends)(void){return MAX_BENDS;}
int EXPORT(pfiw_note_size)(void){return (int)sizeof(pf_note);}
int EXPORT(pfiw_control_size)(void){return (int)sizeof(pf_control);}
int EXPORT(pfiw_bend_size)(void){return (int)sizeof(pf_bend_point);}
int EXPORT(pfiw_sounding_size)(void){return (int)sizeof(pf_sounding);}
int EXPORT(pfiw_load)(int n_notes,int n_controls,int n_bends,int n_strings,double duration)
{
    if(!ready||n_notes>MAX_NOTES||n_controls>MAX_CONTROLS||n_bends>MAX_BENDS)return 1;
    score=(pf_score){notes,n_notes,controls,n_controls,bends,n_bends,n_strings>0?tuning:0,n_strings,duration};
    return pfi_load(arena,&score);
}
void EXPORT(pfiw_seek)(double t){pfi_seek(arena,t);}
double EXPORT(pfiw_time)(void){return pfi_time(arena);}
int EXPORT(pfiw_render)(int frames){if(frames>4096)frames=4096;return pfi_render(arena,left,right,frames);}
float *EXPORT(pfiw_left)(void){return left;}
float *EXPORT(pfiw_right)(void){return right;}
int EXPORT(pfiw_sounding)(void){return pfi_sounding(arena,sounding,16);}
pf_sounding *EXPORT(pfiw_sounding_buffer)(void){return sounding;}

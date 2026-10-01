/* pf_score_io.c - see pf_score_io.h. */
#include "pf_score_io.h"
#include <string.h>

int pf_score_from_midi(const pf_midi_event *ev,int n,double duration,pf_note *notes,int max_notes,pf_control *controls,int max_controls,pf_score *out)
{
    int nn=0,nc=0;
    for(int i=0;i<n;i++){
        const pf_midi_event *e=&ev[i];
        if(e->type==PF_EV_NOTE_ON){
            if(nn>=max_notes)return -1;
            pf_note *N=&notes[nn++];memset(N,0,sizeof *N);
            N->start=e->t;N->end=duration;N->pitch=e->note;N->velocity=e->val;
            N->string=N->fret=N->finger=-1;N->articulation=PF_ART_NORMAL;N->reserved=-1;   /* reserved = open (no note-off yet) */
        }else if(e->type==PF_EV_NOTE_OFF){
            for(int k=0;k<nn;k++)if(notes[k].reserved==-1&&(int)notes[k].pitch==e->note){notes[k].end=e->t;notes[k].reserved=0;break;}
        }else{
            if(nc>=max_controls)return -1;
            pf_control *C=&controls[nc++];C->t=e->t;C->value=e->val/127.f;
            C->kind=e->type==PF_EV_PEDAL?PF_CTL_SUSTAIN:e->type==PF_EV_SOSTENUTO?PF_CTL_SOSTENUTO:PF_CTL_SOFT;
        }
    }
    for(int k=0;k<nn;k++)notes[k].reserved=0;
    memset(out,0,sizeof *out);
    out->notes=notes;out->n_notes=nn;out->controls=controls;out->n_controls=nc;out->duration=duration;
    return nn;
}

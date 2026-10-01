/* apitest.c - the piano adapter must render exactly what pf_player renders.
 *   build/apitest file.mid [...]   (renders the first 30 s of each both ways) */
#include "pf_instrument.h"
#include "pf_score_io.h"
#include "pfplayer.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc,char **argv)
{
    const double sr=44100,secs=30;const int N=(int)(sr*secs),B=128;int failed=0;
    for(int a=1;a<argc;a++){
        pf_song song;if(pf_midi_load(&song,argv[a])){failed=1;continue;}
        /* reference: the file's events with simultaneous events put in the adapter's order
         * (releases, pedals, strikes); count how many instants the file orders differently */
        pf_midi_event *ref=malloc(sizeof(pf_midi_event)*song.n);int moved=0;
        for(int i=0;i<song.n;i++)ref[i]=song.ev[i];
        for(int i=1;i<song.n;i++){pf_midi_event q=ref[i];int j=i-1;
            while(j>=0&&ref[j].t==q.t&&(ref[j].type==PF_EV_NOTE_OFF?0:ref[j].type==PF_EV_NOTE_ON?2:1)>(q.type==PF_EV_NOTE_OFF?0:q.type==PF_EV_NOTE_ON?2:1)){ref[j+1]=ref[j];j--;}
            if(j+1!=i)moved++;ref[j+1]=q;}
        static pf_player pl;pf_player_options o;pf_player_defaults(&o);pf_player_init(&pl,sr,&o);pf_player_load(&pl,ref,song.n,song.duration);
        float *x=malloc(sizeof(float)*N),*y=malloc(sizeof(float)*N),*r=malloc(sizeof(float)*N);
        for(int i=0;i<N;i+=B)pf_player_render(&pl,x+i,B);
        pf_note *notes=malloc(sizeof(pf_note)*song.n);pf_control *ctl=malloc(sizeof(pf_control)*song.n);pf_score sc;
        int nn=pf_score_from_midi(song.ev,song.n,song.duration,notes,song.n,ctl,song.n,&sc);
        const pf_instrument *piano=pf_instrument_find("piano");void *st=malloc(piano->size());
        piano->init(st,sr);piano->load(st,&sc);
        for(int i=0;i<N;i+=B)piano->render(st,y+i,r+i,B);
        double d=0,peak=0;long diff=0;
        for(int i=0;i<N;i++){double e=fabs((double)x[i]-y[i]);if(e>d)d=e;if(fabs(x[i])>peak)peak=fabs(x[i]);if(x[i]!=y[i]||y[i]!=r[i])diff++;}
        printf("%s: %d notes, %d controls, %d events reordered at equal times; max |difference| %.3g (peak %.3g), %ld samples differ\n",argv[a],nn,sc.n_controls,moved,d,peak,diff);
        if(diff)failed=1;
        free(x);free(y);free(r);free(notes);free(ctl);free(st);free(song.ev);free(ref);
    }
    return failed;
}

/* Small, opt-in frequency-motion overlay for pf_partial. Fitted observable,
 * inspired by nonlinear strings; NOT a nonlinear hammer/string simulation. */
#ifndef PF_MOTION_H
#define PF_MOTION_H
#include "pf_partial.h"
typedef struct {
    double shift, decay;
    double radians[PF_PARTIAL_MODES][2];
} pf_motion;
void pf_motion_init(pf_motion *m, const pf_partial *v, double cents, double seconds);
void pf_motion_process(pf_motion *m, pf_partial *v, float *out, int frames);
#endif

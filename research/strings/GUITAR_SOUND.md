# Guitar sound: materials, bridge loading and radiation

Fresh source check: September 30, 2026. Current auditions are local research.

## Best implementation directions

1. Ducceschi, Russo and Webb (DAFx 2026), **Measurement-Informed Nonlinear
   Modal Synthesis of 65 Classical Guitars**.
   https://www.dafx.de/paper-archive/details/KZ0Ws85vmVK5-Tceo9RZ1w
   Local PDF: `papers/ducceschi-russo-webb-2026-guitars.pdf`.
   This is the strongest architecture match: measured bridge compliance and
   bridge-to-air radiation are separate paths, coupled to a nonlinear modal
   string. The paper uses SAV and two low-rank inversions for efficient updates.
   Our previous string model used the general modal/SAV idea but had designed
   body resonances, not these measured bridge/radiation paths. The next complete
   overhaul should reproduce the coupled scheme and fit positive bridge residues.
   Companion repository: https://github.com/Nemus-Project/65_modelled_guitars
   The public repository page currently presents synthesized examples; a usable
   synthesis implementation was not found in the displayed file listing, despite
   the paper advertising code. Do not claim a code port from this repository.

2. Kodama, Sato, Hoshika and Yokoyama (2023), **Attenuation characteristics of
   tones and vibrations in guitars with nylon, fluorocarbon, and phosphor bronze
   strings pressed down against fret**. https://doi.org/10.1250/ast.44.218
   Local PDF: `papers/kodama-2023-string-materials.pdf`.
   Tables 1/2 supply treble-string diameters, linear masses, storage moduli and
   loss moduli. These permit material-dependent bending dispersion and decay.
   Internal bending loss becomes more significant as the string is shortened.
   NY1 and FC1 data drive the new auditions; these are measured material-property
   sets, not a fitted model of Kowalski's installed strings. Measurements of
   elastic moduli at 10 Hz do not establish identical values across audio rates.
   Wound basses need a composite/core-and-winding model, not a solid cylinder.

3. Bank and Karjalainen (DAFx 2010), **Passive Admittance Matrix Modeling for
   Guitar Synthesis**. https://home.mit.bme.hu/~bank/publist/dafx10adm/index.html
   Local PDF: `papers/bank-karjalainen-2010-admittance.pdf`.
   Use its passive multidimensional bridge representation for the two transverse
   polarizations and stable feedback. This can produce different partial decay
   shapes and beating. It prevents treating an arbitrary response filter as a
   safe mechanical feedback element. The author page includes audio examples;
   the current prototype does not implement its matrix reflectance algorithm.

4. Woodhouse (2004), **On the Synthesis of Guitar Plucks**.
   https://euphonics.org/wp-content/uploads/2022/03/Guitar_I.pdf
   Useful for frequency-domain and modal routes from string properties plus
   measured bridge admittance. Accurate damping needs to survive the coupled
   synthesis formulation; an undamped modal fit alone is inadequate. Follow with
   **Plucked Guitar Transients: Comparison of Measurements and Synthesis** for
   calibration and missing high-frequency/polarization effects.

## Measurement data actually used

Robert Mores (2021), archive of classical/flamenco/romantic guitar bridge mobility:
https://zenodo.org/records/4604577 . Archive metadata: CC BY 4.0.
`body/mores-qualified-selected-impulses.mat` contains 65 x 144000 x 6 samples.
Each guitar has three one-second impacts at 48 kHz, bass/center/treble positions.
The downloaded author scripts document force/accelerometer/microphone calibration.
The auditions use the treble impact, treble accelerometer, and treble microphone.

Selected instruments: g05 Daniel Gil de Avalle, 2014, classical Spanish guitar;
g21 Lester DeVoe, 2018, flamenca blanca. Neither is Kowalski's 2007 Fritz Ober.
Instrument labels were checked against the archive's guitar description PDF.

## Current implementation and limits

`tools/guitar_material_audition.py` keeps the Bach events/fingering/variation seed
fixed and adds five ablations: original vs nylon properties; designed vs measured
body; nylon vs fluorocarbon; two measured bodies; radiation with/without loading.

Material modes use omega² = (T k² + E' I k⁴)/mu and
sigma = 1.4 + E'' I k⁴/(2 mu omega). T is corrected so the fundamental remains
at the MIDI pitch. These measured treble properties replace the earlier shared
stiffness and quadratic-frequency loss. Bass EI/loss and background loss remain
assumptions; both material sets share the same basses. This is not a full string
contact, winding, frequency-dependent viscoelastic or two-polarization model.

For the body, regularized force-to-pressure responses yield a 150 ms radiation
FIR (fade begins at 100 ms), applied to the synthesized bridge-force output.
Accelerance is integrated to mobility; its smoothed nonnegative real part adds
resistive modal damping approximately T/L Re(Y), capped at 10/s. This is a
weak-coupling loading approximation. It is not a reproduction of the 2026
constraint scheme, a bidirectional bridge model, or sympathetic string transfer.
Negative measured resistance is discarded, not used as potentially active
feedback. Room influence remains in the measured radiation response.

Next substantial implementation: passive fitted bridge compliance, both string
polarizations, shared-body energy exchange and radiation kept separate; then
nail/finger release and longitudinal components. A richer real recording does
not establish that string material alone causes the difference. Performer,
excitation, microphone position, instrument and room also differ.

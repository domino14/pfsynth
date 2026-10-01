# American Football – "Never Meant" (1999)

Reference piece for the electric-guitar models (clean Telecaster tone, open tunings, two
interlocking guitars). **Local research only.** All audio, stems and saved tab text are
git-ignored (`../.gitignore`). Never commit or redistribute them.

## Files (all git-ignored)

| Path | What | Format |
|---|---|---|
| `never-meant.wav` | Original album master, official upload | 44.1 kHz, 16-bit, stereo, 268.33 s |
| `stems/htdemucs_6s/{guitar,bass,drums,vocals,piano,other}.wav` | Demucs 6-stem separation | 44.1 kHz, 24-bit, stereo, 268.33 s |
| `tabs/ug-tab-979718.txt` | Text of a free public Ultimate Guitar fan tab | plain text |

## Audio source

- URL: https://www.youtube.com/watch?v=p-SWkpGKdP8
- Channel: "American Football" Topic channel (UCX0E0vMNuhVdIH_s3RVFGGA), auto-generated
  "Provided to YouTube by Polyvinyl Record Co.", ℗ Polyvinyl Record Co., album *American
  Football* (release date shown: 2014-05-20, the deluxe reissue of the 1999 LP).
- Fetched: 2026-10-01 with the user's Chrome cookies (user-authorised, local research):
  `yt-dlp --no-playlist --cookies-from-browser chrome -f bestaudio -x --audio-format wav`
  (venv yt-dlp 2026.07.04 from `~/.charter-stems-venv`, with
  `--extractor-args youtube:player_client=web,web_safari,mweb --remote-components ejs:github`,
  as in `jul10-charter/scripts/stemify.sh`). Source stream: format 251, Opus, 48 kHz,
  ~143 kb/s. Resampled to 44.1 kHz stereo 16-bit with ffmpeg (swr, filter_size=64).
- Terms: copyrighted recording; personal/local analysis only.
- Other official uploads, not fetched: 2024 remaster
  (https://www.youtube.com/watch?v=q_MBxKPA8OE, Topic;
  https://www.youtube.com/watch?v=LJ6cate7SeQ, official channel) and the official music
  video (https://www.youtube.com/watch?v=_NfnXdXpjL0, 283 s, has extra video-only length).

## Arrangement, tuning and recording (with sources)

- **Personnel (LP1):** Steve Holmes (guitar), Mike Kinsella (vocals, guitar), Steve Lamos
  (drums, tambourine). Recorded May 1999 at Private Studios, Urbana IL, engineer/producer
  Brendan Gamble; 2024 remaster by Jonathan Pines (YouTube description of LJ6cate7SeQ;
  https://en.wikipedia.org/wiki/Never_Meant).
- **No bass guitar on this track.** Holmes: "there's only bass on two songs on the album"
  (For Sure; I'll See You When We're Both Not So Emotional), *Life of the Record* podcast
  notes, https://lifeoftherecord.com/american-football-notes. The stems agree (see below).
  The Songsterr bass part (credited to Nate Kinsella) follows the post-2014 live lineup.
- **Tunings (sounding, low→high):**
  - Holmes, lead (the famous riff, which he wrote): **F A C G C E** (FACGCE, open Fmaj9).
    Holmes and Kinsella say the tuning came from Victor Villarreal of Cap'n Jazz (Life of
    the Record).
  - Kinsella, rhythm: **F C C A C F** (Songsterr's track tuning).
  - Guitar.com (Huw Baines, 2019-04-02,
    https://guitar.com/features/interviews/american-football-mike-kinsella-steve-holmes/)
    gives "Holmes lining up E-G#-B-F#-B-D# and Kinsella in E-B-B-G#-B-E". These are the
    same two tunings a semitone lower, which suggests a half-step-down live tuning. The record
    itself is at concert pitch: the chroma of the guitar stem is F/A/C/G/E/D at +3 cents
    from A440 (measured here).
  - UG fan tab: Guitar 1 FACGCE; Guitar 2 "DAEAC#D capo 3" (sounds F C G C E F). This
    disagrees with Songsterr and Guitar.com on guitar 2.
- **Guitars/amps:** in 1999 Holmes played a Mexican Telecaster and Kinsella a borrowed
  guitar. "We didn't own a guitar pedal ... It was so clean and dry" (Holmes, Guitar.com).
  Songsterr labels the parts Fender American Elite Telecaster (Holmes) and Telecaster
  (Kinsella), which are their current guitars. No amp is documented for LP1.
- **Every guitar is doubled.** Kinsella: "we'll double every guitar on the album". Played live
  with no click track (Life of the Record). So expect tempo drift and a stereo double of each
  part.
- **Meter/tempo:** mostly 6/4. The verse groups eighths as 4-3-3-3-3-4-4 (UG tab notes).
  Songsterr gives 72 BPM. Onset autocorrelation of the drum stem here peaks at 71.8 and
  143.6 BPM. Key centre: F (Fmaj9/Lydian colour from the open tuning).
- **Form landmarks (from the stem timeline):** 0–4 s short pre-roll fragment, then ~6 s of
  near-silence. ~10 s solo guitar riff (centred, guitar-stem L/R corr 0.96) with drums.
  ~30 s second guitar enters and the guitars spread wide (L/R corr ~0.2). ~50 s vocals.
  ~100–130 s quieter drums. Fade ~250–268 s.

## Stem separation

- Tooling: `jul10-charter/scripts/stemify.sh` → Demucs in `~/.charter-stems-venv` (demucs
  4.1.0, torch 2.13, Apple MPS). Used read-only. Charter's own Rust/ONNX path is
  2/4-stem only. Model **htdemucs_6s** (adefossez/HTDemucs-6s, already in the HF cache).
  Command:
  `demucs -n htdemucs_6s -d mps --shifts 2 --int24 -o stems --filename "{stem}.{ext}" never-meant.wav`
  (25 s wall).
- Levels (whole song; mix RMS −11.7 dBFS):

  | stem | RMS dBFS | rel. mix | energy % | L/R corr | notes |
  |---|---|---|---|---|---|
  | guitar | −13.8 | −2.1 dB | 79.0 | 0.23 | both guitars (and their doubles) in one stem |
  | drums | −22.1 | −10.4 dB | 11.6 | 0.81 | clean |
  | vocals | −23.3 | −11.6 dB | 8.8 | 0.95 | −50 to −80 dBFS in instrumental sections |
  | bass | −35.0 | −23.2 dB | 0.6 | 0.99 | sporadic bursts at C3/G2/A2 (98–132 Hz): low guitar strings, not a bass line |
  | piano | −54.6 | −42.9 dB | 0.0 | 0.96 | intro guitar harmonics leak here (−37 to −50 dBFS, 16–28 s) |
  | other | −61.3 | −49.6 dB | 0.0 | 0.21 | essentially empty |

  Residual (mix − Σstems): −31.0 dBFS (−19.3 dB rel. mix). Pairwise mono-stem
  correlations are all ≤ 0.07.
- Verdict: guitar/drums/vocals separate cleanly. For a guitar-only reference, use
  `guitar.wav` and optionally add back `bass.wav` and `piano.wav`, since they hold small amounts of guitar.
  The two guitar parts share one stem. Because every guitar is doubled, an L/R channel split
  probably will not isolate Holmes vs Kinsella cleanly. A tab-guided resynthesis/score is
  the better route.

## Tabs / scores (links only unless noted; nothing behind login/paywall fetched)

- **Official:** *American Football: Transcriptions and Tablature*, transcribed by Nate
  Kinsella. Guitar, bass, trumpet and vocal for LP1 and the 1998 EP, 144 pp, softcover,
  US$20, in stock at Polyvinyl (checked 2026-10-01):
  https://www.polyvinylrecords.com/products/american-football-american-football-transcriptions-and-tablature-book
  (also https://americanfootball.bandcamp.com/merch/book-american-football-transcriptions-and-tablature).
  This is the authoritative source and needs a purchase.
- **Songsterr** (free to view in browser, with the multi-track player; Plus subscription
  for extra features): https://www.songsterr.com/a/wsa/american-football-never-meant-tab-s25202
  (tracks: Holmes lead FACGCE, Kinsella overdub FACGCE, Kinsella rhythm FCCACF, bass EADG,
  drums, tambourine, vocals, "ambience" pad; 72 BPM). Track tunings were read from the
  public page metadata. Tab data was not saved.
- **Ultimate Guitar:** free fan tab ver. 2, 206 votes, 4.81 (saved as
  `tabs/ug-tab-979718.txt` on 2026-10-01 from the public page, no login):
  https://tabs.ultimate-guitar.com/tab/american-football/never-meant-tabs-979718.
  UG "Official" tab (https://tabs.ultimate-guitar.com/tab/american-football/never-meant-official-2451753)
  is UG Pro (paywalled), not accessed.
- **gtdb** tuning database: https://gtdb.org/facgce/artists/american-football/62/tab/187
- **MuseScore** user arrangements (view in browser; download needs a MuseScore login, and
  Pro for some). Not downloaded:
  https://musescore.com/user/27791559/scores/9936124 (guitar/bass/drums/trumpet),
  https://musescore.com/user/26982208/scores/4895235 (guitar/drums trio).

"""Fetch GAPS pieces for local fitting: annotations from the GAPS v1 archive, audio from
YouTube with the user's Chrome cookies (as authorised by the user, 2026-10-01).

Everything lands in research/strings/midi/gaps/<slug>/ (git-ignored): the score
(MusicXML), the fine-aligned MIDI, the downbeat syncpoints, the recording as 48 kHz WAV
and SOURCE.txt. GAPS v1 annotations: CC BY-NC-SA 4.0. Recordings are never committed
or published; only derived timing and dynamics are.

    build/body-venv/bin/python tools/gaps_fetch.py [<gaps-id> ...]
"""
import csv,json,re,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];GAPS=ROOT/'research/strings/midi/gaps'
ARCHIVE=ROOT/'research/strings/downloads/gaps/gaps_v1_no_audio.zip'   # Zenodo 13962272 (git-ignored)
PIECES={      # GAPS id -> slug: public-domain original guitar works whose performances follow the score
              # literally (the strict MIDI-to-score match passes; repeats as written)
    '223_Z41wc':'sor-op35-22','391_Bk1wc':'sor-op35-17','293_7Sswc':'giuliani-op100-11','055_cV1wc':'carulli-op241-5',
    '164_LM1wc':'carcassi-op60-7','031_vpswc':'mertz-gebeth','341_1M1wc':'mertz-unruhe','036_SN1wc':'molino-romanza',
    '291_3Sswc':'legnani-caprice-7','290_MY1wc':'paganini-sonata-34'}


def composer(r):
    m=re.search(r'([A-ZÁÉÍÓÚ][^\n()]+?)\s*\((\d{4})\s*[-–]\s*(\d{4})\)',(r.get('composers') or '')+' '+(r.get('subtitle') or ''))
    return (m.group(1).strip(),m.group(2),m.group(3)) if m else ('','','')


def main():
    rows={r['id']:r for r in csv.DictReader(open(GAPS/'metadata.csv'))}
    ids=sys.argv[1:] or list(PIECES)
    archive=zipfile.ZipFile(ARCHIVE) if ARCHIVE.exists() else None
    for gid in ids:
        r=rows[gid];h=r['scorehash'];slug=PIECES.get(gid,gid);d=GAPS/slug;d.mkdir(parents=True,exist_ok=True)
        for src,dst in ((f'gaps_v1/musicxml/{h}.xml',f'{h}.xml'),(f'gaps_v1/midi/{h}-fine-aligned.mid',f'{h}-fine-aligned.mid'),(f'gaps_v1/syncpoints/{h}-syncpoints.json',f'{h}-syncpoints.json')):
            if not (d/dst).exists():(d/dst).write_bytes(archive.read(src))
        wav=d/f'{h}.wav'
        if not wav.exists():
            tmp=d/f'{h}.download'
            subprocess.run(['yt-dlp','--no-playlist','--cookies-from-browser','chrome','-f','bestaudio','-x','--audio-format','wav','-o',str(tmp)+'.%(ext)s',
                            f"https://www.youtube.com/watch?v={r['yt_id']}"],check=True,capture_output=True)
            got=next(d.glob(f'{h}.download.*'))
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(got),'-ar','48000',str(wav)],check=True);got.unlink()
        name,born,died=composer(r)
        (d/'SOURCE.txt').write_text(f"GAPS v1 (Zenodo 13962272, CC BY-NC-SA 4.0): {r['title']} — {name} ({born}–{died}).\n"
            f"GAPS id {gid}, scorehash {h}, YouTube {r['yt_id']} (\"{r['video_title']}\").\n"
            "MusicXML (ClassClef/Soundslice export, string/fret TAB), fine-aligned MIDI, downbeat syncpoints.\n"
            "Audio fetched from YouTube on 2026-10-01 at the user's request (yt-dlp, the user's Chrome cookies),\n"
            "converted to 48 kHz WAV. Local research only: never redistribute or publish the recording.\n")
        (d/'meta.json').write_text(json.dumps(dict(gaps_id=gid,scorehash=h,slug=slug,title=r['title'],composer=name,born=born,died=died,youtube=r['yt_id'],video_title=r['video_title']),ensure_ascii=False,indent=1)+'\n')
        print(slug,'ok',flush=True)


if __name__=='__main__':main()

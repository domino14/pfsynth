"""Pull selected AG-PT-set audio files without downloading the 6.7 GB archive.

The Zenodo zip holds aGPTset/data/audio.zip stored (uncompressed), so single members of
the inner zip are read with HTTP range requests. Usage:
    build/body-venv/bin/python tools/agpt_fetch.py
"""
import csv,io,struct,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'research/strings/downloads/ag-pt-set'
URL='https://zenodo.org/records/10159492/files/aGPTset_z.zip?download=1'


class Http(io.RawIOBase):
    def __init__(s,url):
        r=urllib.request.urlopen(urllib.request.Request(url,method='HEAD'));s.size=int(r.headers['Content-Length']);s.url=r.url;s.pos=0
    def seekable(s):return True
    def readable(s):return True
    def tell(s):return s.pos
    def seek(s,o,w=0):s.pos=o if w==0 else s.pos+o if w==1 else s.size+o;return s.pos
    def readinto(s,b):
        n=min(len(b),s.size-s.pos)
        if n<=0:return 0
        d=urllib.request.urlopen(urllib.request.Request(s.url,headers={'Range':f'bytes={s.pos}-{s.pos+n-1}'})).read();b[:len(d)]=d;s.pos+=len(d);return len(d)


class Window(io.RawIOBase):
    def __init__(s,base,start,size):s.b=base;s.start=start;s.size=size;s.pos=0
    def seekable(s):return True
    def readable(s):return True
    def tell(s):return s.pos
    def seek(s,o,w=0):s.pos=o if w==0 else s.pos+o if w==1 else s.size+o;return s.pos
    def readinto(s,buf):
        n=min(len(buf),s.size-s.pos)
        if n<=0:return 0
        s.b.seek(s.start+s.pos);d=s.b.read(n);buf[:len(d)]=d;s.pos+=len(d);return len(d)


def inner_zip():
    f=Http(URL);outer=zipfile.ZipFile(io.BufferedReader(f,1<<16));info=outer.getinfo('aGPTset/data/audio.zip');assert info.compress_type==0
    f.seek(info.header_offset);h=f.read(30);nl,el=struct.unpack('<HH',h[26:30])
    return zipfile.ZipFile(io.BufferedReader(Window(f,info.header_offset+30+nl+el,info.file_size),1<<20))


def member_bytes(base_offset,info):
    """One member of the inner zip with a single HTTP range request (plus its 30-byte header)."""
    import zlib
    get=lambda a,n:urllib.request.urlopen(urllib.request.Request(URL,headers={'Range':f'bytes={a}-{a+n-1}'}),timeout=120).read()
    h=get(base_offset+info.header_offset,30);nl,el=struct.unpack('<HH',h[26:30])
    data=get(base_offset+info.header_offset+30+nl+el,info.compress_size)
    return data if info.compress_type==0 else zlib.decompress(data,-15)


def main():
    """Technique 4 (harmonics) files, and technique 7 (over the soundhole) files with the
    same player, string and intensity as a harmonic file: the ordinary notes to pair with."""
    from concurrent.futures import ThreadPoolExecutor
    labels=list(csv.DictReader(open(DEST/'note_labels.csv')))
    harm=sorted({r['audio_file_path'] for r in labels if r['expressive_technique_id']=='4'})
    sig=lambda f:(f.split('_')[3],f.split('_')[-3],f.split('_')[-2])      # allstringN, intensity, player
    want={sig(f) for f in harm}
    normal=sorted({r['audio_file_path'] for r in labels if r['expressive_technique_id']=='7' and sig(r['audio_file_path']) in want})
    f=Http(URL);outer=zipfile.ZipFile(io.BufferedReader(f,1<<16));info=outer.getinfo('aGPTset/data/audio.zip')
    f.seek(info.header_offset);h=f.read(30);nl,el=struct.unpack('<HH',h[26:30]);base=info.header_offset+30+nl+el
    z=zipfile.ZipFile(io.BufferedReader(Window(f,base,info.file_size),1<<20));members={i.filename.split('/')[-1]:i for i in z.infolist()}
    jobs=[(DEST/'techniques_4',n) for n in harm]+[(DEST/'techniques_7',n) for n in normal]
    for d,_ in jobs:d.mkdir(exist_ok=True)
    jobs=[(d,n) for d,n in jobs if not (d/n).exists() and n in members]
    print(len(harm),'harmonic files,',len(normal),'paired ordinary files;',len(jobs),'to fetch',flush=True)
    def one(job):
        d,n=job
        for attempt in range(3):
            try:
                data=member_bytes(base,members[n]);tmp=d/(n+'.part');tmp.write_bytes(data);tmp.replace(d/n);return n
            except Exception as e:err=e
        return f'FAILED {n}: {err}'
    with ThreadPoolExecutor(6) as pool:
        for k,r in enumerate(pool.map(one,jobs),1):
            if r.startswith('FAILED') or k%20==0:print(k,r,flush=True)
    print('done',flush=True)


if __name__=='__main__':main()

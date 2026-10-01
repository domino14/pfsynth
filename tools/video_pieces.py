"""Per-piece settings for the performance videos (piece_video_audio.py, piece_video.py).
Pure data: imported from both the body-venv (audio) and the video-venv (drawing)."""

SUBTITLE='a physically modelled guitar · every note synthesized, no samples'
BODY_CREDIT='measured response of a {maker} guitar{where} (Robert Mores, Zenodo 4604577, CC BY 4.0)'
GAPS='aligned in GAPS (Riley, Guo, Edwards & Dixon, ISMIR 2024)'

PIECES={
    'sonatina':dict(
        clip='guitar-sonatina-harmonics',out='sonatina-iii',body='g54',room='guitar-room-fit-sonatina.json',
        tuning=['e','B','G','D','A','D'],
        label='JORGE MOREL',title='Sonatina III',
        card=('Jorge Morel','Sonatina III','played by a physically modelled guitar, following Inon Međugorac’s interpretation'),
        performer='Inon Međugorac',
        credits_title=('Sonatina III','Jorge Morel (1931–2021)'),
        sound='every note synthesized: modal nylon strings with a nonlinear pluck, finger-touch harmonics',
        score='GAPS MusicXML (CC BY-NC-SA 4.0), engraved with Verovio'),
    'bach':dict(
        clip='guitar-bach-full',out='bach-prelude-bwv1006a',body='auto',room='guitar-room-fit-refined.json',
        tuning=['e','B','G','D','A','E'],
        label='JOHANN SEBASTIAN BACH · BWV 1006a · ARR. STEFAN APKE',title='Prelude',
        card=('Johann Sebastian Bach','Prelude','from BWV 1006a, arranged by Stefan Apke · played by a physically modelled guitar, following Mateusz Kowalski’s interpretation'),
        performer='Mateusz Kowalski',
        credits_title=('Prelude from BWV 1006a','Johann Sebastian Bach (1685–1750) · arranged by Stefan Apke'),
        sound='every note synthesized: modal nylon strings with a nonlinear pluck; the first page’s slurs as physical hammer-ons and pull-offs',
        score='Stefan Apke’s arrangement (IMSLP, CC BY-SA 4.0) as encoded in GAPS (CC BY-NC-SA 4.0), engraved with Verovio'),
}


def body_text(g):
    """Maker and place as spelled in the source list (guitars.json)."""
    where=', '.join(x for x in (g.get('place',''),g.get('year','')) if x)
    return g['maker'],(', '+where if where else '')

"""Inventory SMF expression events without discarding channel or bend information.

Counts are evidence that messages exist, not labels for playing techniques.
No third-party dependencies; preserves downloaded MIDI unchanged.
"""
import collections
import hashlib
import json
import pathlib
import struct
import sys


def inspect(path):
    raw = path.read_bytes()
    assert raw[:4] == b'MThd', 'Not a Standard MIDI File'
    length = int.from_bytes(raw[4:8], 'big')
    fmt, tracks, division = struct.unpack('>HHH', raw[8:14])
    offset = 8 + length
    notes, bends, controls, texts = [], [], collections.Counter(), []
    channels = set()
    for track in range(tracks):
        assert raw[offset:offset+4] == b'MTrk'
        size = int.from_bytes(raw[offset+4:offset+8], 'big')
        data = raw[offset+8:offset+8+size]
        offset += size + 8
        i, tick, running = 0, 0, None

        def vlq():
            nonlocal i
            value = 0
            for _ in range(4):
                b = data[i]; i += 1
                value = (value << 7) | (b & 127)
                if not b & 128:
                    return value
            raise ValueError('Invalid VLQ')

        while i < len(data):
            tick += vlq()
            status = data[i]
            if status & 128:
                i += 1
            else:
                assert running is not None
                status = running
            if status == 255:
                kind = data[i]; i += 1
                size = vlq(); payload = data[i:i+size]; i += size
                if kind in (1, 3, 6, 7):
                    texts.append(payload.decode('utf-8', errors='replace'))
                running = None
            elif status in (240, 247):
                size = vlq(); i += size; running = None
            else:
                assert 128 <= status < 240
                running = status
                kind, channel = status & 240, status & 15
                size = 1 if kind in (192, 208) else 2
                payload = data[i:i+size]; i += size
                channels.add(channel + 1)
                if kind == 144 and payload[1]:
                    notes.append(payload[0])
                elif kind == 224:
                    bends.append(payload[0] + (payload[1] << 7) - 8192)
                elif kind == 176:
                    controls[payload[0]] += 1
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                format=fmt, tracks=tracks, division=division,
                notes=len(notes), note_range=[min(notes), max(notes)] if notes else [],
                channels=sorted(channels), pitch_bends=len(bends),
                nonzero_bends=sum(v != 0 for v in bends),
                bend_range_raw=[min(bends), max(bends)] if bends else [],
                cc_counts=dict(sorted(controls.items())), text=texts)


if __name__ == '__main__':
    root = pathlib.Path(sys.argv[1])
    result = []
    for path in sorted(root.rglob('*')):
        if path.suffix.lower() in ('.mid', '.midi'):
            try:
                result.append(inspect(path))
            except Exception as e:
                result.append(dict(path=str(path), error=str(e)))
    print(json.dumps(result, indent=2))

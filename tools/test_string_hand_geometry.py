"""Regression checks for sequence fingering without changing performance events."""
import copy
import unittest
from string_hand_geometry import guitar_fingers, audit, geometry

class FingeringTests(unittest.TestCase):
    def test_chromatic_phrase_keeps_position(self):
        notes=[dict(start=i*.15,end=(i+1)*.15,pitch=64+f,string=1,fret=f) for i,f in enumerate([12,11,12])]
        before=copy.deepcopy(notes)
        guitar_fingers(notes)
        self.assertEqual([n['finger'] for n in notes],[4,3,4])
        self.assertEqual(len({n['hand_position'] for n in notes}),1)
        self.assertTrue(audit(notes)['passed'])
        for old,new in zip(before,notes):
            self.assertEqual(old,{k:new[k] for k in old})

    def test_held_finger_and_other_string(self):
        notes=[dict(start=0,end=.6,pitch=69,string=1,fret=5),dict(start=.15,end=.3,pitch=65,string=2,fret=6),dict(start=.3,end=.45,pitch=66,string=2,fret=7)]
        guitar_fingers(notes)
        self.assertTrue(audit(notes)['passed'])
        self.assertNotEqual(notes[0]['finger'],notes[1]['finger'])

    def test_conflicting_string_rejected(self):
        self.assertIsNone(geometry([(0,0,5),(1,0,7)]))

    def test_barre_cannot_cross_open_string(self):
        self.assertIsNone(geometry([(0,0,5),(1,2,5),(2,1,0)],fixed={0:1,1:1}))

    def test_bad_position_detected(self):
        n=[dict(start=0,end=1,pitch=76,string=1,fret=12,finger=1,hand_position=1)]
        self.assertFalse(audit(n)['passed'])

class EditionTests(unittest.TestCase):
    def test_published_opening_and_performance_preserved(self):
        import json
        from guitar_edition_fingering import apply_edition,ROOT
        notes=json.loads((ROOT/'build/stringlab/guitar-bach-performance-events.json').read_text())
        before=[(n['start'],n['end'],n['pitch'],n['velocity']) for n in notes]
        apply_edition(notes)
        self.assertEqual(before,[(n['start'],n['end'],n['pitch'],n['velocity']) for n in notes])
        self.assertEqual([n['finger'] for n in notes[1:7]],[4,3,4,4,1,4])
        self.assertEqual([n['fret'] for n in notes[1:7]],[12,11,12,7,4,7])
        self.assertEqual(sum('finger' not in n for n in notes),19)
        self.assertTrue(audit(notes)['passed'])

if __name__=='__main__':unittest.main()

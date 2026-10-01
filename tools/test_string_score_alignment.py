"""Regression checks for the note-level printed score and the fitted-dynamics helpers."""
import json
import unittest
import numpy as np
from string_score_alignment import engraved_heads,attach,OUT
from guitar_dynamics_fit import velocities_from,V0,EXP,LIMIT_DB

class ScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g,cls.heads,cls.report=engraved_heads('clefscan')
        _,cls.vector,cls.vreport=engraved_heads('pdf')

    def test_clefscan_heads_identified_in_matching_measures(self):
        # The GAPS MusicXML departs from Apke's page from measure 13 on.
        self.assertEqual(self.report['matched_measures'],list(range(1,13)))
        self.assertEqual(self.vreport['matched_measures'],list(range(1,13)))

    def test_clefscan_positions_agree_with_pdf_vectors(self):
        for key,v in self.vector.items():
            h=self.heads[key]
            self.assertEqual((h['system'],h['measure']),(v['system'],v['measure']))
            self.assertLess(np.hypot(h['x']-v['x'],h['y']-v['y']),2.5)

    def test_printed_fingers_match_musicxml(self):
        # The only disagreements are MusicXML open-string 0s with no printed digit.
        self.assertEqual(self.report['fingers_agree'],93)
        self.assertTrue(all(m['musicxml']==0 and m['printed'] is None for m in self.report['finger_mismatches']))

    def test_every_excerpt_note_sits_under_its_head(self):
        data,_=attach(json.loads((OUT/'stringlab.json').read_text()))
        clip=next(c for c in data['clips'] if c['id']=='guitar-bach-performance')
        notes=clip['score']['notes'];frames=clip['score']['engraving']['systems']
        self.assertEqual(sum('ink' in n for n in notes),len(notes))
        for f in frames:
            self.assertTrue((OUT/f['image']).exists())
            times=[t for t,_ in f['points']];xs=[x for _,x in f['points']]
            self.assertEqual(times,sorted(times));self.assertEqual(xs,sorted(xs))
        self.assertEqual([f['start'] for f in frames[1:]],[f['end'] for f in frames[:-1]])

class DynamicsTests(unittest.TestCase):
    def test_median_note_stays_at_reference_velocity(self):
        gain=np.array([1,2,.5,1.5,.8,1.2,1]);share=np.full(len(gain),.6)
        v,_=velocities_from(gain,np.full(len(gain),100.),share)
        self.assertAlmostEqual(float(np.median(v)),V0)

    def test_unidentified_note_follows_its_phrase(self):
        gain=np.ones(9);gain[4]=1e-6;share=np.full(9,.6);share[4]=0
        v,raw=velocities_from(gain,np.full(9,100.),share)
        self.assertLess(raw[4],1)                 # the raw fit collapses
        self.assertAlmostEqual(v[4],v[0])         # the estimate leans on neighbours

    def test_trusted_outlier_is_limited(self):
        gain=np.ones(9);gain[4]=100.;share=np.full(9,.9)
        v,_=velocities_from(gain,np.full(9,100.),share)
        self.assertAlmostEqual(20*EXP*np.log10(v[4]/v[0]),LIMIT_DB,places=6)

if __name__=='__main__':unittest.main()

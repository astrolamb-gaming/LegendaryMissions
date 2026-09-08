"""The stock crews, as data.

A roster is authored text, so its failures are authoring failures: a duplicate key silently
replaces a person, two people with one name are indistinguishable on a Director bridge wall,
and a `Console:` nothing registers stays empty forever. None of those raise - the file
parses either way and the game just shows the wrong crew.

Static: it reads the .amd and checks it. No engine, no page, no client.

    python -m unittest test_crew_rosters
"""
import os
import unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

from sbs_utils.procedural.amd import amd_read_text
from sbs_utils.procedural.amd_doc import amd_document
from sbs_utils.procedural.amd_crew import amd_crew_data, crew_from_document, crew_validate


HERE = os.path.dirname(os.path.abspath(__file__))
ROSTERS = os.path.join(HERE, "crew_rosters.amd")

#: The stock watch has to be able to crew a whole SHIP, not a bridge - a dozen consoles, a
#: second science station, a hangar of pilots. Below this it runs out and the rest of the
#: ship falls through to automatic names, which is what having a cast is meant to avoid.
WATCH_SIZE = 40


def _rosters():
    return crew_from_document(amd_document(amd_read_text(ROSTERS), data_parser=amd_crew_data))


class TestStockRosters(unittest.TestCase):
    def setUp(self):
        self.rosters = {r.key: r for r in _rosters()}

    def test_all_three_are_declared(self):
        self.assertEqual(set(self.rosters), {"tsn_watch", "deep_watch", "free_traders"})

    def test_the_watch_is_deep_enough_to_crew_a_ship(self):
        self.assertGreaterEqual(len(self.rosters["tsn_watch"].members), WATCH_SIZE)

    def test_the_skeleton_watches_stay_small_on_purpose(self):
        """Deep Watch has fewer people than stations BY DESIGN - consoles nobody covers
        read as unmanned, which is the whole point of a skeleton watch."""
        self.assertLess(len(self.rosters["deep_watch"].members), 8)

    def test_nobody_shares_a_key(self):
        for key, roster in self.rosters.items():
            keys = [m.key for m in roster.members]
            self.assertEqual(len(keys), len(set(keys)), key)

    def test_nobody_shares_a_name(self):
        """Two people with one name are the same person on every readout that shows one."""
        for key, roster in self.rosters.items():
            names = [m.name.lower() for m in roster.members]
            self.assertEqual(sorted(names), sorted(set(names)), key)

    def test_everyone_has_a_rank_or_deliberately_none(self):
        """Free Traders have no ranks - nobody out here has one. Everyone else does."""
        self.assertTrue(all(m.rank for m in self.rosters["tsn_watch"].members))
        self.assertTrue(not any(m.rank for m in self.rosters["free_traders"].members))

    def test_no_station_is_named_twice_in_the_watch(self):
        """A second person on one console is legal - they fill it in order - but in a cast
        this size it is a copy-paste, not a decision."""
        named = [m.console for m in self.rosters["tsn_watch"].members if m.console]
        self.assertEqual(sorted(named), sorted(set(named)))

    def test_the_watch_covers_every_crewed_station(self):
        named = {m.console for m in self.rosters["tsn_watch"].members if m.console}
        self.assertEqual(named, {"mainscreen", "helm", "weapons", "science",
                                 "engineering", "comms", "hangar"})

    def test_the_rest_float(self):
        """A member with no Console: is offered to any seat nobody was written for, which
        is what makes the cast deep rather than merely long."""
        floating = [m for m in self.rosters["tsn_watch"].members if not m.console]
        self.assertGreaterEqual(len(floating), 30)

    def test_everybody_says_which_face_they_wear(self):
        """A member with no `Face:` gets one ROLLED, and a terran face has a gender axis -
        so without `Gender:` the roll is a coin toss against the name written above it."""
        for key, roster in self.rosters.items():
            for m in roster.members:
                self.assertTrue(m.gender, f"{key}/{m.key} ({m.name}) declares no Gender")
                self.assertIn(m.gender, ("male", "female", "fluid"), m.key)

    def test_the_declared_gender_agrees_with_the_name(self):
        """Where the library's own pool knows a given name, the roster must not contradict
        it - the two would then disagree about the same person."""
        from sbs_utils.procedural.crew import crew_name_gender
        for key, roster in self.rosters.items():
            for m in roster.members:
                known = crew_name_gender(m.name)
                if known:
                    self.assertEqual(m.gender, known, f"{key}/{m.key} ({m.name})")

    def test_it_is_not_one_gender_wearing_two_hats(self):
        """A watch bill of forty people should look like a crew."""
        watch = self.rosters["tsn_watch"].members
        for want in ("male", "female"):
            share = len([m for m in watch if m.gender == want]) / len(watch)
            self.assertGreater(share, 0.3, f"only {share:.0%} of the watch is {want}")

    def test_the_library_validator_is_happy(self):
        """`check_files=False`: no shipData is loaded here, and none of these bind a hull."""
        bad = [p for p in crew_validate(list(self.rosters.values()), check_files=False)
               if p[1] in ("error", "warning")]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()

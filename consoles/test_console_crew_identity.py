"""The picker's identity line: who this console is about to be.

The console picker used to offer an empty "Crew person Name" box. Almost nobody filled it
in, and the name was only worked out AFTER the console was chosen - so the one screen where
a player is deciding what to be was the one screen that could not say who they were.

This drives the helper the row binds to. It is the real library resolution behind it
(`crew_preview_post`), so a roster declared for a hull, an automatic name, and a name the
player typed all answer here exactly as they will on the console.

    python -m unittest test_console_crew_identity
"""
import unittest

from sbs_utils.fs import test_set_exe_dir
test_set_exe_dir()

import sbs_utils.mast_sbs.story_nodes            # noqa: F401  breaks a circular import
from cosmos_dev.mock import sbs
from sbs_utils.helpers import Context, FakeEvent, FrameContext
from sbs_utils.spaceobject import SpaceObject
from sbs_utils.procedural.amd_doc import amd_document
from sbs_utils.procedural.amd_crew import amd_crew_data, crew_from_document
from sbs_utils.procedural.execution import set_shared_variable
import sbs_utils.procedural.crew as crew

from common_console_selection import console_crew_identity


#: A cast bound to a HULL - the mod tier, and the one the picker could never reach before,
#: because it is choosing a hull for a ship that does not exist yet.
CAST = """# [Rosters](rosters)

## [Galaxy Class](galaxy)
---
crew
Hull: tsn_battle_cruiser
Race: terran
---

### [Geordi La Forge](geordi)
---
Rank: Lt. Commander
Console: engineering
---

### [Data](data)
---
Rank: Lt. Commander
Console: science
---
"""

CID = 7
SLOT = 0
HULL = "tsn_battle_cruiser"
BARE = "tsn_light_cruiser"          # no cast declared for it


class IdentityCase(unittest.TestCase):
    def setUp(self):
        sbs.create_new_sim()
        FrameContext.context = Context(sbs.sim, sbs, FakeEvent())
        SpaceObject.clear()
        crew.crew_clear()
        crew.crew_names_clear()
        set_shared_variable("CREW_SELECT", "")
        crew.crew_declare(crew_from_document(amd_document(CAST, data_parser=amd_crew_data)))
        self.addCleanup(crew.crew_clear)
        self.addCleanup(crew.crew_names_clear)

    def ident(self, console, hull=HULL, slot=SLOT, name="", face="", portrait="", pick=""):
        return console_crew_identity(CID, slot, hull, console, name, face, portrait, pick)


class TestWhatTheLineSays(IdentityCase):
    def test_a_hull_bound_cast_answers_with_no_ship_at_all(self):
        """The whole reason the hull is passed. During setup there IS no ship."""
        self.assertEqual(self.ident("engineering").label, "Lt. Commander Geordi La Forge")

    def test_the_person_follows_the_highlighted_station(self):
        self.assertEqual(self.ident("science").name, "Data")
        self.assertEqual(self.ident("engineering").name, "Geordi La Forge")

    def test_a_hull_with_no_cast_still_names_the_seat(self):
        line = self.ident("helm", hull=BARE)
        self.assertTrue(line.name, "an unnamed console is what this feature exists to fix")
        self.assertTrue(line.face, "and it should have a face to go with it")

    def test_what_the_player_typed_wins(self):
        self.assertEqual(self.ident("engineering", name="Doug").label, "Doug")

    def test_nobody_reads_as_a_prompt_rather_than_a_blank(self):
        """CREW_AUTONAME off and no roster. A blank line looks broken; this asks."""
        from sbs_utils.procedural.settings import settings_get_defaults
        settings_get_defaults()["CREW_AUTONAME"] = False
        self.addCleanup(settings_get_defaults().__setitem__, "CREW_AUTONAME", True)
        self.assertEqual(self.ident("helm", hull=BARE).label, "No crew name")

    def test_the_likeness_is_one_markdown_value_for_both_kinds(self):
        """A text area speaks face:// and image://, so nothing swaps widgets when a roster
        answers with a photograph."""
        self.assertIn("face://", self.ident("engineering").markdown)


class TestItIsAPreview(IdentityCase):
    def test_it_takes_no_seat(self):
        self.ident("engineering")
        self.assertEqual(crew.crew_seat_count(), 0)

    def test_clicking_around_the_station_list_settles(self):
        """A player flicking through consoles must not burn a new person per click."""
        first = [self.ident(c).name for c in ("helm", "weapons", "science", "engineering")]
        second = [self.ident(c).name for c in ("helm", "weapons", "science", "engineering")]
        self.assertEqual(first, second)
        self.assertEqual(len(set(first)), len(first), "and no two stations are one person")

    def test_a_different_slot_is_a_different_crew(self):
        self.assertNotEqual(self.ident("helm", hull=BARE, slot=0).name,
                            self.ident("helm", hull=BARE, slot=1).name)

    def test_the_preview_is_what_the_console_gets(self):
        from sbs_utils.gui import GuiClient
        from sbs_utils.procedural.inventory import set_inventory_value
        GuiClient(CID)
        set_inventory_value(CID, "CONSOLE_TYPE", "helm")
        shown = self.ident("helm", hull=BARE)
        taken = crew.crew_assign(CID, None, "helm", hull=BARE, slot=SLOT)
        self.assertEqual(taken.name, shown.name)
        self.assertEqual(taken.face, shown.face)


if __name__ == "__main__":
    unittest.main()

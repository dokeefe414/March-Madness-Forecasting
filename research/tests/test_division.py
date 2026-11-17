"""2027 Division I reference join: source memberships, not conference guessing."""
import unittest
from forecast.division import parse_division_members, parse_ncaa_aliases, parse_ncaa_espn_ids, annotate_division
from forecast.selection import build_watchlist

GROUPS = """league,group_id,season,level,name
mbb,mbb:di,2027,subdivision,Division I
mbb,mbb:dii,2027,subdivision,Division II
mbb,mbb:di,2026,subdivision,Division I
mbb,mbb:big-south,2027,conference,Big South
mbb,mbb:metro,2027,conference,Metro
"""
MEMBERS = """league,season,team_id,team_name,subdivision_id,conference_id
mbb,2027,1,College A,mbb:di,mbb:big-south
mbb,2027,2,College B,mbb:dii,mbb:other
mbb,2027,3,College C,mbb:di,mbb:metro
mbb,2026,4,Old Team,mbb:di,mbb:big-south
"""


ALIASES = """league,team_id,team_id_source,source,source_id,id_kind,name_kind,value,valid_from,valid_to
mbb,1,espn,ncaa,101,school,name,Duke,2024,2027
mbb,2,espn,ncaa,102,school,name,Northwestern St,2024,2027
mbb,3,espn,ncaa,103,school,name,College C,2025,2027
mbb,4,espn,ncaa,104,school,name,Old Team,2020,2026
mbb,5,espn,ncaa,105,school,name,Future Team,2028,2029
mbb,99,espn,fox,500,team,name,Duke,2026,2027
"""

SOURCE_IDS = """season,ncaa_team_id,espn_team_id,match_method
2026-27,101,1,exact
2026-27,102,2,alias
2025-26,999,1,exact
2026-27,103,,unmatched
"""

class DivisionMembershipTests(unittest.TestCase):
    def test_source_division_and_unknown_are_not_assumed(self):
        members = parse_division_members(GROUPS, MEMBERS)
        rows = [{"name":"College A"},{"name":"College B"},{"name":"College C"},
                {"name":"Unknown new team"}]
        report = annotate_division(rows, members)
        self.assertEqual([x["divisionIConfirmed"] for x in rows],
                         [True, False, True, None])
        self.assertEqual(report["divisionIConfirmed"], 2)
        self.assertEqual(report["sourceDivisionIConferenceGroups"], 2)
        self.assertEqual(rows[0]["divisionConferenceGroupId"], "mbb:big-south")
        self.assertEqual(rows[0]["divisionConferenceGroupName"], "Big South")
        self.assertIsNone(rows[1]["divisionConferenceGroupId"])
        self.assertEqual(rows[2]["divisionConferenceGroupId"], "mbb:metro")
        self.assertEqual(rows[2]["divisionConferenceGroupName"], "Metro")
        self.assertIsNone(rows[3]["divisionConferenceGroupId"])
        self.assertEqual(report["unmatchedRatedTeams"], 1)

    def test_conflicting_alias_dropped(self):
        conflict = MEMBERS + "mbb,2027,55,College A,mbb:dii,mbb:other\n"
        members = parse_division_members(GROUPS, conflict)
        self.assertNotIn("college a", members)

    def test_valid_dated_ncaa_alias_maps_espn_group_to_ncaa_school(self):
        group_names = MEMBERS.replace("College A", "Duke Blue Devils")
        catalog = parse_division_members(GROUPS, group_names, ALIASES)
        self.assertIn("duke", catalog)
        self.assertTrue(catalog["duke"]["divisionIConfirmed"])
        rows = [{"name": "Duke"}, {"name": "Northwestern St"}]
        coverage = annotate_division(rows, catalog)
        self.assertEqual([row["divisionIConfirmed"] for row in rows], [True, False])
        self.assertEqual(coverage["divisionIConfirmed"], 1)

    def test_provider_alias_date_window_and_collision_safety(self):
        links = parse_ncaa_aliases(ALIASES)
        self.assertEqual(links["duke"], "1")
        self.assertNotIn("old team", links)
        self.assertNotIn("future team", links)
        clash = ALIASES + "mbb,11,espn,ncaa,501,school,name,Duke,2026,2027\n"
        self.assertNotIn("duke", parse_ncaa_aliases(clash))
        with self.assertRaisesRegex(ValueError, "aliases missing fields"):
            parse_ncaa_aliases("team_name,team_id\nDuke,1")

    def test_source_2027_ncaa_id_to_espn_membership_even_when_names_differ(self):
        group_names = MEMBERS.replace("College A", "College A Tigers")
        members = parse_division_members(GROUPS, group_names,
                                         crosswalk_csv=SOURCE_IDS)
        self.assertTrue(members["ncaa-id:101"]["divisionIConfirmed"])
        teams = [{"name": "Totally different display text", "ncaaSourceTeamId": "101"},
                 {"name": "Another name", "ncaaSourceTeamId": "102"},
                 {"name": "No verified mapping", "ncaaSourceTeamId": "999"}]
        report = annotate_division(teams, members)
        self.assertEqual([x["divisionIConfirmed"] for x in teams], [True, False, None])
        self.assertEqual(report["seasonNCAAIdMatchedTeams"], 2)
        self.assertEqual(report["divisionIConfirmed"], 1)

    def test_conflicting_or_wrong_season_ncaa_numeric_id_is_rejected(self):
        ids = parse_ncaa_espn_ids(SOURCE_IDS)
        self.assertEqual(ids["101"], "1")
        self.assertNotIn("103", ids)
        self.assertNotIn("999", ids)
        bad = SOURCE_IDS + "2026-27,101,4,exact\n"
        self.assertNotIn("101", parse_ncaa_espn_ids(bad))
        with self.assertRaisesRegex(ValueError, "crosswalk missing fields"):
            parse_ncaa_espn_ids("season,id\n2026-27,101")

    def test_field_gate_excludes_undocumented_division(self):
        teams = [
            {"teamId":str(i), "name":str(i), "conference":"Group "+str(i%32),
             "conferenceVerified":True, "divisionIConfirmed":False if i==0 else None,
             "projectedRating":1600-i, "wins":2, "losses":0}
            for i in range(99)
        ]
        result = build_watchlist(teams, "2026-11-15")
        self.assertEqual(result["status"],"insufficient-coverage")
        self.assertEqual(result["teams"], [])

    def test_missing_group_ref_rejected(self):
        with self.assertRaisesRegex(ValueError,"subdivision missing"):
            parse_division_members(GROUPS.replace("Division I","Division 99"), MEMBERS)


if __name__=="__main__":
    unittest.main()

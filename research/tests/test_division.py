"""2027 Division I reference join: source memberships, not conference guessing."""
import unittest
from forecast.division import parse_division_members, annotate_division
from forecast.selection import build_watchlist

GROUPS = """league,group_id,season,level,name
mbb,mbb:di,2027,subdivision,Division I
mbb,mbb:dii,2027,subdivision,Division II
mbb,mbb:di,2026,subdivision,Division I
"""
MEMBERS = """league,season,team_id,team_name,subdivision_id,conference_id
mbb,2027,1,College A,mbb:di,mbb:big-south
mbb,2027,2,College B,mbb:dii,mbb:other
mbb,2027,3,College C,mbb:di,mbb:metro
mbb,2026,4,Old Team,mbb:di,mbb:big-south
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
        self.assertEqual(report["unmatchedRatedTeams"], 1)

    def test_conflicting_alias_dropped(self):
        conflict = MEMBERS + "mbb,2027,55,College A,mbb:dii,mbb:other\n"
        members = parse_division_members(GROUPS, conflict)
        self.assertNotIn("college a", members)

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

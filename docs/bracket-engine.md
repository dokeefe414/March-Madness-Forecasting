# NCAA bracket simulator: 64, 65, 68 and 76 entrants

Code: `web/lib/fullBracket.ts`, interface: `web/components/FullBracketLab.tsx`, regression tests: `web/scripts/test-bracket.mts`.

## Format evolution

| Tournament field | Entrants | Opening Round games | Main draw |
| --- | ---: | ---: | ---: |
| Original 64-team | 64 | 0 | 64 |
| One play-in | 65 | 1 | 64 |
| First Four era | 68 | 4 | 64 |
| **2027 expansion** | **76** | **12** | **64** |

The 76-team field is confirmed by [NCAA](https://www.ncaa.com/news/basketball-men/article/2026-05-07/how-2027-expanded-ncaa-tournament-and-march-madness-brackets-will-work). The 24 Opening Round participants play 12 games to fill 12 slots in the standard 64-team draw. **Real 2027 participants and seed positions are not announced yet**; the current UI only reconstructs sourced historical fields.

## Internal structure

Each of four seeded regions (historically W, X, Y, Z) has 16 seed positions ordered:

```text
1–16   8–9   5–12   4–13
6–11   3–14  7–10   2–15
```

A seed position contains exactly one entrant (direct main draw) or **two** entrants playing a preliminary game. Therefore 64 slots plus 4 extra entrants = 68, and 64 slots plus **12** extra entrants = 76. The program does not choose those 12 positions before sourced data is available.

Historical field inputs come from `web/public/tournaments/<year>.json` seed codes (for example `W16a`, `W16b`) and corresponding frozen season ratings. The parser rejects missing seed positions, unknown codes, repeat IDs and missing pre-tournament ratings. Incomplete 2026 tournament data is **not** accepted as a full reconstruction because First Four games/seed participants are missing.

## One seeded Monte Carlo run

1. In a paired slot, simulate Opening Round winner from neutral-site Elo probability.
2. Resolve 32 first-round matches in the specified slot order.
3. Resolve the next rounds to determine Round of 32 (32), Sweet 16 (16), Elite Eight (8) and Final Four (4).
4. For the Final Four **assume** region crossover W–X and Y–Z; actual NCAA national-semifinal geography varies historically and this is intentionally labeled a **scenario**, not verified historical placement.
5. Resolve semifinal finalists (2) and champion (1); repeat `runs` times with deterministic seeded RNG.
6. Return team advancement probabilities through every round, including opening-round win chance for play-in entrants.

Per simulation count invariants: `sum(round32)=32`, `sum(final4)=4`, `sum(titleGame)=2`, `sum(champion)=1`. Input is validated again before each simulation. Client simulation controls are capped at 20,000 in UI and 100,000 in library to bound workload.

## Tests

```bash
cd web
npm install
npm run test:bracket
npm run typecheck
npm run build
```

Test-generated mock fields of 64/65/68/76 entrants are **hermetic fixtures**, never published as NCAA results. They verify field counts, deterministic seeds, missing/duplicate teams and sum invariants.

## Statistical limits

All outcomes are conditional on known, correctly seeded entrants, frozen pre-tournament Elo and a simple neutral-court formula. The model does not predict field selection, injuries, roster changes, matchup styles, possession metrics or actual Final Four crossover. The 2027 bracket will require an official team-and-seed importer before there can be a legitimate live 76-team simulation.

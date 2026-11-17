import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { buildHistoricalField, buildFieldFromSlots, simulateFullBracket, SEED_ORDER, REGIONS } from "../lib/fullBracket.ts";

function makeField(extra: number) {
  let id = 0;
  const regions = REGIONS.map((code) => ({
    code,
    slots: SEED_ORDER.map((seed, i) => ({
      region: code, seed,
      teams: Array.from({length: 1 + (id++ < extra ? 1 : 0)}, (_, j) => {
        const unique = code + "-" + seed + "-" + j;
        return {teamId: unique, name: unique, rating: 1500 + seed, projectedRating: 1500 + seed, region: code, seed};
      }),
    })),
  }));
  return buildFieldFromSlots(2027, regions);
}
for (const [extra, expected] of [[0,64],[1,65],[4,68],[12,76]]) {
  test("supports verified " + expected + "-team bracket structure", () => {
    const field = makeField(extra);
    assert.equal(field.entrants.length, expected);
    assert.equal(field.openingRoundGames, extra);
    const result = simulateFullBracket(field, 160, 42);
    assert.equal(result.length, expected);
    assert.ok(Math.abs(result.reduce((s,x) => s + x.champion, 0) - 1) < 1e-10);
    assert.ok(Math.abs(result.reduce((s,x) => s + x.final4, 0) - 4) < 1e-10);
    assert.ok(Math.abs(result.reduce((s,x) => s + x.titleGame, 0) - 2) < 1e-10);
    assert.ok(Math.abs(result.reduce((s,x) => s + x.round32, 0) - 32) < 1e-10);
    const a = simulateFullBracket(field, 200, 42);
    const b = simulateFullBracket(field, 200, 42);
    assert.deepEqual(a, b);
    assert.notDeepEqual(a, simulateFullBracket(field, 200, 17));
  });
}
test("rejects incomplete field and repeated team", () => {
  const field = makeField(12);
  field.regions[0].slots[0].teams = [];
  assert.throws(() => simulateFullBracket(field, 100), /Invalid slot/);
  const duplicate = makeField(0);
  duplicate.regions[0].slots[0].teams[0].teamId = duplicate.regions[1].slots[0].teams[0].teamId;
  assert.throws(() => simulateFullBracket(duplicate, 100), /Each team/);
});

test("every eligible historical 1985–2025 NCAA archive reconstructs without invented entrants", () => {
  const index = JSON.parse(readFileSync("data/history-index.json", "utf8"));
  let checked = 0;
  const counts = new Map();
  for (const entry of index.seasons) {
    const y = entry.season;
    if (y > 2025 || y === 2020 || !entry.tournamentGames) continue;
    const archive = JSON.parse(readFileSync("public/tournaments/" + y + ".json", "utf8"));
    const snapshot = JSON.parse(readFileSync("public/seasons/" + y + ".json", "utf8"));
    const field = buildHistoricalField(archive, snapshot.teams);
    assert.ok([64, 65, 68].includes(field.entrants.length), "unexpected real format for " + y);
    assert.equal(field.regions.length, 4);
    counts.set(field.entrants.length, (counts.get(field.entrants.length) || 0) + 1);
    checked++;
  }
  assert.equal(checked, 40, "Historical NCAA held tournaments from 1985–2025 excluding canceled 2020");
  assert.ok(counts.has(64), "Expected original-era tournament fields");
  assert.ok(counts.has(68), "Expected First Four-era fields");
});
test("partial 2026 main draw cannot be mistaken for complete tournament", () => {
  const archive = JSON.parse(readFileSync("public/tournaments/2026.json", "utf8"));
  const snapshot = JSON.parse(readFileSync("public/seasons/2026.json", "utf8"));
  assert.throws(() => buildHistoricalField(archive, snapshot.teams), /Partial tournament/);
});

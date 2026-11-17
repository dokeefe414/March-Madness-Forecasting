/** Format-aware, reproducible NCAA tournament simulator.
 *
 * Accepts historical seeded fields of 64, 65, or 68 and future 76-team
 * fields with 12 Opening Round slots. It never invents missing teams.
 *
 * A seed slot may hold one entrant (direct to Round of 64), or exactly two
 * entrants (one opening-round game). Opening-round outcomes determine who
 * occupies that seed in the 64-team standard bracket.
 */
export type BracketTeam = {
  teamId: string;
  name: string;
  rating: number;
  projectedRating: number;
  region: string;
  seed: number;
};
export type BracketSlot = { region: string; seed: number; teams: BracketTeam[] };
export type BracketField = {
  season: number;
  regions: { code: string; slots: BracketSlot[] }[];
  entrants: BracketTeam[];
  openingRoundGames: number;
};
export type BracketArchive = {
  season: number;
  champion: string | null;
  mainDrawOnly: boolean;
  note?: string;
  teams: Record<string, string>;
  seeds?: Record<string, string>;
  games: Array<{ winnerId: string; loserId: string; winnerScore: number; loserScore: number; day?: number; round?: string }>;
};
export type BracketResult = {
  teamId: string;
  name: string;
  region: string;
  seed: number;
  round32: number;
  sweet16: number;
  elite8: number;
  final4: number;
  titleGame: number;
  champion: number;
  openingRoundWin: number | null;
};

export const REGIONS = ["W", "X", "Y", "Z"] as const;
/** Standard bracket Round-of-64 order; adjacent entrants face each other. */
export const SEED_ORDER = [1, 16, 8, 9, 5, 12, 4, 13, 6, 11, 3, 14, 7, 10, 2, 15];

export function buildHistoricalField(
  archive: BracketArchive,
  ratings: Array<{ teamId: string; name: string; rating: number; projectedRating: number }>
): BracketField {
  if (archive.mainDrawOnly) throw new Error("Partial tournament result archives cannot reconstruct opening-round entrants.");
  if (!archive.seeds || !Object.keys(archive.seeds).length) throw new Error("No sourced tournament seed list is available.");
  const ratingById = new Map(ratings.map((team) => [team.teamId, team]));
  const regionMap = new Map(REGIONS.map((r) => [r, new Map<number, BracketTeam[]>()]));
  const ids = new Set<string>();
  for (const [teamId, seedLabel] of Object.entries(archive.seeds)) {
    if (ids.has(teamId)) throw new Error("Duplicate team ID.");
    ids.add(teamId);
    const match = /^([WXYZ])(0[1-9]|1[0-6])([ab]?)$/.exec(seedLabel);
    if (!match) throw new Error("Unknown seeded field notation: " + seedLabel);
    const rating = ratingById.get(teamId);
    if (!rating || !Number.isFinite(rating.projectedRating) || !Number.isFinite(rating.rating)) {
      throw new Error("Missing pre-tournament rating for " + (archive.teams[teamId] || teamId));
    }
    const region = match[1];
    const seed = Number(match[2]);
    const slots = regionMap.get(region);
    if (!slots) throw new Error("Unsupported bracket region " + region);
    const entries = slots.get(seed) || [];
    entries.push({
      teamId, name: archive.teams[teamId] || rating.name,
      rating: rating.rating, projectedRating: rating.projectedRating, region, seed,
    });
    slots.set(seed, entries);
  }
  const regions = REGIONS.map((code) => {
    const raw = regionMap.get(code)!;
    const slots = SEED_ORDER.map((seed) => {
      const teams = raw.get(seed) || [];
      if (teams.length !== 1 && teams.length !== 2)
        throw new Error("Region " + code + " seed " + seed + " has " + teams.length + " teams; expected 1 or 2.");
      return { region: code, seed, teams };
    });
    return { code, slots };
  });
  const entrants = regions.flatMap((r) => r.slots.flatMap((slot) => slot.teams));
  const openingRoundGames = entrants.length - 64;
  if (![0, 1, 4, 12].includes(openingRoundGames)) {
    throw new Error("Expected a historical 64/65/68 field or 76-team field, got " + entrants.length);
  }
  return { season: archive.season, regions, entrants, openingRoundGames };
}

/** Allows seeded fields from a future verified 76-team field without guessing it. */
export function buildFieldFromSlots(
  season: number,
  regions: { code: string; slots: BracketSlot[] }[]
): BracketField {
  if (regions.length !== 4 || regions.some((r, i) => r.code !== REGIONS[i] || r.slots.length !== 16))
    throw new Error("Exactly four ordered regions with 16 standard seed slots are required.");
  for (const region of regions) {
    for (let i = 0; i < 16; i++) {
      const slot = region.slots[i];
      if (slot.region !== region.code || slot.seed !== SEED_ORDER[i] ||
          ![1, 2].includes(slot.teams.length) ||
          slot.teams.some((t) => !Number.isFinite(t.projectedRating) || !Number.isFinite(t.rating)))
        throw new Error("Invalid slot at " + region.code + " / " + SEED_ORDER[i]);
    }
  }
  const entrants = regions.flatMap((r) => r.slots.flatMap((s) => s.teams));
  if (new Set(entrants.map((t) => t.teamId)).size !== entrants.length)
    throw new Error("Each team can enter only one bracket slot.");
  if (![64, 65, 68, 76].includes(entrants.length))
    throw new Error("Field must have 64, 65, 68 or 76 entrants.");
  return { season, regions, entrants, openingRoundGames: entrants.length - 64 };
}

function seededRandom(seed: number) {
  let state = seed >>> 0;
  return () => {
    state += 0x6d2b79f5;
    let x = Math.imul(state ^ (state >>> 15), 1 | state);
    x ^= x + Math.imul(x ^ (x >>> 7), 61 | x);
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}
function chance(a: BracketTeam, b: BracketTeam): number {
  return 1 / (1 + Math.pow(10, -(a.projectedRating - b.projectedRating) / 400));
}

export function simulateFullBracket(field: BracketField, runs = 5000, randomSeed = 42): BracketResult[] {
  if (!Number.isInteger(runs) || runs < 1 || runs > 100000)
    throw new Error("Runs must be an integer from 1 to 100,000.");
  // Revalidate external fields; do not let malformed arrays silently produce
  // a nonsensical champion or phantom game.
  const valid = buildFieldFromSlots(field.season, field.regions);
  if (valid.openingRoundGames !== field.openingRoundGames ||
      valid.entrants.length !== field.entrants.length)
    throw new Error("Field metadata is inconsistent.");
  const rng = seededRandom(randomSeed);
  const rounds = ["round32", "sweet16", "elite8", "final4", "titleGame", "champion"] as const;
  const counts = new Map<string, BracketResult>(field.entrants.map((t) => [t.teamId, {
    teamId: t.teamId, name: t.name, region: t.region, seed: t.seed,
    round32: 0, sweet16: 0, elite8: 0, final4: 0, titleGame: 0,
    champion: 0, openingRoundWin: null,
  }]));
  const pick = (a: BracketTeam, b: BracketTeam) => rng() < chance(a, b) ? a : b;
  for (let run = 0; run < runs; run++) {
    let regionWinners: BracketTeam[] = [];
    for (const region of field.regions) {
      let current = region.slots.map((slot) => {
        if (slot.teams.length === 1) return slot.teams[0];
        const winner = pick(slot.teams[0], slot.teams[1]);
        const record = counts.get(winner.teamId)!;
        record.openingRoundWin = (record.openingRoundWin ?? 0) + 1;
        const loser = slot.teams.find((t) => t.teamId !== winner.teamId)!;
        const loserRecord = counts.get(loser.teamId)!;
        if (loserRecord.openingRoundWin === null) loserRecord.openingRoundWin = 0;
        return winner;
      });
      for (let r = 0; r < 4; r++) {
        const next: BracketTeam[] = [];
        for (let i = 0; i < current.length; i += 2) {
          const winner = pick(current[i], current[i + 1]);
          counts.get(winner.teamId)![rounds[r]]++;
          next.push(winner);
        }
        current = next;
      }
      regionWinners.push(current[0]);
    }
    // Generic region crossover W-X, Y-Z. Historical NCAA Final Four pairings
    // vary by season, so this is a documented bracket *scenario* assumption.
    const finalists = [
      pick(regionWinners[0], regionWinners[1]),
      pick(regionWinners[2], regionWinners[3]),
    ];
    for (const team of finalists) counts.get(team.teamId)!.titleGame++;
    const champion = pick(finalists[0], finalists[1]);
    counts.get(champion.teamId)!.champion++;
  }
  return [...counts.values()].map((row) => {
    const result = { ...row };
    for (const metric of rounds) result[metric] /= runs;
    if (result.openingRoundWin !== null) result.openingRoundWin /= runs;
    return result;
  }).sort((a, b) => b.champion - a.champion || a.name.localeCompare(b.name));
}

/** Public UI model contract. Ratings are Elo-style points, not NCAA rankings. */

export type Team = {
  rank: number;
  teamId: string;
  name: string;
  rating: number;
  projectedRating: number;
  trend: number;
  wins: number;
  losses: number;
  history: number[];
  seed?: string;
  pointsForPerGame?: number;
  pointsAgainstPerGame?: number;
  marginPerGame?: number;
  opponentAverageElo?: number;
};

export type RatingsDataset = {
  mode: "demo" | "historical" | "current";
  season: number;
  throughDay: number | null;
  label: string;
  source: string;
  method: string;
  isComplete?: boolean;
  regularSeasonGames?: number;
  sourceUrl?: string;
  sourceCommit?: string;
  tournament?: {
    champion: string | null;
    championId: string | null;
    games: number;
    evaluatedGames: number;
    missingTeams: number;
    brier: number | null;
    accuracy: number | null;
    source: string;
    mainDrawOnly?: boolean;
  };
  teams: Team[];
  retrievedAtUtc?: string;
  lastGameDate?: string;
  cutoffDate?: string;
  recentGames?: Array<{id: string; date: string; home: string; away: string; homeScore: number; awayScore: number}>;
  isOfficialBracket?: boolean;
};

export type TitleResult = { teamId: string; titleProbability: number };

export function matchupProbability(ratingA: number, ratingB: number): number {
  if (!Number.isFinite(ratingA) || !Number.isFinite(ratingB)) {
    throw new Error("Ratings must be finite.");
  }
  return 1 / (1 + Math.pow(10, -(ratingA - ratingB) / 400));
}

export function simulateBracket(entrants: Team[], runs: number): TitleResult[] {
  if (entrants.length < 2 || (entrants.length & (entrants.length - 1)) !== 0) {
    throw new Error("Bracket must contain a power-of-two number of teams.");
  }
  if (runs < 1 || !Number.isInteger(runs)) {
    throw new Error("Simulation count must be a positive integer.");
  }
  const counts = new Map(entrants.map((team) => [team.teamId, 0]));
  for (let run = 0; run < runs; run++) {
    let remaining = [...entrants];
    while (remaining.length > 1) {
      const next: Team[] = [];
      for (let i = 0; i < remaining.length; i += 2) {
        const a = remaining[i];
        const b = remaining[i + 1];
        next.push(Math.random() < matchupProbability(a.projectedRating, b.projectedRating) ? a : b);
      }
      remaining = next;
    }
    const winner = remaining[0].teamId;
    counts.set(winner, (counts.get(winner) ?? 0) + 1);
  }
  return [...counts].map(([teamId, count]) => ({
    teamId,
    titleProbability: count / runs,
  })).sort((a, b) => b.titleProbability - a.titleProbability);
}

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
  opponentAverageEloAtGame?: number;
  classicElo?: number;
  eloLastGameDate?: string | null;
  eloLastGameChange?: number | null;
  eloRecentChanges?: Array<{contestId:string;date:string;opponent:string;result:"W"|"L";margin:number;eloChange:number;opponentEloBefore:number}>;
  conference?: string | null;
  conferenceVerified?: boolean;
  divisionIConfirmed?: boolean | null;
  divisionConferenceGroupId?: string | null;
  ncaaSourceTeamId?: string | null;
  offRating100?: number;
  defRating100?: number;
  pacePossessions?: number;
  adjOff100?: number;
  adjDef100?: number;
  adjNet100?: number;
  possessionGames?: number;
  adaptiveRating?: number;
  volatility?: number;
  regimeShift?: number;
  ewmaSlope?: number;
  sampleStatus?: string;
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
  sourceReconciliation?: {
    mode:string;ncaaAcceptedGames:number;ratedEspnOnlyFinals:number;
    totalRatedGames:number;espnFinalsObservedThisRun:number;
    persistedEspnFinalReceipts:number;ncaaLastGameDate:string|null;
    espnOnlyLastGameDate:string|null;rejectedOrReconciled:Record<string,number>;
    sourceWarnings?:string[];
  };
  cutoffDate?: string;
  recentGames?: Array<{id: string; date: string; home: string; away: string; homeScore: number; awayScore: number}>;
  isOfficialBracket?: boolean;
  divisionCoverage?: {status?:string; matchedRatedTeams?:number;divisionIConfirmed?:number; explicitlyNonDI?:number; sourceDivisionIConferenceGroups?:number; unmatchedRatedTeams?:number};
  identityCoverage?: {status?: string; source?:string; ratedTeams?: number; matchedRatedTeams?: number; unmatchedRatedTeams?: number; conferencesRepresented?: number; matchRate?:number; conferenceCounts?:Record<string,number>};
  efficiencyCoverage?: {status?: string; source?:string; matchedTeamGames?: number; teamsWithMetrics?: number; scheduledFinalGames?:number; skippedRows?:number};
  selectionWatchlist?: unknown;
  historicalCalibration?: {temperature:number;blendWeight:number;trainedThroughSeason:number;source:string;caveat:string};
  pregameDiagnostics?: {evaluatedGames: number; brier: number; accuracy: number; coinFlipBrier: number; method: string; caveat: string};
  eloComparison?: {evaluatedGames:number;enhancedBrier:number|null;classicBrier:number|null;enhancedAccuracy:number|null;classicAccuracy:number|null;enhancedBrierGain:number|null;method:string;caveat:string};
  eloMethodology?: {version:string;kFactor:number;recordedHomeAdvantage:number;marginCapPoints:number;priorDateFrozen:boolean;policy:string;unavailable:string};
  recentEloUpdates?: Array<{contestId:string;date:string;winner:string;loser:string;scoreMargin:number;winnerEloChange:number;loserEloChange:number}>;
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

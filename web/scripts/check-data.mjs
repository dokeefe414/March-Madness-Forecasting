import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const read = (file) => JSON.parse(fs.readFileSync(path.join(root, file), "utf8"));
const data = read("data/rankings.json");
const index = read("data/history-index.json");
if (data.mode !== "historical") throw Error("Default snapshot must be authentic historical data");
if (!Number.isInteger(data.season)) throw Error("season must be an integer");
if (!Array.isArray(data.teams) || data.teams.length < 2) throw Error("dataset needs at least two teams");
if (!Array.isArray(index.seasons) || index.seasons.length !== 42) throw Error("Expected 42 years, 1985–2026");
if (index.firstSeason !== 1985 || index.lastSeason !== 2026) throw Error("Invalid range");
if (index.sourceCommit !== data.sourceCommit) throw Error("Source pin mismatch");
const ids = new Set();
function verifyTeam(team) {
  if (ids.has(team.teamId)) throw Error("duplicate team ID: " + team.teamId);
  ids.add(team.teamId);
  for (const field of ["rating", "projectedRating", "trend", "wins", "losses"]) {
    if (!Number.isFinite(team[field])) throw Error("non-finite " + field + " for " + team.name);
  }
  if (!Array.isArray(team.history) || !team.history.length) throw Error("missing history: " + team.name);
  if (!team.history.every(Number.isFinite)) throw Error("invalid history: " + team.name);
}
data.teams.forEach(verifyTeam);
let regCount = 0;
let tourneyCount = 0;
for (const item of index.seasons) {
  const snapshot = read("public/seasons/" + item.season + ".json");
  const tournament = read("public/tournaments/" + item.season + ".json");
  if (snapshot.season !== item.season || tournament.season !== item.season) throw Error("Mismatched season");
  if (snapshot.mode !== "historical" || snapshot.sourceCommit !== index.sourceCommit) throw Error("Unverified season " + item.season);
  if (snapshot.teams.length !== item.teams || !snapshot.teams.length) throw Error("Team count mismatch " + item.season);
  if (snapshot.regularSeasonGames !== item.regularSeasonGames || snapshot.throughDay !== item.throughDay) throw Error("Game count or day mismatch " + item.season);
  if (snapshot.isComplete !== item.isComplete) throw Error("Season completion mismatch " + item.season);
  if (snapshot.tournament.games !== tournament.games.length) throw Error("Tournament game count mismatch " + item.season);
  if (snapshot.tournament.champion !== tournament.champion) throw Error("Champion mismatch " + item.season);
  regCount += item.regularSeasonGames;
  tourneyCount += tournament.games.length;
}
if (regCount !== 198079) throw Error("Expected 198079 regular-season games, found " + regCount);
if (tourneyCount !== 2648) throw Error("Expected 2585 historic + 63 main-draw 2026 games, found " + tourneyCount);
if (read("public/tournaments/2020.json").games.length !== 0) throw Error("2020 tournament did not occur");
if (read("public/seasons/2026.json").isComplete) throw Error("2026 available regular season is incomplete");
if (read("public/tournaments/2026.json").champion !== "Michigan") throw Error("2026 championship mismatch");
if (data.season !== 2025 || data.tournament.champion !== "Florida" || !data.isComplete) throw Error("Default season must be complete 2025");
console.log("Verified 42 historical seasons, " + regCount.toLocaleString() +
  " regular-season games, " + tourneyCount.toLocaleString() + " historical tournament-game rows.");

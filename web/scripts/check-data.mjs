import fs from "node:fs";
import path from "node:path";

const source = path.join(process.cwd(), "data", "rankings.json");
const data = JSON.parse(fs.readFileSync(source, "utf8"));
if (!["demo", "historical"].includes(data.mode)) throw Error("mode must be demo or historical");
if (!Number.isInteger(data.season)) throw Error("season must be an integer");
if (!Array.isArray(data.teams) || data.teams.length < 2) throw Error("dataset needs at least two teams");
const ids = new Set();
data.teams.forEach((team) => {
  if (ids.has(team.teamId)) throw Error("duplicate team ID: " + team.teamId);
  ids.add(team.teamId);
  for (const field of ["rating", "projectedRating", "trend", "wins", "losses"]) {
    if (!Number.isFinite(team[field])) throw Error("non-finite " + field + " for " + team.name);
  }
  if (!Array.isArray(team.history) || !team.history.length) throw Error("missing history: " + team.name);
  if (!team.history.every(Number.isFinite)) throw Error("invalid history: " + team.name);
});
console.log("Validated " + data.teams.length + " " + data.mode + " teams.");

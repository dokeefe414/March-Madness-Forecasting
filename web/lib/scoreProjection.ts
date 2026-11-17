import type {Team} from "./models";

/** Source-derived, descriptive neutral-court baseline — not calibrated market odds.
 * A team's observed scored/allowed points per game and an opponent's allowed/
 * scored points are averaged symmetrically. No invented game-level scores,
 * injuries, possession data or fitted spread coefficients are introduced.
 */
export type ScoreProjection={
  awayPoints:number;homePoints:number;
  favorite:string;spread:number;total:number;
  homeMargin:number;awayGames:number;homeGames:number;
  method:string;
};
const MIN_GAMES=5;
export function estimateScore(home:Team|undefined,away:Team|undefined):ScoreProjection|null{
 if(!home||!away||home.teamId===away.teamId)return null;
 const hg=home.wins+home.losses,ag=away.wins+away.losses;
 if(hg<MIN_GAMES||ag<MIN_GAMES)return null;
 const values=[home.pointsForPerGame,home.pointsAgainstPerGame,away.pointsForPerGame,away.pointsAgainstPerGame];
 if(values.some(x=>typeof x!=="number"||!Number.isFinite(x)||x<=0||x>=200))return null;
 const [hFor,hAgainst,aFor,aAgainst]=values as number[];
 const h=Math.round((hFor+aAgainst)/2*10)/10;
 const a=Math.round((aFor+hAgainst)/2*10)/10;
 const margin=Math.round((h-a)*10)/10;
 return {
   homePoints:h,awayPoints:a,homeMargin:margin,
   favorite:margin>0?home.name:margin<0?away.name:"Even",
   spread:Math.round(Math.abs(margin)*10)/10,
   total:Math.round((h+a)*10)/10,
   homeGames:hg,awayGames:ag,
   method:"Offense/defense mean cross-matchup from previously verified team points scored and allowed per game; neutral-court descriptive baseline",
 };
}

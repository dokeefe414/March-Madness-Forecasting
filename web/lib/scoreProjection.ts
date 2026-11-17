import type {Team} from "./models";

/** A forecasted score is a descriptive model hypothesis, NOT sportsbook odds.
 * Source team box efficiency is opponent-adjusted and possession-weighted on
 * the Python pipeline; require paired possession coverage for the high-quality
 * projection. Never manufacture missing box statistics.
 */
export type ScoreProjection={
 awayPoints:number;homePoints:number;favorite:string;spread:number;total:number;
 homeMargin:number;awayGames:number;homeGames:number;method:string;
 methodKind:"opponent-adjusted-possessions"|"raw-scoring-means";
 expectedPossessions:number|null;observedPossessionGames:number|null;
};
const MIN_GAMES=5;
const finite=(n:unknown):n is number=>typeof n==="number"&&Number.isFinite(n);
const rounded=(n:number)=>Math.round(n*10)/10;
export function estimateScore(home:Team|undefined,away:Team|undefined):ScoreProjection|null{
 if(!home||!away||home.teamId===away.teamId)return null;
 const hg=home.wins+home.losses,ag=away.wins+away.losses;
 if(hg<MIN_GAMES||ag<MIN_GAMES)return null;
 let homePoints:number,awayPoints:number,method:string;
 let expectedPossessions:number|null=null;
 let observedPossessionGames:number|null=null;
 let methodKind:ScoreProjection["methodKind"];
 const adjusted=[home.adjOff100,home.adjDef100,away.adjOff100,away.adjDef100,
                 home.pacePossessions,away.pacePossessions];
 const rawBox=[home.offRating100,home.defRating100,away.offRating100,away.defRating100];
 const boxGames=Math.min(home.possessionGames??0,away.possessionGames??0);
 // Require at least five same-source possession games, finite efficiencies,
 // a plausible mean tempo, and a plausible offensive/defensive league anchor.
 const haveBox=boxGames>=MIN_GAMES&&adjusted.every(finite)&&rawBox.every(finite);
 const tempo=haveBox?((home.pacePossessions!+away.pacePossessions!)/2):0;
 const sourceAnchor=haveBox?rawBox.reduce<number>((sum,v)=>sum+(v??0),0)/4:0;
 if(haveBox&&tempo>=50&&tempo<=95&&sourceAnchor>=50&&sourceAnchor<=150
    &&adjusted.slice(0,4).every(v=>(v as number)>35&&(v as number)<200)){
   const [homeOff,homeDef,awayOff,awayDef]=adjusted as number[];
   // Multiplicative, symmetric strengths: both offenses and opposing adjusted
   // defensive efficiencies are normalized by the observed-source mean.
   homePoints=rounded(homeOff*awayDef/sourceAnchor*tempo/100);
   awayPoints=rounded(awayOff*homeDef/sourceAnchor*tempo/100);
   expectedPossessions=rounded(tempo);
   observedPossessionGames=boxGames;
   methodKind="opponent-adjusted-possessions";
   method="Source-linked opponent-adjusted offense and defense per 100 possessions × observed average tempo. Estimated league anchor from the two teams' verified raw efficiency. Already regularized by Python's 600-possession ridge.";
 }else{
   const values=[home.pointsForPerGame,home.pointsAgainstPerGame,away.pointsForPerGame,away.pointsAgainstPerGame];
   if(values.some(x=>!finite(x)||x<=0||x>=200))return null;
   const [hFor,hAgainst,aFor,aAgainst]=values as number[];
   homePoints=rounded((hFor+aAgainst)/2);
   awayPoints=rounded((aFor+hAgainst)/2);
   methodKind="raw-scoring-means";
   method="Fallback only: source-recorded points-for and opponent points-conceded season averages. Missing verified possession/adjusted efficiency coverage; not a pace model.";
 }
 const margin=rounded(homePoints-awayPoints);
 return {homePoints,awayPoints,homeMargin:margin,
  favorite:margin>0?home.name:margin<0?away.name:"Even",
  spread:rounded(Math.abs(margin)),total:rounded(homePoints+awayPoints),
  homeGames:hg,awayGames:ag,method,methodKind,expectedPossessions,observedPossessionGames};
}

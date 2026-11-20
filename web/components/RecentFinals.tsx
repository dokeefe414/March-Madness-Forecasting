"use client";

type FinalGame={
  eventId:string;date:string;scheduledStartUtc:string;
  home:string;away:string;homeScore:number;awayScore:number;winner:string;
  status:"ESPN-final";ncaaRatingInputConfirmed:boolean;eloRatingInputConfirmed?:boolean;
  ncaaIdentityMatchConfirmed:boolean;
};
export type RecentFinalsReport={
  schemaVersion:number;season:number;type:string;status:"source-ready"|"source-partial"|"source-unavailable";
  generatedAtUtc:string;ratingRetrievedAtUtc:string;ncaaResultsThroughDate:string;
  mostRecentEspnFinalDate:string|null;confirmedFinalCount:number;
  ncaaRatingInputMatched:number;boardDaysRetrieved:number;lookbackDays:number;
  sourceWarnings:string[];games:FinalGame[];
};
type Props={report:RecentFinalsReport|null;ncaaLastDate:string|null;eloLastDate:string|null;espnRatedGames:number;onRefresh:()=>void;refreshing:boolean};
const et=(iso:string)=>new Date(iso).toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})+" ET";
const dateFmt=(iso:string)=>{const d=new Date(iso+"T12:00:00Z");return d.toLocaleDateString("en-US",{month:"short",day:"numeric",timeZone:"UTC"});};

export default function RecentFinals({report,ncaaLastDate,eloLastDate,espnRatedGames,onRefresh,refreshing}:Props){
  const rows=report?.games||[];
  const matched=rows.filter(x=>x.ncaaRatingInputConfirmed).length;
  const rated=rows.filter(x=>x.eloRatingInputConfirmed).length;
  const sourceAhead=Boolean(report?.mostRecentEspnFinalDate&&ncaaLastDate&&report.mostRecentEspnFinalDate>ncaaLastDate);
  const latest=report?.generatedAtUtc&&Number.isFinite(Date.parse(report.generatedAtUtc))?et(report.generatedAtUtc):"not available";
  return <section className="gc-finals" aria-label="Recent ESPN-confirmed basketball final scores">
    <div className="gc-finals-header">
      <div>
        <span className="gc-finals-kicker"><i aria-hidden="true"/> SOURCE-VERIFIED COLLEGE BASKETBALL RESULTS</span>
        <h2>Final scores. <em>Every day.</em></h2>
        <p>ESPN-confirmed final scores are listed here even when the NCAA-derived schedule is delayed. Elo incorporates finals only when both teams have independently sourced same-season ESPN team IDs. Unmatched results never enter training or become graded original predictions.</p>
      </div>
      <button type="button" onClick={onRefresh} disabled={refreshing} className="gc-finals-refresh">
        {refreshing?"CHECKING SOURCES…":"↻ CHECK FOR UPDATES"}
      </button>
    </div>
    <div className="gc-finals-proof">
      <div><small>LATEST ESPN FINAL</small><strong>{report?.mostRecentEspnFinalDate?dateFmt(report.mostRecentEspnFinalDate):"—"}</strong><span>Must report STATUS_FINAL</span></div>
      <div><small>LATEST ELO / NCAA DATE</small><strong>{eloLastDate?dateFmt(eloLastDate):"—"} / {ncaaLastDate?dateFmt(ncaaLastDate):"—"}</strong><span>{espnRatedGames} ESPN-only game(s) currently in Elo</span></div>
      <div><small>ESPN FINALS IN WINDOW</small><strong>{report?.confirmedFinalCount?.toLocaleString()??"—"}</strong><span>{report?.boardDaysRetrieved??0}/{report?.lookbackDays??4} days retrieved</span></div>
      <div><small>ESPN CAPTURE TIME</small><strong>{latest}</strong><span>Scheduled site refresh + browser recheck</span></div>
    </div>
    {sourceAhead&&<p className="gc-finals-lag" role="status">
       <strong>ESPN results are ahead of the NCAA score file.</strong> Results with verified season-specific ESPN IDs can already update Elo. Unmatched games still await trusted identity or NCAA data.
    </p>}
    {report?.status==="source-partial"&&<p className="gc-finals-lag" role="status">
      One or more ESPN scoreboards were unavailable. Displayed finals are confirmed, but the list can be incomplete.
    </p>}
    {report?.status==="source-unavailable"&&<p className="gc-finals-lag" role="status">
      ESPN's recent-finals source could not be retrieved. The previous Elo ratings and forecast archives remain untouched.
    </p>}
    {!report?<p className="gc-finals-empty">Daily final scores are temporarily unavailable. This does not mean no games were played. The independent upcoming schedule and original forecast archive remain available.</p>:
      rows.length===0?<p className="gc-finals-empty">
        No confirmed final scores were returned for the last {report.lookbackDays} Eastern calendar days. Source coverage: {report.boardDaysRetrieved}/{report.lookbackDays} days.
      </p>:<div className="gc-finals-list" aria-label="Verified game scores">
        {rows.slice(0,30).map(g=><article className="gc-final-card" key={g.eventId}>
          <div className="gc-final-top"><span>{dateFmt(g.date)} · {et(g.scheduledStartUtc)}</span><strong>FINAL · ESPN</strong></div>
          <div className="gc-final-scoreline">
            <div className={g.awayScore>g.homeScore?"winner":""}><span>AWAY</span><strong>{g.away}</strong><b>{g.awayScore}</b></div>
            <div className={g.homeScore>g.awayScore?"winner":""}><span>HOME</span><strong>{g.home}</strong><b>{g.homeScore}</b></div>
          </div>
          <p>{g.ncaaRatingInputConfirmed?
            "MATCHED NCAA RESULT · INCLUDED IN CURRENT ELO":
            g.eloRatingInputConfirmed?
            "ESPN ID-VERIFIED FINAL · INCLUDED IN ELO (NCAA PENDING)":
            "ESPN FINAL · ID / SOURCE VERIFICATION PENDING, NOT IN ELO"}</p>
        </article>)}
      </div>}
    {rows.length>30&&<p className="gc-finals-note">Showing the newest 30 of {rows.length} source-confirmed finals from the published four-day window.</p>}
    <p className="gc-finals-note">ESPN final-status scores refresh when GitHub publishes new snapshots and whenever this open page checks for new published data. A previously published pregame probability is immutable; independent ESPN and NCAA results must agree before its win/loss is graded. {rated} displayed games matched current Elo inputs ({matched} also matched NCAA). Unmatched ESPN results are not rated.</p>
  </section>;
}

/** Resolve published historical JSON safely on GitHub Pages after repository rename.
 *
 * A user may arrive with a browser-cached site shell or a bookmarked old
 * project URL. Historical game data is static and same-origin; try only known
 * public deployment roots, never a third-party host or an unsourced fallback.
 * Every result is schema-checked by the caller.
 */
const BUILD_BASE = process.env.NEXT_PUBLIC_BASE_PATH || "";
const CURRENT_PAGES_BASE = "/March-Madness-Forecasting26-27";
const OLD_PAGES_BASE = "/March-Madness-Forecasting";

function cleanRoot(root:string):string{
 return root.replace(/\/+$/,"");
}

export function historicalAssetUrls(kind:"seasons"|"tournaments",season:number):string[]{
 if(!Number.isInteger(season)||season<1985||season>2026)
   throw new Error("Historical season must be within the available 1985–2026 archive.");
 const pathname=typeof window==="undefined"?"":window.location.pathname;
 const detected=pathname.startsWith(CURRENT_PAGES_BASE+"/")?CURRENT_PAGES_BASE:
                pathname.startsWith(OLD_PAGES_BASE+"/")?OLD_PAGES_BASE:"";
 const roots=[detected,BUILD_BASE,CURRENT_PAGES_BASE,OLD_PAGES_BASE,""];
 const seen=new Set<string>();
 return roots.map(cleanRoot).filter(root=>{
   if(seen.has(root))return false;
   seen.add(root);return true;
 }).map(root=>root+"/"+kind+"/"+season+".json");
}

/** Retry same-origin archival JSON only when the first route is unavailable.
 * Distinguish a network/404 problem from malformed data instead of masking it.
 */
export async function fetchHistoricalJson<T>(
 kind:"seasons"|"tournaments",season:number,validate:(value:unknown)=>value is T
):Promise<T>{
 const urls=historicalAssetUrls(kind,season);
 const attempts:string[]=[];
 for(const url of urls){
   try{
     const response=await fetch(url,{cache:"no-store",headers:{Accept:"application/json"}});
     if(!response.ok){attempts.push(url+" (HTTP "+response.status+")");continue}
     const contentType=response.headers.get("content-type")||"";
     if(!contentType.includes("json")){attempts.push(url+" (not JSON)");continue}
     const parsed:unknown=await response.json();
     if(!validate(parsed)){attempts.push(url+" (invalid archive schema)");continue}
     return parsed;
   }catch(error){
     attempts.push(url+" ("+(error instanceof Error?error.message:"network error")+")");
   }
 }
 throw new Error(kind==="seasons"
   ?"Historical season "+season+" could not load. Tried archived data URLs: "+attempts.join("; ")
   :"Tournament "+season+" data could not load. Tried archived data URLs: "+attempts.join("; "));
}

/* No archived predictions, current JSON, or API data are ever cached.
 * Offline shell is a convenience, never a claim of real-time odds.
 */
const VERSION="march-forecast-shell-v12";
const ROOT="/March-Madness-Forecasting26-27/";
self.addEventListener("install",event=>{
  event.waitUntil(caches.open(VERSION).then(cache=>cache.add(ROOT)).then(()=>self.skipWaiting()));
});
self.addEventListener("activate",event=>event.waitUntil(
  Promise.all([caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==VERSION).map(k=>caches.delete(k)))),self.clients.claim()])
));
self.addEventListener("fetch",event=>{
  const req=event.request,url=new URL(req.url);
  if(req.method!=="GET"||url.origin!==self.location.origin)return;
  if(/\/forecasts\/|\/current\/|\.json(?:$|\?)/.test(url.pathname))return; // network-only, fail closed
  if(req.mode==="navigate"&&url.pathname.startsWith(ROOT)){
    event.respondWith(fetch(req).catch(()=>caches.match(ROOT)));
  }
});

"use client";
import {useEffect} from "react";
export default function PwaEnable(){
 useEffect(()=>{
  if(!("serviceWorker" in navigator)||location.protocol!=="https:")return;
  navigator.serviceWorker.register("/March-Madness-Forecasting/sw.js",{scope:"/March-Madness-Forecasting/"}).catch(()=>{});
 },[]);
 return null;
}

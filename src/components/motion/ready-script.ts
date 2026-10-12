/* Kept apart from reveal.ts so the root layout does not pull in motion. */
/** Runs before paint. Drops the class again if the engine never starts. */
export const MOTION_READY_SCRIPT = `(function(){try{if(matchMedia("(prefers-reduced-motion: reduce)").matches)return;var d=document.documentElement;d.classList.add("motion-ready");setTimeout(function(){if(!window.__revealStarted)d.classList.remove("motion-ready")},3000)}catch(e){}})();`;

function equalBounds(a,b){return ['x','y','width','height'].every(k=>a[k]===b[k]);}
function interpolateBounds(from,to,t){
  const eased=1-Math.pow(1-Math.min(1,Math.max(0,t)),3);
  return Object.fromEntries(['x','y','width','height'].map(k=>[k,Math.round(from[k]+(to[k]-from[k])*eased)]));
}
class BoundsAnimator{
  constructor(get,set,{now=()=>performance.now(),schedule=fn=>setTimeout(fn,16),cancel=clearTimeout}={}){
    Object.assign(this,{get,set,now,schedule,cancel});this.timer=null;this.target=null;
  }
  move(target,animate=true){
    if(this.target&&equalBounds(this.target,target))return;
    this.stop();this.target=target;
    const from=this.get();
    if(equalBounds(from,target))return;
    if(!animate){this.set(target);return;}
    const started=this.now();let last=from;
    const tick=()=>{
      const t=Math.min(1,(this.now()-started)/160);
      const next=interpolateBounds(from,target,t);
      if(!equalBounds(last,next)){this.set(next);last=next;}
      this.timer=t<1?this.schedule(tick):null;
    };
    this.timer=this.schedule(tick);
  }
  stop(){if(this.timer!==null)this.cancel(this.timer);this.timer=null;this.target=null;}
}
module.exports={BoundsAnimator,interpolateBounds,equalBounds};

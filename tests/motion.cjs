const assert=require('node:assert/strict');
const {BoundsAnimator,interpolateBounds}=require('../desktop/motion.cjs');
let time=0,scheduled=new Map(),id=0,sets=0,bounds={x:300,y:600,width:520,height:180};
const options={now:()=>time,schedule:fn=>{scheduled.set(++id,fn);return id;},cancel:key=>scheduled.delete(key)};
const animation=new BoundsAnimator(()=>bounds,b=>{bounds=b;sets++;},options);
const target={x:300,y:400,width:520,height:380};
animation.move(target);
for(let i=0;i<10;i++)animation.move({...target});
assert.equal(scheduled.size,1,'duplicate measurements must not restart an animation');
while(scheduled.size){time+=16;const batch=[...scheduled.values()];scheduled.clear();for(const tick of batch)tick();assert.equal(bounds.y+bounds.height,780,'bottom stays anchored above caret');}
assert.deepEqual(bounds,target);assert.ok(sets<=10,'native resize calls are bounded');
const count=sets;animation.move({...target});assert.equal(sets,count);
assert.deepEqual(interpolateBounds(target,target,1),target);
console.log('Motion tests passed: deduplication, easing, anchored bottom, bounded native resize');

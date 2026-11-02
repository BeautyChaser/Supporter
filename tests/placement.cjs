const assert=require('node:assert/strict');
const {place}=require('../desktop/placement.cjs');
let p=place({x:620,y:900},{width:520,height:186},{x:0,y:0,width:1920,height:1080});
assert.equal(p.y,704);assert.equal(p.x,620);
p=place({x:-1800,y:600},{width:520,height:300},{x:-1920,y:0,width:1920,height:1080});
assert.equal(p.x,-1800);assert.equal(p.y,290);
p=place({x:1900,y:5},{width:520,height:186},{x:0,y:0,width:1920,height:1080});
assert.equal(p.x,1388);assert.ok(p.y>=12);
console.log('Placement tests passed: above caret, negative monitor, edge clamping');

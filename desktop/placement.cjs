function place(anchor,size,area) {
  const width=Math.min(size.width,area.width-24),height=Math.min(size.height,area.height-24);
  const x=Math.max(area.x+12,Math.min(anchor.x,area.x+area.width-width-12));
  const above=anchor.y-height-10;
  const y=above>=area.y+12?above:Math.min(anchor.y+28,area.y+area.height-height-12);
  return {x:Math.round(x),y:Math.round(Math.max(area.y+12,y)),width:Math.round(width),height:Math.round(height)};
}
module.exports={place};

const os=require('node:os');
const materials=new WeakMap();
function applyGlass(window,appearance={},platform=process.platform,release=os.release()){
  const enabled=appearance.glass!==false;
  const opacity=Math.max(.5,Math.min(.96,Number(appearance.glassOpacity)||.8));
  const build=Number(String(release).split('.')[2]||0);
  let native=false;
  if(platform==='win32'&&build>=22621&&typeof window.setBackgroundMaterial==='function'){
    const material=enabled?'acrylic':'none';
    try{if(materials.get(window)!==material){window.setBackgroundMaterial(material);materials.set(window,material);}native=enabled;}
    catch{materials.delete(window);}
  }
  window.setBackgroundColor('#00000000');
  return {enabled,native,opacity:enabled?(native?opacity:Math.max(.9,opacity)):1};
}
module.exports={applyGlass};

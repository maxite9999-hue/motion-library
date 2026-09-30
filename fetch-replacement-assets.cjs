// Fixed public assets used by the four replacement templates; verifies downloaded bytes.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
async function fetchAssets(){
 const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'replacement-assets.json'),'utf8'));
 for(const item of manifest.files){
  if(!/^JJ-00[4-7]-reference\.mp4$/.test(item.file))throw Error('Unexpected asset filename');
  const p=path.join(__dirname,item.file);const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
  if(fs.existsSync(p)&&hash(fs.readFileSync(p))===item.sha256)continue;
  const res=await fetch(manifest.base+encodeURIComponent(item.file));if(!res.ok)throw Error('Asset unavailable: '+item.file+' HTTP '+res.status);
  const bytes=Buffer.from(await res.arrayBuffer());if(hash(bytes)!==item.sha256)throw Error('Checksum mismatch: '+item.file);
  fs.writeFileSync(p,bytes);console.log('Verified',item.file);
 }
}
module.exports=fetchAssets;if(require.main===module)fetchAssets().catch(e=>{console.error(e.message);process.exit(1)});

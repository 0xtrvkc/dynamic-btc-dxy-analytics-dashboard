const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync(require('node:path').join(__dirname,'../index.html'),'utf8');
const source=html.slice(html.indexOf('const Stats ='),html.indexOf('</script>',html.indexOf('const Stats =')));
const sandbox={};vm.runInNewContext(source+';globalThis.stats=Stats',sandbox);const S=sandbox.stats;
function fixture(){
 const cycles=[1,2,3,4].map(n=>({n,start:`202${n}-01-01`,status:n<4?'completed':'ongoing'}));
 const adjusted={1:{peakPrice:100,troughPrice:25,dxyAtPeak:80,dxyAtTrough:85},2:{peakPrice:200,troughPrice:50,dxyAtPeak:90,dxyAtTrough:95},3:{peakPrice:500,troughPrice:125,dxyAtPeak:100,dxyAtTrough:105},4:{peakPrice:750,troughPrice:250,dxyAtPeak:110,dxyAtTrough:115}};
 return {cycles,adjusted};
}
test('held-out DXY forecast uses the origin close, not future extreme DXY',()=>{
 const {cycles,adjusted}=fixture(),calls=[];
 const r=S.backtest(cycles,adjusted,d=>{calls.push(d);return 90;})[0];
 assert.deepEqual(calls,['2023-01-01']);assert.equal(r.conditioningDxy,90);
 assert.ok(Math.abs(r.peak.B.pred-200)<1e-9);assert.ok(Math.abs(r.trough.B.pred-50/Math.sqrt(2))<1e-9);
});
test('mutating future target outcomes leaves every frozen prediction unchanged',()=>{
 const f=fixture(),before=S.backtest(f.cycles,f.adjusted,()=>90)[0];
 f.adjusted[3]={peakPrice:99999,troughPrice:1,dxyAtPeak:9999,dxyAtTrough:-100};
 const after=S.backtest(f.cycles,f.adjusted,()=>90)[0];
 for(const target of ['peak','trough'])for(const key of ['A','B','C'])assert.equal(before[target][key].pred,after[target][key].pred);
 assert.notEqual(before.peak.B.err,after.peak.B.err);
});
test('missing origin DXY never silently becomes zero or a future observation',()=>{
 const f=fixture();assert.equal(S.backtest(f.cycles,f.adjusted,()=>null)[0].peak.B,null);
 assert.equal(S.backtest(f.cycles,f.adjusted)[0].trough.B,null);
});
test('live DXY input is supplied explicitly and independent of the open-cycle extrema',()=>{
 const f=fixture(),before=S.buildProjections(f.cycles,f.adjusted,92);
 f.adjusted[4].dxyAtPeak=5000;
 assert.equal(S.buildProjections(f.cycles,f.adjusted,92).peakModels.B.value,before.peakModels.B.value);
 assert.equal(S.buildProjections(f.cycles,f.adjusted).peakModels.B,null);
});
test('missing training DXY observations are filtered as paired samples',()=>{
 const f=fixture();f.adjusted[1].dxyAtPeak=null;
 assert.equal(S.backtest(f.cycles,f.adjusted,()=>90)[0].peak.B,null);
 assert.equal(S.linreg([null,2],[1,2]),null);
});
test('UI and report disclose the actual origin and do not describe lookahead forecasts',()=>{
 assert.match(html,/row.forecastOrigin/);assert.match(html,/DXY frozen at halving close/);
 assert.doesNotMatch(html,/uses lookahead DXY input|actualDxyAtPeak|actualDxyAtTrough/);
 for(const m of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g))new vm.Script(m[1]);
});
test('backtest table renders frozen origin and missing-input rows safely',()=>{
 const start=html.indexOf('function renderBacktest('),end=html.indexOf('function renderCycleAnalysis(',start);
 const ctx={Fmt:{usd:v=>String(v),num:v=>v===null?'—':String(v),pct:v=>String(v),int:v=>String(v)}};
 vm.createContext(ctx);vm.runInContext(html.slice(start,end),ctx);
 const f=fixture();ctx.model={backtestRows:S.backtest(f.cycles,f.adjusted,()=>90),proj:{available:false}};
 const rendered=vm.runInContext('renderBacktest(model)',ctx);assert.match(rendered,/frozen 2023-01-01, DXY 90/);assert.doesNotMatch(rendered,/uses the target cycle.*actual/);
 ctx.model.backtestRows=S.backtest(f.cycles,f.adjusted,()=>null);assert.doesNotThrow(()=>vm.runInContext('renderBacktest(model)',ctx));
});

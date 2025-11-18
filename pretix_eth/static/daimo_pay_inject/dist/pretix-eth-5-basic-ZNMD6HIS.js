import{a as c,b as m,c as h,d as Po,e as Do,f as jo}from"./pretix-eth-5-chunk-V76MI62R.js";import{h as ht,i as st}from"./pretix-eth-5-chunk-CWRWVZQN.js";import{A as pe,K as y,L as _,M as Ao,N as X,O as d,a as Oo,h as de,i as pt,j as f,k as N,l as He,m as B,o as U,p as E,q as C,r as Gt,s as v,t as yt,u as x,x as Yt}from"./pretix-eth-5-chunk-V7RLZCVE.js";import"./pretix-eth-5-chunk-MCYRL7OX.js";import{b as g,e as l,f as mt,h as Ke,j as p}from"./pretix-eth-5-chunk-TH6XAEVV.js";import{a as Or}from"./pretix-eth-5-chunk-HFALOJEQ.js";import"./pretix-eth-5-chunk-G6JA5WON.js";import"./pretix-eth-5-chunk-ZCL5HT24.js";import"./pretix-eth-5-chunk-ERWRNXFQ.js";import"./pretix-eth-5-chunk-UYVEV2Z2.js";import"./pretix-eth-5-chunk-64QJEAS7.js";import{c as S,f as Br}from"./pretix-eth-5-chunk-BIK4PATU.js";var ii=S((sd,oi)=>{oi.exports=function(){return typeof Promise=="function"&&Promise.prototype&&Promise.prototype.then}});var gt=S(Wt=>{var eo,kr=[0,26,44,70,100,134,172,196,242,292,346,404,466,532,581,655,733,815,901,991,1085,1156,1258,1364,1474,1588,1706,1828,1921,2051,2185,2323,2465,2611,2761,2876,3034,3196,3362,3532,3706];Wt.getSymbolSize=function(t){if(!t)throw new Error('"version" cannot be null or undefined');if(t<1||t>40)throw new Error('"version" should be in range from 1 to 40');return t*4+17};Wt.getSymbolTotalCodewords=function(t){return kr[t]};Wt.getBCHDigit=function(r){let t=0;for(;r!==0;)t++,r>>>=1;return t};Wt.setToSJISFunction=function(t){if(typeof t!="function")throw new Error('"toSJISFunc" is not a valid function.');eo=t};Wt.isKanjiModeEnabled=function(){return typeof eo<"u"};Wt.toSJIS=function(t){return eo(t)}});var Se=S(Y=>{Y.L={bit:1};Y.M={bit:0};Y.Q={bit:3};Y.H={bit:2};function zr(r){if(typeof r!="string")throw new Error("Param is not a string");switch(r.toLowerCase()){case"l":case"low":return Y.L;case"m":case"medium":return Y.M;case"q":case"quartile":return Y.Q;case"h":case"high":return Y.H;default:throw new Error("Unknown EC Level: "+r)}}Y.isValid=function(t){return t&&typeof t.bit<"u"&&t.bit>=0&&t.bit<4};Y.from=function(t,e){if(Y.isValid(t))return t;try{return zr(t)}catch{return e}}});var si=S((cd,ni)=>{function ri(){this.buffer=[],this.length=0}ri.prototype={get:function(r){let t=Math.floor(r/8);return(this.buffer[t]>>>7-r%8&1)===1},put:function(r,t){for(let e=0;e<t;e++)this.putBit((r>>>t-e-1&1)===1)},getLengthInBits:function(){return this.length},putBit:function(r){let t=Math.floor(this.length/8);this.buffer.length<=t&&this.buffer.push(0),r&&(this.buffer[t]|=128>>>this.length%8),this.length++}};ni.exports=ri});var li=S((ud,ai)=>{function ee(r){if(!r||r<1)throw new Error("BitMatrix size must be defined and greater than 0");this.size=r,this.data=new Uint8Array(r*r),this.reservedBit=new Uint8Array(r*r)}ee.prototype.set=function(r,t,e,i){let n=r*this.size+t;this.data[n]=e,i&&(this.reservedBit[n]=!0)};ee.prototype.get=function(r,t){return this.data[r*this.size+t]};ee.prototype.xor=function(r,t,e){this.data[r*this.size+t]^=e};ee.prototype.isReserved=function(r,t){return this.reservedBit[r*this.size+t]};ai.exports=ee});var ci=S(_e=>{var Ur=gt().getSymbolSize;_e.getRowColCoords=function(t){if(t===1)return[];let e=Math.floor(t/7)+2,i=Ur(t),n=i===145?26:Math.ceil((i-13)/(2*e-2))*2,o=[i-7];for(let s=1;s<e-1;s++)o[s]=o[s-1]-n;return o.push(6),o.reverse()};_e.getPositions=function(t){let e=[],i=_e.getRowColCoords(t),n=i.length;for(let o=0;o<n;o++)for(let s=0;s<n;s++)o===0&&s===0||o===0&&s===n-1||o===n-1&&s===0||e.push([i[o],i[s]]);return e}});var pi=S(di=>{var Nr=gt().getSymbolSize,ui=7;di.getPositions=function(t){let e=Nr(t);return[[0,0],[e-ui,0],[0,e-ui]]}});var hi=S(O=>{O.Patterns={PATTERN000:0,PATTERN001:1,PATTERN010:2,PATTERN011:3,PATTERN100:4,PATTERN101:5,PATTERN110:6,PATTERN111:7};var St={N1:3,N2:3,N3:40,N4:10};O.isValid=function(t){return t!=null&&t!==""&&!isNaN(t)&&t>=0&&t<=7};O.from=function(t){return O.isValid(t)?parseInt(t,10):void 0};O.getPenaltyN1=function(t){let e=t.size,i=0,n=0,o=0,s=null,a=null;for(let u=0;u<e;u++){n=o=0,s=a=null;for(let b=0;b<e;b++){let w=t.get(u,b);w===s?n++:(n>=5&&(i+=St.N1+(n-5)),s=w,n=1),w=t.get(b,u),w===a?o++:(o>=5&&(i+=St.N1+(o-5)),a=w,o=1)}n>=5&&(i+=St.N1+(n-5)),o>=5&&(i+=St.N1+(o-5))}return i};O.getPenaltyN2=function(t){let e=t.size,i=0;for(let n=0;n<e-1;n++)for(let o=0;o<e-1;o++){let s=t.get(n,o)+t.get(n,o+1)+t.get(n+1,o)+t.get(n+1,o+1);(s===4||s===0)&&i++}return i*St.N2};O.getPenaltyN3=function(t){let e=t.size,i=0,n=0,o=0;for(let s=0;s<e;s++){n=o=0;for(let a=0;a<e;a++)n=n<<1&2047|t.get(s,a),a>=10&&(n===1488||n===93)&&i++,o=o<<1&2047|t.get(a,s),a>=10&&(o===1488||o===93)&&i++}return i*St.N3};O.getPenaltyN4=function(t){let e=0,i=t.data.length;for(let o=0;o<i;o++)e+=t.data[o];return Math.abs(Math.ceil(e*100/i/5)-10)*St.N4};function Mr(r,t,e){switch(r){case O.Patterns.PATTERN000:return(t+e)%2===0;case O.Patterns.PATTERN001:return t%2===0;case O.Patterns.PATTERN010:return e%3===0;case O.Patterns.PATTERN011:return(t+e)%3===0;case O.Patterns.PATTERN100:return(Math.floor(t/2)+Math.floor(e/3))%2===0;case O.Patterns.PATTERN101:return t*e%2+t*e%3===0;case O.Patterns.PATTERN110:return(t*e%2+t*e%3)%2===0;case O.Patterns.PATTERN111:return(t*e%3+(t+e)%2)%2===0;default:throw new Error("bad maskPattern:"+r)}}O.applyMask=function(t,e){let i=e.size;for(let n=0;n<i;n++)for(let o=0;o<i;o++)e.isReserved(o,n)||e.xor(o,n,Mr(t,o,n))};O.getBestMask=function(t,e){let i=Object.keys(O.Patterns).length,n=0,o=1/0;for(let s=0;s<i;s++){e(s),O.applyMask(s,t);let a=O.getPenaltyN1(t)+O.getPenaltyN2(t)+O.getPenaltyN3(t)+O.getPenaltyN4(t);O.applyMask(s,t),a<o&&(o=a,n=s)}return n}});var io=S(oo=>{var wt=Se(),Te=[1,1,1,1,1,1,1,1,1,1,2,2,1,2,2,4,1,2,4,4,2,4,4,4,2,4,6,5,2,4,6,6,2,5,8,8,4,5,8,8,4,5,8,11,4,8,10,11,4,9,12,16,4,9,16,16,6,10,12,18,6,10,17,16,6,11,16,19,6,13,18,21,7,14,21,25,8,16,20,25,8,17,23,25,9,17,23,34,9,18,25,30,10,20,27,32,12,21,29,35,12,23,34,37,12,25,34,40,13,26,35,42,14,28,38,45,15,29,40,48,16,31,43,51,17,33,45,54,18,35,48,57,19,37,51,60,19,38,53,63,20,40,56,66,21,43,59,70,22,45,62,74,24,47,65,77,25,49,68,81],Le=[7,10,13,17,10,16,22,28,15,26,36,44,20,36,52,64,26,48,72,88,36,64,96,112,40,72,108,130,48,88,132,156,60,110,160,192,72,130,192,224,80,150,224,264,96,176,260,308,104,198,288,352,120,216,320,384,132,240,360,432,144,280,408,480,168,308,448,532,180,338,504,588,196,364,546,650,224,416,600,700,224,442,644,750,252,476,690,816,270,504,750,900,300,560,810,960,312,588,870,1050,336,644,952,1110,360,700,1020,1200,390,728,1050,1260,420,784,1140,1350,450,812,1200,1440,480,868,1290,1530,510,924,1350,1620,540,980,1440,1710,570,1036,1530,1800,570,1064,1590,1890,600,1120,1680,1980,630,1204,1770,2100,660,1260,1860,2220,720,1316,1950,2310,750,1372,2040,2430];oo.getBlocksCount=function(t,e){switch(e){case wt.L:return Te[(t-1)*4+0];case wt.M:return Te[(t-1)*4+1];case wt.Q:return Te[(t-1)*4+2];case wt.H:return Te[(t-1)*4+3];default:return}};oo.getTotalCodewordsCount=function(t,e){switch(e){case wt.L:return Le[(t-1)*4+0];case wt.M:return Le[(t-1)*4+1];case wt.Q:return Le[(t-1)*4+2];case wt.H:return Le[(t-1)*4+3];default:return}}});var mi=S(Oe=>{var oe=new Uint8Array(512),Be=new Uint8Array(256);(function(){let t=1;for(let e=0;e<255;e++)oe[e]=t,Be[t]=e,t<<=1,t&256&&(t^=285);for(let e=255;e<512;e++)oe[e]=oe[e-255]})();Oe.log=function(t){if(t<1)throw new Error("log("+t+")");return Be[t]};Oe.exp=function(t){return oe[t]};Oe.mul=function(t,e){return t===0||e===0?0:oe[Be[t]+Be[e]]}});var fi=S(ie=>{var ro=mi();ie.mul=function(t,e){let i=new Uint8Array(t.length+e.length-1);for(let n=0;n<t.length;n++)for(let o=0;o<e.length;o++)i[n+o]^=ro.mul(t[n],e[o]);return i};ie.mod=function(t,e){let i=new Uint8Array(t);for(;i.length-e.length>=0;){let n=i[0];for(let s=0;s<e.length;s++)i[s]^=ro.mul(e[s],n);let o=0;for(;o<i.length&&i[o]===0;)o++;i=i.slice(o)}return i};ie.generateECPolynomial=function(t){let e=new Uint8Array([1]);for(let i=0;i<t;i++)e=ie.mul(e,new Uint8Array([1,ro.exp(i)]));return e}});var bi=S((wd,wi)=>{var gi=fi();function no(r){this.genPoly=void 0,this.degree=r,this.degree&&this.initialize(this.degree)}no.prototype.initialize=function(t){this.degree=t,this.genPoly=gi.generateECPolynomial(this.degree)};no.prototype.encode=function(t){if(!this.genPoly)throw new Error("Encoder not initialized");let e=new Uint8Array(t.length+this.degree);e.set(t);let i=gi.mod(e,this.genPoly),n=this.degree-i.length;if(n>0){let o=new Uint8Array(this.degree);return o.set(i,n),o}return i};wi.exports=no});var so=S(vi=>{vi.isValid=function(t){return!isNaN(t)&&t>=1&&t<=40}});var ao=S(ct=>{var xi="[0-9]+",qr="[A-Z $%*+\\-./:]+",re="(?:[u3000-u303F]|[u3040-u309F]|[u30A0-u30FF]|[uFF00-uFFEF]|[u4E00-u9FAF]|[u2605-u2606]|[u2190-u2195]|u203B|[u2010u2015u2018u2019u2025u2026u201Cu201Du2225u2260]|[u0391-u0451]|[u00A7u00A8u00B1u00B4u00D7u00F7])+";re=re.replace(/u/g,"\\u");var Fr="(?:(?![A-Z0-9 $%*+\\-./:]|"+re+`)(?:.|[\r
]))+`;ct.KANJI=new RegExp(re,"g");ct.BYTE_KANJI=new RegExp("[^A-Z0-9 $%*+\\-./:]+","g");ct.BYTE=new RegExp(Fr,"g");ct.NUMERIC=new RegExp(xi,"g");ct.ALPHANUMERIC=new RegExp(qr,"g");var Vr=new RegExp("^"+re+"$"),Hr=new RegExp("^"+xi+"$"),Kr=new RegExp("^[A-Z0-9 $%*+\\-./:]+$");ct.testKanji=function(t){return Vr.test(t)};ct.testNumeric=function(t){return Hr.test(t)};ct.testAlphanumeric=function(t){return Kr.test(t)}});var bt=S(j=>{var Gr=so(),lo=ao();j.NUMERIC={id:"Numeric",bit:1,ccBits:[10,12,14]};j.ALPHANUMERIC={id:"Alphanumeric",bit:2,ccBits:[9,11,13]};j.BYTE={id:"Byte",bit:4,ccBits:[8,16,16]};j.KANJI={id:"Kanji",bit:8,ccBits:[8,10,12]};j.MIXED={bit:-1};j.getCharCountIndicator=function(t,e){if(!t.ccBits)throw new Error("Invalid mode: "+t);if(!Gr.isValid(e))throw new Error("Invalid version: "+e);return e>=1&&e<10?t.ccBits[0]:e<27?t.ccBits[1]:t.ccBits[2]};j.getBestModeForData=function(t){return lo.testNumeric(t)?j.NUMERIC:lo.testAlphanumeric(t)?j.ALPHANUMERIC:lo.testKanji(t)?j.KANJI:j.BYTE};j.toString=function(t){if(t&&t.id)return t.id;throw new Error("Invalid mode")};j.isValid=function(t){return t&&t.bit&&t.ccBits};function Yr(r){if(typeof r!="string")throw new Error("Param is not a string");switch(r.toLowerCase()){case"numeric":return j.NUMERIC;case"alphanumeric":return j.ALPHANUMERIC;case"kanji":return j.KANJI;case"byte":return j.BYTE;default:throw new Error("Unknown mode: "+r)}}j.from=function(t,e){if(j.isValid(t))return t;try{return Yr(t)}catch{return e}}});var $i=S(_t=>{var Ae=gt(),Jr=io(),yi=Se(),vt=bt(),co=so(),Ei=7973,Ci=Ae.getBCHDigit(Ei);function Qr(r,t,e){for(let i=1;i<=40;i++)if(t<=_t.getCapacity(i,e,r))return i}function Ri(r,t){return vt.getCharCountIndicator(r,t)+4}function Xr(r,t){let e=0;return r.forEach(function(i){let n=Ri(i.mode,t);e+=n+i.getBitsLength()}),e}function Zr(r,t){for(let e=1;e<=40;e++)if(Xr(r,e)<=_t.getCapacity(e,t,vt.MIXED))return e}_t.from=function(t,e){return co.isValid(t)?parseInt(t,10):e};_t.getCapacity=function(t,e,i){if(!co.isValid(t))throw new Error("Invalid QR Code version");typeof i>"u"&&(i=vt.BYTE);let n=Ae.getSymbolTotalCodewords(t),o=Jr.getTotalCodewordsCount(t,e),s=(n-o)*8;if(i===vt.MIXED)return s;let a=s-Ri(i,t);switch(i){case vt.NUMERIC:return Math.floor(a/10*3);case vt.ALPHANUMERIC:return Math.floor(a/11*2);case vt.KANJI:return Math.floor(a/13);case vt.BYTE:default:return Math.floor(a/8)}};_t.getBestVersionForData=function(t,e){let i,n=yi.from(e,yi.M);if(Array.isArray(t)){if(t.length>1)return Zr(t,n);if(t.length===0)return 1;i=t[0]}else i=t;return Qr(i.mode,i.getLength(),n)};_t.getEncodedBits=function(t){if(!co.isValid(t)||t<7)throw new Error("Invalid QR Code version");let e=t<<12;for(;Ae.getBCHDigit(e)-Ci>=0;)e^=Ei<<Ae.getBCHDigit(e)-Ci;return t<<12|e}});var _i=S(Si=>{var uo=gt(),Wi=1335,tn=21522,Ii=uo.getBCHDigit(Wi);Si.getEncodedBits=function(t,e){let i=t.bit<<3|e,n=i<<10;for(;uo.getBCHDigit(n)-Ii>=0;)n^=Wi<<uo.getBCHDigit(n)-Ii;return(i<<10|n)^tn}});var Li=S((Ed,Ti)=>{var en=bt();function kt(r){this.mode=en.NUMERIC,this.data=r.toString()}kt.getBitsLength=function(t){return 10*Math.floor(t/3)+(t%3?t%3*3+1:0)};kt.prototype.getLength=function(){return this.data.length};kt.prototype.getBitsLength=function(){return kt.getBitsLength(this.data.length)};kt.prototype.write=function(t){let e,i,n;for(e=0;e+3<=this.data.length;e+=3)i=this.data.substr(e,3),n=parseInt(i,10),t.put(n,10);let o=this.data.length-e;o>0&&(i=this.data.substr(e),n=parseInt(i,10),t.put(n,o*3+1))};Ti.exports=kt});var Oi=S((Rd,Bi)=>{var on=bt(),po=["0","1","2","3","4","5","6","7","8","9","A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z"," ","$","%","*","+","-",".","/",":"];function zt(r){this.mode=on.ALPHANUMERIC,this.data=r}zt.getBitsLength=function(t){return 11*Math.floor(t/2)+6*(t%2)};zt.prototype.getLength=function(){return this.data.length};zt.prototype.getBitsLength=function(){return zt.getBitsLength(this.data.length)};zt.prototype.write=function(t){let e;for(e=0;e+2<=this.data.length;e+=2){let i=po.indexOf(this.data[e])*45;i+=po.indexOf(this.data[e+1]),t.put(i,11)}this.data.length%2&&t.put(po.indexOf(this.data[e]),6)};Bi.exports=zt});var Pi=S(($d,Ai)=>{"use strict";Ai.exports=function(t){for(var e=[],i=t.length,n=0;n<i;n++){var o=t.charCodeAt(n);if(o>=55296&&o<=56319&&i>n+1){var s=t.charCodeAt(n+1);s>=56320&&s<=57343&&(o=(o-55296)*1024+s-56320+65536,n+=1)}if(o<128){e.push(o);continue}if(o<2048){e.push(o>>6|192),e.push(o&63|128);continue}if(o<55296||o>=57344&&o<65536){e.push(o>>12|224),e.push(o>>6&63|128),e.push(o&63|128);continue}if(o>=65536&&o<=1114111){e.push(o>>18|240),e.push(o>>12&63|128),e.push(o>>6&63|128),e.push(o&63|128);continue}e.push(239,191,189)}return new Uint8Array(e).buffer}});var ji=S((Id,Di)=>{var rn=Pi(),nn=bt();function Ut(r){this.mode=nn.BYTE,typeof r=="string"&&(r=rn(r)),this.data=new Uint8Array(r)}Ut.getBitsLength=function(t){return t*8};Ut.prototype.getLength=function(){return this.data.length};Ut.prototype.getBitsLength=function(){return Ut.getBitsLength(this.data.length)};Ut.prototype.write=function(r){for(let t=0,e=this.data.length;t<e;t++)r.put(this.data[t],8)};Di.exports=Ut});var zi=S((Wd,ki)=>{var sn=bt(),an=gt();function Nt(r){this.mode=sn.KANJI,this.data=r}Nt.getBitsLength=function(t){return t*13};Nt.prototype.getLength=function(){return this.data.length};Nt.prototype.getBitsLength=function(){return Nt.getBitsLength(this.data.length)};Nt.prototype.write=function(r){let t;for(t=0;t<this.data.length;t++){let e=an.toSJIS(this.data[t]);if(e>=33088&&e<=40956)e-=33088;else if(e>=57408&&e<=60351)e-=49472;else throw new Error("Invalid SJIS character: "+this.data[t]+`
Make sure your charset is UTF-8`);e=(e>>>8&255)*192+(e&255),r.put(e,13)}};ki.exports=Nt});var Ki=S(Mt=>{var I=bt(),Mi=Li(),qi=Oi(),Fi=ji(),Vi=zi(),ne=ao(),Pe=gt(),ln=Or();function Ui(r){return unescape(encodeURIComponent(r)).length}function se(r,t,e){let i=[],n;for(;(n=r.exec(e))!==null;)i.push({data:n[0],index:n.index,mode:t,length:n[0].length});return i}function Hi(r){let t=se(ne.NUMERIC,I.NUMERIC,r),e=se(ne.ALPHANUMERIC,I.ALPHANUMERIC,r),i,n;return Pe.isKanjiModeEnabled()?(i=se(ne.BYTE,I.BYTE,r),n=se(ne.KANJI,I.KANJI,r)):(i=se(ne.BYTE_KANJI,I.BYTE,r),n=[]),t.concat(e,i,n).sort(function(s,a){return s.index-a.index}).map(function(s){return{data:s.data,mode:s.mode,length:s.length}})}function ho(r,t){switch(t){case I.NUMERIC:return Mi.getBitsLength(r);case I.ALPHANUMERIC:return qi.getBitsLength(r);case I.KANJI:return Vi.getBitsLength(r);case I.BYTE:return Fi.getBitsLength(r)}}function cn(r){return r.reduce(function(t,e){let i=t.length-1>=0?t[t.length-1]:null;return i&&i.mode===e.mode?(t[t.length-1].data+=e.data,t):(t.push(e),t)},[])}function un(r){let t=[];for(let e=0;e<r.length;e++){let i=r[e];switch(i.mode){case I.NUMERIC:t.push([i,{data:i.data,mode:I.ALPHANUMERIC,length:i.length},{data:i.data,mode:I.BYTE,length:i.length}]);break;case I.ALPHANUMERIC:t.push([i,{data:i.data,mode:I.BYTE,length:i.length}]);break;case I.KANJI:t.push([i,{data:i.data,mode:I.BYTE,length:Ui(i.data)}]);break;case I.BYTE:t.push([{data:i.data,mode:I.BYTE,length:Ui(i.data)}])}}return t}function dn(r,t){let e={},i={start:{}},n=["start"];for(let o=0;o<r.length;o++){let s=r[o],a=[];for(let u=0;u<s.length;u++){let b=s[u],w=""+o+u;a.push(w),e[w]={node:b,lastCount:0},i[w]={};for(let R=0;R<n.length;R++){let T=n[R];e[T]&&e[T].node.mode===b.mode?(i[T][w]=ho(e[T].lastCount+b.length,b.mode)-ho(e[T].lastCount,b.mode),e[T].lastCount+=b.length):(e[T]&&(e[T].lastCount=b.length),i[T][w]=ho(b.length,b.mode)+4+I.getCharCountIndicator(b.mode,t))}}n=a}for(let o=0;o<n.length;o++)i[n[o]].end=0;return{map:i,table:e}}function Ni(r,t){let e,i=I.getBestModeForData(r);if(e=I.from(t,i),e!==I.BYTE&&e.bit<i.bit)throw new Error('"'+r+'" cannot be encoded with mode '+I.toString(e)+`.
 Suggested mode is: `+I.toString(i));switch(e===I.KANJI&&!Pe.isKanjiModeEnabled()&&(e=I.BYTE),e){case I.NUMERIC:return new Mi(r);case I.ALPHANUMERIC:return new qi(r);case I.KANJI:return new Vi(r);case I.BYTE:return new Fi(r)}}Mt.fromArray=function(t){return t.reduce(function(e,i){return typeof i=="string"?e.push(Ni(i,null)):i.data&&e.push(Ni(i.data,i.mode)),e},[])};Mt.fromString=function(t,e){let i=Hi(t,Pe.isKanjiModeEnabled()),n=un(i),o=dn(n,e),s=ln.find_path(o.map,"start","end"),a=[];for(let u=1;u<s.length-1;u++)a.push(o.table[s[u]].node);return Mt.fromArray(cn(a))};Mt.rawSplit=function(t){return Mt.fromArray(Hi(t,Pe.isKanjiModeEnabled()))}});var Yi=S(Gi=>{var je=gt(),mo=Se(),pn=si(),hn=li(),mn=ci(),fn=pi(),wo=hi(),bo=io(),gn=bi(),De=$i(),wn=_i(),bn=bt(),fo=Ki();function vn(r,t){let e=r.size,i=fn.getPositions(t);for(let n=0;n<i.length;n++){let o=i[n][0],s=i[n][1];for(let a=-1;a<=7;a++)if(!(o+a<=-1||e<=o+a))for(let u=-1;u<=7;u++)s+u<=-1||e<=s+u||(a>=0&&a<=6&&(u===0||u===6)||u>=0&&u<=6&&(a===0||a===6)||a>=2&&a<=4&&u>=2&&u<=4?r.set(o+a,s+u,!0,!0):r.set(o+a,s+u,!1,!0))}}function xn(r){let t=r.size;for(let e=8;e<t-8;e++){let i=e%2===0;r.set(e,6,i,!0),r.set(6,e,i,!0)}}function yn(r,t){let e=mn.getPositions(t);for(let i=0;i<e.length;i++){let n=e[i][0],o=e[i][1];for(let s=-2;s<=2;s++)for(let a=-2;a<=2;a++)s===-2||s===2||a===-2||a===2||s===0&&a===0?r.set(n+s,o+a,!0,!0):r.set(n+s,o+a,!1,!0)}}function Cn(r,t){let e=r.size,i=De.getEncodedBits(t),n,o,s;for(let a=0;a<18;a++)n=Math.floor(a/3),o=a%3+e-8-3,s=(i>>a&1)===1,r.set(n,o,s,!0),r.set(o,n,s,!0)}function go(r,t,e){let i=r.size,n=wn.getEncodedBits(t,e),o,s;for(o=0;o<15;o++)s=(n>>o&1)===1,o<6?r.set(o,8,s,!0):o<8?r.set(o+1,8,s,!0):r.set(i-15+o,8,s,!0),o<8?r.set(8,i-o-1,s,!0):o<9?r.set(8,15-o-1+1,s,!0):r.set(8,15-o-1,s,!0);r.set(i-8,8,1,!0)}function En(r,t){let e=r.size,i=-1,n=e-1,o=7,s=0;for(let a=e-1;a>0;a-=2)for(a===6&&a--;;){for(let u=0;u<2;u++)if(!r.isReserved(n,a-u)){let b=!1;s<t.length&&(b=(t[s]>>>o&1)===1),r.set(n,a-u,b),o--,o===-1&&(s++,o=7)}if(n+=i,n<0||e<=n){n-=i,i=-i;break}}}function Rn(r,t,e){let i=new pn;e.forEach(function(u){i.put(u.mode.bit,4),i.put(u.getLength(),bn.getCharCountIndicator(u.mode,r)),u.write(i)});let n=je.getSymbolTotalCodewords(r),o=bo.getTotalCodewordsCount(r,t),s=(n-o)*8;for(i.getLengthInBits()+4<=s&&i.put(0,4);i.getLengthInBits()%8!==0;)i.putBit(0);let a=(s-i.getLengthInBits())/8;for(let u=0;u<a;u++)i.put(u%2?17:236,8);return $n(i,r,t)}function $n(r,t,e){let i=je.getSymbolTotalCodewords(t),n=bo.getTotalCodewordsCount(t,e),o=i-n,s=bo.getBlocksCount(t,e),a=i%s,u=s-a,b=Math.floor(i/s),w=Math.floor(o/s),R=w+1,T=b-w,K=new gn(T),V=0,L=new Array(s),$=new Array(s),k=0,W=new Uint8Array(r.buffer);for(let Ot=0;Ot<s;Ot++){let Ve=Ot<u?w:R;L[Ot]=W.slice(V,V+Ve),$[Ot]=K.encode(L[Ot]),V+=Ve,k=Math.max(k,Ve)}let z=new Uint8Array(i),P=0,D,nt;for(D=0;D<k;D++)for(nt=0;nt<s;nt++)D<L[nt].length&&(z[P++]=L[nt][D]);for(D=0;D<T;D++)for(nt=0;nt<s;nt++)z[P++]=$[nt][D];return z}function In(r,t,e,i){let n;if(Array.isArray(r))n=fo.fromArray(r);else if(typeof r=="string"){let b=t;if(!b){let w=fo.rawSplit(r);b=De.getBestVersionForData(w,e)}n=fo.fromString(r,b||40)}else throw new Error("Invalid data");let o=De.getBestVersionForData(n,e);if(!o)throw new Error("The amount of data is too big to be stored in a QR Code");if(!t)t=o;else if(t<o)throw new Error(`
The chosen QR Code version cannot contain this amount of data.
Minimum version required to store current data is: `+o+`.
`);let s=Rn(t,e,n),a=je.getSymbolSize(t),u=new hn(a);return vn(u,t),xn(u),yn(u,t),go(u,e,0),t>=7&&Cn(u,t),En(u,s),isNaN(i)&&(i=wo.getBestMask(u,go.bind(null,u,e))),wo.applyMask(i,u),go(u,e,i),{modules:u,version:t,errorCorrectionLevel:e,maskPattern:i,segments:n}}Gi.create=function(t,e){if(typeof t>"u"||t==="")throw new Error("No input text");let i=mo.M,n,o;return typeof e<"u"&&(i=mo.from(e.errorCorrectionLevel,mo.M),n=De.from(e.version),o=wo.from(e.maskPattern),e.toSJISFunc&&je.setToSJISFunction(e.toSJISFunc)),In(t,n,i,o)}});var vo=S(Tt=>{function Ji(r){if(typeof r=="number"&&(r=r.toString()),typeof r!="string")throw new Error("Color should be defined as hex string");let t=r.slice().replace("#","").split("");if(t.length<3||t.length===5||t.length>8)throw new Error("Invalid hex color: "+r);(t.length===3||t.length===4)&&(t=Array.prototype.concat.apply([],t.map(function(i){return[i,i]}))),t.length===6&&t.push("F","F");let e=parseInt(t.join(""),16);return{r:e>>24&255,g:e>>16&255,b:e>>8&255,a:e&255,hex:"#"+t.slice(0,6).join("")}}Tt.getOptions=function(t){t||(t={}),t.color||(t.color={});let e=typeof t.margin>"u"||t.margin===null||t.margin<0?4:t.margin,i=t.width&&t.width>=21?t.width:void 0,n=t.scale||4;return{width:i,scale:i?4:n,margin:e,color:{dark:Ji(t.color.dark||"#000000ff"),light:Ji(t.color.light||"#ffffffff")},type:t.type,rendererOpts:t.rendererOpts||{}}};Tt.getScale=function(t,e){return e.width&&e.width>=t+e.margin*2?e.width/(t+e.margin*2):e.scale};Tt.getImageWidth=function(t,e){let i=Tt.getScale(t,e);return Math.floor((t+e.margin*2)*i)};Tt.qrToImageData=function(t,e,i){let n=e.modules.size,o=e.modules.data,s=Tt.getScale(n,i),a=Math.floor((n+i.margin*2)*s),u=i.margin*s,b=[i.color.light,i.color.dark];for(let w=0;w<a;w++)for(let R=0;R<a;R++){let T=(w*a+R)*4,K=i.color.light;if(w>=u&&R>=u&&w<a-u&&R<a-u){let V=Math.floor((w-u)/s),L=Math.floor((R-u)/s);K=b[o[V*n+L]?1:0]}t[T++]=K.r,t[T++]=K.g,t[T++]=K.b,t[T]=K.a}}});var Qi=S(ke=>{var xo=vo();function Wn(r,t,e){r.clearRect(0,0,t.width,t.height),t.style||(t.style={}),t.height=e,t.width=e,t.style.height=e+"px",t.style.width=e+"px"}function Sn(){try{return document.createElement("canvas")}catch{throw new Error("You need to specify a canvas element")}}ke.render=function(t,e,i){let n=i,o=e;typeof n>"u"&&(!e||!e.getContext)&&(n=e,e=void 0),e||(o=Sn()),n=xo.getOptions(n);let s=xo.getImageWidth(t.modules.size,n),a=o.getContext("2d"),u=a.createImageData(s,s);return xo.qrToImageData(u.data,t,n),Wn(a,o,s),a.putImageData(u,0,0),o};ke.renderToDataURL=function(t,e,i){let n=i;typeof n>"u"&&(!e||!e.getContext)&&(n=e,e=void 0),n||(n={});let o=ke.render(t,e,n),s=n.type||"image/png",a=n.rendererOpts||{};return o.toDataURL(s,a.quality)}});var tr=S(Zi=>{var _n=vo();function Xi(r,t){let e=r.a/255,i=t+'="'+r.hex+'"';return e<1?i+" "+t+'-opacity="'+e.toFixed(2).slice(1)+'"':i}function yo(r,t,e){let i=r+t;return typeof e<"u"&&(i+=" "+e),i}function Tn(r,t,e){let i="",n=0,o=!1,s=0;for(let a=0;a<r.length;a++){let u=Math.floor(a%t),b=Math.floor(a/t);!u&&!o&&(o=!0),r[a]?(s++,a>0&&u>0&&r[a-1]||(i+=o?yo("M",u+e,.5+b+e):yo("m",n,0),n=0,o=!1),u+1<t&&r[a+1]||(i+=yo("h",s),s=0)):n++}return i}Zi.render=function(t,e,i){let n=_n.getOptions(e),o=t.modules.size,s=t.modules.data,a=o+n.margin*2,u=n.color.light.a?"<path "+Xi(n.color.light,"fill")+' d="M0 0h'+a+"v"+a+'H0z"/>':"",b="<path "+Xi(n.color.dark,"stroke")+' d="'+Tn(s,o,n.margin)+'"/>',w='viewBox="0 0 '+a+" "+a+'"',T='<svg xmlns="http://www.w3.org/2000/svg" '+(n.width?'width="'+n.width+'" height="'+n.width+'" ':"")+w+' shape-rendering="crispEdges">'+u+b+`</svg>
`;return typeof i=="function"&&i(null,T),T}});var or=S(ae=>{var Ln=ii(),Co=Yi(),er=Qi(),Bn=tr();function Eo(r,t,e,i,n){let o=[].slice.call(arguments,1),s=o.length,a=typeof o[s-1]=="function";if(!a&&!Ln())throw new Error("Callback required as last argument");if(a){if(s<2)throw new Error("Too few arguments provided");s===2?(n=e,e=t,t=i=void 0):s===3&&(t.getContext&&typeof n>"u"?(n=i,i=void 0):(n=i,i=e,e=t,t=void 0))}else{if(s<1)throw new Error("Too few arguments provided");return s===1?(e=t,t=i=void 0):s===2&&!t.getContext&&(i=e,e=t,t=void 0),new Promise(function(u,b){try{let w=Co.create(e,i);u(r(w,t,i))}catch(w){b(w)}})}try{let u=Co.create(e,i);n(null,r(u,t,i))}catch(u){n(u)}}ae.create=Co.create;ae.toCanvas=Eo.bind(null,er.render);ae.toDataURL=Eo.bind(null,er.renderToDataURL);ae.toString=Eo.bind(null,function(r,t,e){return Bn.render(r,e)})});var ko=g`
  :host {
    position: relative;
    background-color: var(--wui-color-gray-glass-002);
    display: flex;
    justify-content: center;
    align-items: center;
    width: var(--local-size);
    height: var(--local-size);
    border-radius: inherit;
    border-radius: var(--local-border-radius);
  }

  :host > wui-flex {
    overflow: hidden;
    border-radius: inherit;
    border-radius: var(--local-border-radius);
  }

  :host::after {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    right: 0;
    border-radius: inherit;
    border: 1px solid var(--wui-color-gray-glass-010);
    pointer-events: none;
  }

  :host([name='Extension'])::after {
    border: 1px solid var(--wui-color-accent-glass-010);
  }

  :host([data-wallet-icon='allWallets']) {
    background-color: var(--wui-all-wallets-bg-100);
  }

  :host([data-wallet-icon='allWallets'])::after {
    border: 1px solid var(--wui-color-accent-glass-010);
  }

  wui-icon[data-parent-size='inherit'] {
    width: 75%;
    height: 75%;
    align-items: center;
  }

  wui-icon[data-parent-size='sm'] {
    width: 18px;
    height: 18px;
  }

  wui-icon[data-parent-size='md'] {
    width: 24px;
    height: 24px;
  }

  wui-icon[data-parent-size='lg'] {
    width: 42px;
    height: 42px;
  }

  wui-icon[data-parent-size='full'] {
    width: 100%;
    height: 100%;
  }

  :host > wui-icon-box {
    position: absolute;
    overflow: hidden;
    right: -1px;
    bottom: -2px;
    z-index: 1;
    border: 2px solid var(--wui-color-bg-150, #1e1f1f);
    padding: 1px;
  }
`;var Ct=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},at=class extends p{constructor(){super(...arguments),this.size="md",this.name="",this.installed=!1,this.badgeSize="xs"}render(){let t="xxs";return this.size==="lg"?t="m":this.size==="md"?t="xs":t="xxs",this.style.cssText=`
       --local-border-radius: var(--wui-border-radius-${t});
       --local-size: var(--wui-wallet-image-size-${this.size});
   `,this.walletIcon&&(this.dataset.walletIcon=this.walletIcon),l`
      <wui-flex justifyContent="center" alignItems="center"> ${this.templateVisual()} </wui-flex>
    `}templateVisual(){return this.imageSrc?l`<wui-image src=${this.imageSrc} alt=${this.name}></wui-image>`:this.walletIcon?l`<wui-icon
        data-parent-size="md"
        size="md"
        color="inherit"
        name=${this.walletIcon}
      ></wui-icon>`:l`<wui-icon
      data-parent-size=${this.size}
      size="inherit"
      color="inherit"
      name="walletPlaceholder"
    ></wui-icon>`}};at.styles=[_,y,ko];Ct([c()],at.prototype,"size",void 0);Ct([c()],at.prototype,"name",void 0);Ct([c()],at.prototype,"imageSrc",void 0);Ct([c()],at.prototype,"walletIcon",void 0);Ct([c({type:Boolean})],at.prototype,"installed",void 0);Ct([c()],at.prototype,"badgeSize",void 0);at=Ct([d("wui-wallet-image")],at);var zo=g`
  :host {
    position: relative;
    border-radius: var(--wui-border-radius-xxs);
    width: 40px;
    height: 40px;
    overflow: hidden;
    background: var(--wui-color-gray-glass-002);
    display: flex;
    justify-content: center;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--wui-spacing-4xs);
    padding: 3.75px !important;
  }

  :host::after {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    right: 0;
    border-radius: inherit;
    border: 1px solid var(--wui-color-gray-glass-010);
    pointer-events: none;
  }

  :host > wui-wallet-image {
    width: 14px;
    height: 14px;
    border-radius: var(--wui-border-radius-5xs);
  }

  :host > wui-flex {
    padding: 2px;
    position: fixed;
    overflow: hidden;
    left: 34px;
    bottom: 8px;
    background: var(--dark-background-150, #1e1f1f);
    border-radius: 50%;
    z-index: 2;
    display: flex;
  }
`;var Uo=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Ge=4,he=class extends p{constructor(){super(...arguments),this.walletImages=[]}render(){let t=this.walletImages.length<Ge;return l`${this.walletImages.slice(0,Ge).map(({src:e,walletName:i})=>l`
            <wui-wallet-image
              size="inherit"
              imageSrc=${e}
              name=${h(i)}
            ></wui-wallet-image>
          `)}
      ${t?[...Array(Ge-this.walletImages.length)].map(()=>l` <wui-wallet-image size="inherit" name=""></wui-wallet-image>`):null}
      <wui-flex>
        <wui-icon-box
          size="xxs"
          iconSize="xxs"
          iconcolor="success-100"
          backgroundcolor="success-100"
          icon="checkmark"
          background="opaque"
        ></wui-icon-box>
      </wui-flex>`}};he.styles=[y,zo];Uo([c({type:Array})],he.prototype,"walletImages",void 0);he=Uo([d("wui-all-wallets-image")],he);var No=g`
  button {
    column-gap: var(--wui-spacing-s);
    padding: 7px var(--wui-spacing-l) 7px var(--wui-spacing-xs);
    width: 100%;
    background-color: var(--wui-color-gray-glass-002);
    border-radius: var(--wui-border-radius-xs);
    color: var(--wui-color-fg-100);
  }

  button > wui-text:nth-child(2) {
    display: flex;
    flex: 1;
  }

  button:disabled {
    background-color: var(--wui-color-gray-glass-015);
    color: var(--wui-color-gray-glass-015);
  }

  button:disabled > wui-tag {
    background-color: var(--wui-color-gray-glass-010);
    color: var(--wui-color-fg-300);
  }

  wui-icon {
    color: var(--wui-color-fg-200) !important;
  }
`;var q=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},M=class extends p{constructor(){super(...arguments),this.walletImages=[],this.imageSrc="",this.name="",this.tabIdx=void 0,this.installed=!1,this.disabled=!1,this.showAllWallets=!1,this.loading=!1,this.loadingSpinnerColor="accent-100"}render(){return l`
      <button ?disabled=${this.disabled} tabindex=${h(this.tabIdx)}>
        ${this.templateAllWallets()} ${this.templateWalletImage()}
        <wui-text variant="paragraph-500" color="inherit">${this.name}</wui-text>
        ${this.templateStatus()}
      </button>
    `}templateAllWallets(){return this.showAllWallets&&this.imageSrc?l` <wui-all-wallets-image .imageeSrc=${this.imageSrc}> </wui-all-wallets-image> `:this.showAllWallets&&this.walletIcon?l` <wui-wallet-image .walletIcon=${this.walletIcon} size="sm"> </wui-wallet-image> `:null}templateWalletImage(){return!this.showAllWallets&&this.imageSrc?l`<wui-wallet-image
        size="sm"
        imageSrc=${this.imageSrc}
        name=${this.name}
        .installed=${this.installed}
      ></wui-wallet-image>`:!this.showAllWallets&&!this.imageSrc?l`<wui-wallet-image size="sm" name=${this.name}></wui-wallet-image>`:null}templateStatus(){return this.loading?l`<wui-loading-spinner
        size="lg"
        color=${this.loadingSpinnerColor}
      ></wui-loading-spinner>`:this.tagLabel&&this.tagVariant?l`<wui-tag variant=${this.tagVariant}>${this.tagLabel}</wui-tag>`:this.icon?l`<wui-icon color="inherit" size="sm" name=${this.icon}></wui-icon>`:null}};M.styles=[y,_,No];q([c({type:Array})],M.prototype,"walletImages",void 0);q([c()],M.prototype,"imageSrc",void 0);q([c()],M.prototype,"name",void 0);q([c()],M.prototype,"tagLabel",void 0);q([c()],M.prototype,"tagVariant",void 0);q([c()],M.prototype,"icon",void 0);q([c()],M.prototype,"walletIcon",void 0);q([c()],M.prototype,"tabIdx",void 0);q([c({type:Boolean})],M.prototype,"installed",void 0);q([c({type:Boolean})],M.prototype,"disabled",void 0);q([c({type:Boolean})],M.prototype,"showAllWallets",void 0);q([c({type:Boolean})],M.prototype,"loading",void 0);q([c({type:String})],M.prototype,"loadingSpinnerColor",void 0);M=q([d("wui-list-wallet")],M);var At=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Et=class extends p{constructor(){super(),this.unsubscribe=[],this.tabIdx=void 0,this.connectors=v.state.connectors,this.count=E.state.count,this.filteredCount=E.state.filteredWallets.length,this.isFetchingRecommendedWallets=E.state.isFetchingRecommendedWallets,this.unsubscribe.push(v.subscribeKey("connectors",t=>this.connectors=t),E.subscribeKey("count",t=>this.count=t),E.subscribeKey("filteredWallets",t=>this.filteredCount=t.length),E.subscribeKey("isFetchingRecommendedWallets",t=>this.isFetchingRecommendedWallets=t))}disconnectedCallback(){this.unsubscribe.forEach(t=>t())}render(){let t=this.connectors.find(u=>u.id==="walletConnect"),{allWallets:e}=N.state;if(!t||e==="HIDE"||e==="ONLY_MOBILE"&&!f.isMobile())return null;let i=E.state.featured.length,n=this.count+i,o=n<10?n:Math.floor(n/10)*10,s=this.filteredCount>0?this.filteredCount:o,a=`${s}`;return this.filteredCount>0?a=`${this.filteredCount}`:s<n&&(a=`${s}+`),l`
      <wui-list-wallet
        name="All Wallets"
        walletIcon="allWallets"
        showAllWallets
        @click=${this.onAllWallets.bind(this)}
        tagLabel=${a}
        tagVariant="shade"
        data-testid="all-wallets"
        tabIdx=${h(this.tabIdx)}
        .loading=${this.isFetchingRecommendedWallets}
        loadingSpinnerColor=${this.isFetchingRecommendedWallets?"fg-300":"accent-100"}
      ></wui-list-wallet>
    `}onAllWallets(){U.sendEvent({type:"track",event:"CLICK_ALL_WALLETS"}),C.push("AllWallets")}};At([c()],Et.prototype,"tabIdx",void 0);At([m()],Et.prototype,"connectors",void 0);At([m()],Et.prototype,"count",void 0);At([m()],Et.prototype,"filteredCount",void 0);At([m()],Et.prototype,"isFetchingRecommendedWallets",void 0);Et=At([d("w3m-all-wallets-widget")],Et);var Ye=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},me=class extends p{constructor(){super(),this.unsubscribe=[],this.tabIdx=void 0,this.connectors=v.state.connectors,this.unsubscribe.push(v.subscribeKey("connectors",t=>this.connectors=t))}disconnectedCallback(){this.unsubscribe.forEach(t=>t())}render(){let t=this.connectors.filter(e=>e.type==="ANNOUNCED");return t?.length?l`
      <wui-flex flexDirection="column" gap="xs">
        ${t.filter(st.showConnector).map(e=>l`
              <wui-list-wallet
                imageSrc=${h(B.getConnectorImage(e))}
                name=${e.name??"Unknown"}
                @click=${()=>this.onConnector(e)}
                tagVariant="success"
                tagLabel="installed"
                data-testid=${`wallet-selector-${e.id}`}
                .installed=${!0}
                tabIdx=${h(this.tabIdx)}
              >
              </wui-list-wallet>
            `)}
      </wui-flex>
    `:(this.style.cssText="display: none",null)}onConnector(t){t.id==="walletConnect"?f.isMobile()?C.push("AllWallets"):C.push("ConnectingWalletConnect"):C.push("ConnectingExternal",{connector:t})}};Ye([c()],me.prototype,"tabIdx",void 0);Ye([m()],me.prototype,"connectors",void 0);me=Ye([d("w3m-connect-announced-widget")],me);var fe=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Jt=class extends p{constructor(){super(),this.unsubscribe=[],this.tabIdx=void 0,this.connectors=v.state.connectors,this.loading=!1,this.unsubscribe.push(v.subscribeKey("connectors",t=>this.connectors=t)),f.isTelegram()&&f.isIos()&&(this.loading=!x.state.wcUri,this.unsubscribe.push(x.subscribeKey("wcUri",t=>this.loading=!t)))}disconnectedCallback(){this.unsubscribe.forEach(t=>t())}render(){let{customWallets:t}=N.state;if(!t?.length)return this.style.cssText="display: none",null;let e=this.filterOutDuplicateWallets(t);return l`<wui-flex flexDirection="column" gap="xs">
      ${e.map(i=>l`
          <wui-list-wallet
            imageSrc=${h(B.getWalletImage(i))}
            name=${i.name??"Unknown"}
            @click=${()=>this.onConnectWallet(i)}
            data-testid=${`wallet-selector-${i.id}`}
            tabIdx=${h(this.tabIdx)}
            ?loading=${this.loading}
          >
          </wui-list-wallet>
        `)}
    </wui-flex>`}filterOutDuplicateWallets(t){let e=pt.getRecentWallets(),i=this.connectors.map(a=>a.info?.rdns).filter(Boolean),n=e.map(a=>a.rdns).filter(Boolean),o=i.concat(n);if(o.includes("io.metamask.mobile")&&f.isMobile()){let a=o.indexOf("io.metamask.mobile");o[a]="io.metamask"}return t.filter(a=>!o.includes(String(a?.rdns)))}onConnectWallet(t){this.loading||C.push("ConnectingWalletConnect",{wallet:t})}};fe([c()],Jt.prototype,"tabIdx",void 0);fe([m()],Jt.prototype,"connectors",void 0);fe([m()],Jt.prototype,"loading",void 0);Jt=fe([d("w3m-connect-custom-widget")],Jt);var Je=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},ge=class extends p{constructor(){super(),this.unsubscribe=[],this.tabIdx=void 0,this.connectors=v.state.connectors,this.unsubscribe.push(v.subscribeKey("connectors",t=>this.connectors=t))}disconnectedCallback(){this.unsubscribe.forEach(t=>t())}render(){let i=this.connectors.filter(n=>n.type==="EXTERNAL").filter(st.showConnector).filter(n=>n.id!==Oo.CONNECTOR_ID.COINBASE_SDK);return i?.length?l`
      <wui-flex flexDirection="column" gap="xs">
        ${i.map(n=>l`
            <wui-list-wallet
              imageSrc=${h(B.getConnectorImage(n))}
              .installed=${!0}
              name=${n.name??"Unknown"}
              data-testid=${`wallet-selector-external-${n.id}`}
              @click=${()=>this.onConnector(n)}
              tabIdx=${h(this.tabIdx)}
            >
            </wui-list-wallet>
          `)}
      </wui-flex>
    `:(this.style.cssText="display: none",null)}onConnector(t){C.push("ConnectingExternal",{connector:t})}};Je([c()],ge.prototype,"tabIdx",void 0);Je([m()],ge.prototype,"connectors",void 0);ge=Je([d("w3m-connect-external-widget")],ge);var Qe=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},we=class extends p{constructor(){super(...arguments),this.tabIdx=void 0,this.wallets=[]}render(){return this.wallets.length?l`
      <wui-flex flexDirection="column" gap="xs">
        ${this.wallets.map(t=>l`
            <wui-list-wallet
              data-testid=${`wallet-selector-featured-${t.id}`}
              imageSrc=${h(B.getWalletImage(t))}
              name=${t.name??"Unknown"}
              @click=${()=>this.onConnectWallet(t)}
              tabIdx=${h(this.tabIdx)}
            >
            </wui-list-wallet>
          `)}
      </wui-flex>
    `:(this.style.cssText="display: none",null)}onConnectWallet(t){v.selectWalletConnector(t)}};Qe([c()],we.prototype,"tabIdx",void 0);Qe([c()],we.prototype,"wallets",void 0);we=Qe([d("w3m-connect-featured-widget")],we);var Xe=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},be=class extends p{constructor(){super(...arguments),this.tabIdx=void 0,this.connectors=[]}render(){let t=this.connectors.filter(st.showConnector);return t.length===0?(this.style.cssText="display: none",null):l`
      <wui-flex flexDirection="column" gap="xs">
        ${t.map(e=>l`
            <wui-list-wallet
              imageSrc=${h(B.getConnectorImage(e))}
              .installed=${!0}
              name=${e.name??"Unknown"}
              tagVariant="success"
              tagLabel="installed"
              data-testid=${`wallet-selector-${e.id}`}
              @click=${()=>this.onConnector(e)}
              tabIdx=${h(this.tabIdx)}
            >
            </wui-list-wallet>
          `)}
      </wui-flex>
    `}onConnector(t){v.setActiveConnector(t),C.push("ConnectingExternal",{connector:t})}};Xe([c()],be.prototype,"tabIdx",void 0);Xe([c()],be.prototype,"connectors",void 0);be=Xe([d("w3m-connect-injected-widget")],be);var Ze=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},ve=class extends p{constructor(){super(),this.unsubscribe=[],this.tabIdx=void 0,this.connectors=v.state.connectors,this.unsubscribe.push(v.subscribeKey("connectors",t=>this.connectors=t))}disconnectedCallback(){this.unsubscribe.forEach(t=>t())}render(){let t=this.connectors.filter(e=>e.type==="MULTI_CHAIN"&&e.name!=="WalletConnect");return t?.length?l`
      <wui-flex flexDirection="column" gap="xs">
        ${t.map(e=>l`
            <wui-list-wallet
              imageSrc=${h(B.getConnectorImage(e))}
              .installed=${!0}
              name=${e.name??"Unknown"}
              tagVariant="shade"
              tagLabel="multichain"
              data-testid=${`wallet-selector-${e.id}`}
              @click=${()=>this.onConnector(e)}
              tabIdx=${h(this.tabIdx)}
            >
            </wui-list-wallet>
          `)}
      </wui-flex>
    `:(this.style.cssText="display: none",null)}onConnector(t){v.setActiveConnector(t),C.push("ConnectingMultiChain")}};Ze([c()],ve.prototype,"tabIdx",void 0);Ze([m()],ve.prototype,"connectors",void 0);ve=Ze([d("w3m-connect-multi-chain-widget")],ve);var xe=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Qt=class extends p{constructor(){super(),this.unsubscribe=[],this.tabIdx=void 0,this.connectors=v.state.connectors,this.loading=!1,this.unsubscribe.push(v.subscribeKey("connectors",t=>this.connectors=t)),f.isTelegram()&&f.isIos()&&(this.loading=!x.state.wcUri,this.unsubscribe.push(x.subscribeKey("wcUri",t=>this.loading=!t)))}render(){let e=pt.getRecentWallets().filter(i=>!ht.isExcluded(i)).filter(i=>!this.hasWalletConnector(i)).filter(i=>this.isWalletCompatibleWithCurrentChain(i));return e.length?l`
      <wui-flex flexDirection="column" gap="xs">
        ${e.map(i=>l`
            <wui-list-wallet
              imageSrc=${h(B.getWalletImage(i))}
              name=${i.name??"Unknown"}
              @click=${()=>this.onConnectWallet(i)}
              tagLabel="recent"
              tagVariant="shade"
              tabIdx=${h(this.tabIdx)}
              ?loading=${this.loading}
            >
            </wui-list-wallet>
          `)}
      </wui-flex>
    `:(this.style.cssText="display: none",null)}onConnectWallet(t){this.loading||v.selectWalletConnector(t)}hasWalletConnector(t){return this.connectors.some(e=>e.id===t.id||e.name===t.name)}isWalletCompatibleWithCurrentChain(t){let e=Yt.state.activeChain;return e&&t.chains?t.chains.some(i=>{let n=i.split(":")[0];return e===n}):!0}};xe([c()],Qt.prototype,"tabIdx",void 0);xe([m()],Qt.prototype,"connectors",void 0);xe([m()],Qt.prototype,"loading",void 0);Qt=xe([d("w3m-connect-recent-widget")],Qt);var ye=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Xt=class extends p{constructor(){super(),this.unsubscribe=[],this.tabIdx=void 0,this.wallets=[],this.loading=!1,f.isTelegram()&&f.isIos()&&(this.loading=!x.state.wcUri,this.unsubscribe.push(x.subscribeKey("wcUri",t=>this.loading=!t)))}render(){let{connectors:t}=v.state,{customWallets:e,featuredWalletIds:i}=N.state,n=pt.getRecentWallets(),o=t.find(R=>R.id==="walletConnect"),a=t.filter(R=>R.type==="INJECTED"||R.type==="ANNOUNCED"||R.type==="MULTI_CHAIN").filter(R=>R.name!=="Browser Wallet");if(!o)return null;if(i||e||!this.wallets.length)return this.style.cssText="display: none",null;let u=a.length+n.length,b=Math.max(0,2-u),w=ht.filterOutDuplicateWallets(this.wallets).slice(0,b);return w.length?l`
      <wui-flex flexDirection="column" gap="xs">
        ${w.map(R=>l`
            <wui-list-wallet
              imageSrc=${h(B.getWalletImage(R))}
              name=${R?.name??"Unknown"}
              @click=${()=>this.onConnectWallet(R)}
              tabIdx=${h(this.tabIdx)}
              ?loading=${this.loading}
            >
            </wui-list-wallet>
          `)}
      </wui-flex>
    `:(this.style.cssText="display: none",null)}onConnectWallet(t){if(this.loading)return;let e=v.getConnector(t.id,t.rdns);e?C.push("ConnectingExternal",{connector:e}):C.push("ConnectingWalletConnect",{wallet:t})}};ye([c()],Xt.prototype,"tabIdx",void 0);ye([c()],Xt.prototype,"wallets",void 0);ye([m()],Xt.prototype,"loading",void 0);Xt=ye([d("w3m-connect-recommended-widget")],Xt);var Ce=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Zt=class extends p{constructor(){super(),this.unsubscribe=[],this.tabIdx=void 0,this.connectors=v.state.connectors,this.connectorImages=He.state.connectorImages,this.unsubscribe.push(v.subscribeKey("connectors",t=>this.connectors=t),He.subscribeKey("connectorImages",t=>this.connectorImages=t))}disconnectedCallback(){this.unsubscribe.forEach(t=>t())}render(){if(f.isMobile())return this.style.cssText="display: none",null;let t=this.connectors.find(i=>i.id==="walletConnect");if(!t)return this.style.cssText="display: none",null;let e=t.imageUrl||this.connectorImages[t?.imageId??""];return l`
      <wui-list-wallet
        imageSrc=${h(e)}
        name=${t.name??"Unknown"}
        @click=${()=>this.onConnector(t)}
        tagLabel="qr code"
        tagVariant="main"
        tabIdx=${h(this.tabIdx)}
        data-testid="wallet-selector-walletconnect"
      >
      </wui-list-wallet>
    `}onConnector(t){v.setActiveConnector(t),C.push("ConnectingWalletConnect")}};Ce([c()],Zt.prototype,"tabIdx",void 0);Ce([m()],Zt.prototype,"connectors",void 0);Ce([m()],Zt.prototype,"connectorImages",void 0);Zt=Ce([d("w3m-connect-walletconnect-widget")],Zt);var Mo=g`
  :host {
    margin-top: var(--wui-spacing-3xs);
  }
  wui-separator {
    margin: var(--wui-spacing-m) calc(var(--wui-spacing-m) * -1) var(--wui-spacing-xs)
      calc(var(--wui-spacing-m) * -1);
    width: calc(100% + var(--wui-spacing-s) * 2);
  }
`;var te=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Rt=class extends p{constructor(){super(),this.unsubscribe=[],this.tabIdx=void 0,this.connectors=v.state.connectors,this.recommended=E.state.recommended,this.featured=E.state.featured,this.unsubscribe.push(v.subscribeKey("connectors",t=>this.connectors=t),E.subscribeKey("recommended",t=>this.recommended=t),E.subscribeKey("featured",t=>this.featured=t))}disconnectedCallback(){this.unsubscribe.forEach(t=>t())}render(){return l`
      <wui-flex flexDirection="column" gap="xs"> ${this.connectorListTemplate()} </wui-flex>
    `}connectorListTemplate(){let{custom:t,recent:e,announced:i,injected:n,multiChain:o,recommended:s,featured:a,external:u}=st.getConnectorsByType(this.connectors,this.recommended,this.featured);return st.getConnectorTypeOrder({custom:t,recent:e,announced:i,injected:n,multiChain:o,recommended:s,featured:a,external:u}).map(w=>{switch(w){case"injected":return l`
            ${o.length?l`<w3m-connect-multi-chain-widget
                  tabIdx=${h(this.tabIdx)}
                ></w3m-connect-multi-chain-widget>`:null}
            ${i.length?l`<w3m-connect-announced-widget
                  tabIdx=${h(this.tabIdx)}
                ></w3m-connect-announced-widget>`:null}
            ${n.length?l`<w3m-connect-injected-widget
                  .connectors=${n}
                  tabIdx=${h(this.tabIdx)}
                ></w3m-connect-injected-widget>`:null}
          `;case"walletConnect":return l`<w3m-connect-walletconnect-widget
            tabIdx=${h(this.tabIdx)}
          ></w3m-connect-walletconnect-widget>`;case"recent":return l`<w3m-connect-recent-widget
            tabIdx=${h(this.tabIdx)}
          ></w3m-connect-recent-widget>`;case"featured":return l`<w3m-connect-featured-widget
            .wallets=${a}
            tabIdx=${h(this.tabIdx)}
          ></w3m-connect-featured-widget>`;case"custom":return l`<w3m-connect-custom-widget
            tabIdx=${h(this.tabIdx)}
          ></w3m-connect-custom-widget>`;case"external":return l`<w3m-connect-external-widget
            tabIdx=${h(this.tabIdx)}
          ></w3m-connect-external-widget>`;case"recommended":return l`<w3m-connect-recommended-widget
            .wallets=${s}
            tabIdx=${h(this.tabIdx)}
          ></w3m-connect-recommended-widget>`;default:return console.warn(`Unknown connector type: ${w}`),null}})}};Rt.styles=Mo;te([c()],Rt.prototype,"tabIdx",void 0);te([m()],Rt.prototype,"connectors",void 0);te([m()],Rt.prototype,"recommended",void 0);te([m()],Rt.prototype,"featured",void 0);Rt=te([d("w3m-connector-list")],Rt);var qo=g`
  :host {
    display: inline-flex;
    background-color: var(--wui-color-gray-glass-002);
    border-radius: var(--wui-border-radius-3xl);
    padding: var(--wui-spacing-3xs);
    position: relative;
    height: 36px;
    min-height: 36px;
    overflow: hidden;
  }

  :host::before {
    content: '';
    position: absolute;
    pointer-events: none;
    top: 4px;
    left: 4px;
    display: block;
    width: var(--local-tab-width);
    height: 28px;
    border-radius: var(--wui-border-radius-3xl);
    background-color: var(--wui-color-gray-glass-002);
    box-shadow: inset 0 0 0 1px var(--wui-color-gray-glass-002);
    transform: translateX(calc(var(--local-tab) * var(--local-tab-width)));
    transition: transform var(--wui-ease-out-power-1) var(--wui-duration-md);
    will-change: background-color, opacity;
  }

  :host([data-type='flex'])::before {
    left: 3px;
    transform: translateX(calc((var(--local-tab) * 34px) + (var(--local-tab) * 4px)));
  }

  :host([data-type='flex']) {
    display: flex;
    padding: 0px 0px 0px 12px;
    gap: 4px;
  }

  :host([data-type='flex']) > button > wui-text {
    position: absolute;
    left: 18px;
    opacity: 0;
  }

  button[data-active='true'] > wui-icon,
  button[data-active='true'] > wui-text {
    color: var(--wui-color-fg-100);
  }

  button[data-active='false'] > wui-icon,
  button[data-active='false'] > wui-text {
    color: var(--wui-color-fg-200);
  }

  button[data-active='true']:disabled,
  button[data-active='false']:disabled {
    background-color: transparent;
    opacity: 0.5;
    cursor: not-allowed;
  }

  button[data-active='true']:disabled > wui-text {
    color: var(--wui-color-fg-200);
  }

  button[data-active='false']:disabled > wui-text {
    color: var(--wui-color-fg-300);
  }

  button > wui-icon,
  button > wui-text {
    pointer-events: none;
    transition: color var(--wui-e ase-out-power-1) var(--wui-duration-md);
    will-change: color;
  }

  button {
    width: var(--local-tab-width);
    transition: background-color var(--wui-ease-out-power-1) var(--wui-duration-md);
    will-change: background-color;
  }

  :host([data-type='flex']) > button {
    width: 34px;
    position: relative;
    display: flex;
    justify-content: flex-start;
  }

  button:hover:enabled,
  button:active:enabled {
    background-color: transparent !important;
  }

  button:hover:enabled > wui-icon,
  button:active:enabled > wui-icon {
    transition: all var(--wui-ease-out-power-1) var(--wui-duration-lg);
    color: var(--wui-color-fg-125);
  }

  button:hover:enabled > wui-text,
  button:active:enabled > wui-text {
    transition: all var(--wui-ease-out-power-1) var(--wui-duration-lg);
    color: var(--wui-color-fg-125);
  }

  button {
    border-radius: var(--wui-border-radius-3xl);
  }
`;var ft=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},et=class extends p{constructor(){super(...arguments),this.tabs=[],this.onTabChange=()=>null,this.buttons=[],this.disabled=!1,this.localTabWidth="100px",this.activeTab=0,this.isDense=!1}render(){return this.isDense=this.tabs.length>3,this.style.cssText=`
      --local-tab: ${this.activeTab};
      --local-tab-width: ${this.localTabWidth};
    `,this.dataset.type=this.isDense?"flex":"block",this.tabs.map((t,e)=>{let i=e===this.activeTab;return l`
        <button
          ?disabled=${this.disabled}
          @click=${()=>this.onTabClick(e)}
          data-active=${i}
          data-testid="tab-${t.label?.toLowerCase()}"
        >
          ${this.iconTemplate(t)}
          <wui-text variant="small-600" color="inherit"> ${t.label} </wui-text>
        </button>
      `})}firstUpdated(){this.shadowRoot&&this.isDense&&(this.buttons=[...this.shadowRoot.querySelectorAll("button")],setTimeout(()=>{this.animateTabs(0,!0)},0))}iconTemplate(t){return t.icon?l`<wui-icon size="xs" color="inherit" name=${t.icon}></wui-icon>`:null}onTabClick(t){this.buttons&&this.animateTabs(t,!1),this.activeTab=t,this.onTabChange(t)}animateTabs(t,e){let i=this.buttons[this.activeTab],n=this.buttons[t],o=i?.querySelector("wui-text"),s=n?.querySelector("wui-text"),a=n?.getBoundingClientRect(),u=s?.getBoundingClientRect();i&&o&&!e&&t!==this.activeTab&&(o.animate([{opacity:0}],{duration:50,easing:"ease",fill:"forwards"}),i.animate([{width:"34px"}],{duration:500,easing:"ease",fill:"forwards"})),n&&a&&u&&s&&(t!==this.activeTab||e)&&(this.localTabWidth=`${Math.round(a.width+u.width)+6}px`,n.animate([{width:`${a.width+u.width}px`}],{duration:e?0:500,fill:"forwards",easing:"ease"}),s.animate([{opacity:1}],{duration:e?0:125,delay:e?0:200,fill:"forwards",easing:"ease"}))}};et.styles=[y,_,qo];ft([c({type:Array})],et.prototype,"tabs",void 0);ft([c()],et.prototype,"onTabChange",void 0);ft([c({type:Array})],et.prototype,"buttons",void 0);ft([c({type:Boolean})],et.prototype,"disabled",void 0);ft([c()],et.prototype,"localTabWidth",void 0);ft([m()],et.prototype,"activeTab",void 0);ft([m()],et.prototype,"isDense",void 0);et=ft([d("wui-tabs")],et);var to=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Ee=class extends p{constructor(){super(...arguments),this.platformTabs=[],this.unsubscribe=[],this.platforms=[],this.onSelectPlatfrom=void 0}disconnectCallback(){this.unsubscribe.forEach(t=>t())}render(){let t=this.generateTabs();return l`
      <wui-flex justifyContent="center" .padding=${["0","0","l","0"]}>
        <wui-tabs .tabs=${t} .onTabChange=${this.onTabChange.bind(this)}></wui-tabs>
      </wui-flex>
    `}generateTabs(){let t=this.platforms.map(e=>e==="browser"?{label:"Browser",icon:"extension",platform:"browser"}:e==="mobile"?{label:"Mobile",icon:"mobile",platform:"mobile"}:e==="qrcode"?{label:"Mobile",icon:"mobile",platform:"qrcode"}:e==="web"?{label:"Webapp",icon:"browser",platform:"web"}:e==="desktop"?{label:"Desktop",icon:"desktop",platform:"desktop"}:{label:"Browser",icon:"extension",platform:"unsupported"});return this.platformTabs=t.map(({platform:e})=>e),t}onTabChange(t){let e=this.platformTabs[t];e&&this.onSelectPlatfrom?.(e)}};to([c({type:Array})],Ee.prototype,"platforms",void 0);to([c()],Ee.prototype,"onSelectPlatfrom",void 0);Ee=to([d("w3m-connecting-header")],Ee);var Fo=g`
  :host {
    width: var(--local-width);
    position: relative;
  }

  button {
    border: none;
    border-radius: var(--local-border-radius);
    width: var(--local-width);
    white-space: nowrap;
  }

  /* -- Sizes --------------------------------------------------- */
  button[data-size='md'] {
    padding: 8.2px var(--wui-spacing-l) 9px var(--wui-spacing-l);
    height: 36px;
  }

  button[data-size='md'][data-icon-left='true'][data-icon-right='false'] {
    padding: 8.2px var(--wui-spacing-l) 9px var(--wui-spacing-s);
  }

  button[data-size='md'][data-icon-right='true'][data-icon-left='false'] {
    padding: 8.2px var(--wui-spacing-s) 9px var(--wui-spacing-l);
  }

  button[data-size='lg'] {
    padding: var(--wui-spacing-m) var(--wui-spacing-2l);
    height: 48px;
  }

  /* -- Variants --------------------------------------------------------- */
  button[data-variant='main'] {
    background-color: var(--wui-color-accent-100);
    color: var(--wui-color-inverse-100);
    border: none;
    box-shadow: inset 0 0 0 1px var(--wui-color-gray-glass-010);
  }

  button[data-variant='inverse'] {
    background-color: var(--wui-color-inverse-100);
    color: var(--wui-color-inverse-000);
    border: none;
    box-shadow: inset 0 0 0 1px var(--wui-color-gray-glass-010);
  }

  button[data-variant='accent'] {
    background-color: var(--wui-color-accent-glass-010);
    color: var(--wui-color-accent-100);
    border: none;
    box-shadow: inset 0 0 0 1px var(--wui-color-gray-glass-005);
  }

  button[data-variant='accent-error'] {
    background: var(--wui-color-error-glass-015);
    color: var(--wui-color-error-100);
    border: none;
    box-shadow: inset 0 0 0 1px var(--wui-color-error-glass-010);
  }

  button[data-variant='accent-success'] {
    background: var(--wui-color-success-glass-015);
    color: var(--wui-color-success-100);
    border: none;
    box-shadow: inset 0 0 0 1px var(--wui-color-success-glass-010);
  }

  button[data-variant='neutral'] {
    background: transparent;
    color: var(--wui-color-fg-100);
    border: none;
    box-shadow: inset 0 0 0 1px var(--wui-color-gray-glass-005);
  }

  /* -- Focus states --------------------------------------------------- */
  button[data-variant='main']:focus-visible:enabled {
    background-color: var(--wui-color-accent-090);
    box-shadow:
      inset 0 0 0 1px var(--wui-color-accent-100),
      0 0 0 4px var(--wui-color-accent-glass-020);
  }
  button[data-variant='inverse']:focus-visible:enabled {
    background-color: var(--wui-color-inverse-100);
    box-shadow:
      inset 0 0 0 1px var(--wui-color-gray-glass-010),
      0 0 0 4px var(--wui-color-accent-glass-020);
  }
  button[data-variant='accent']:focus-visible:enabled {
    background-color: var(--wui-color-accent-glass-010);
    box-shadow:
      inset 0 0 0 1px var(--wui-color-accent-100),
      0 0 0 4px var(--wui-color-accent-glass-020);
  }
  button[data-variant='accent-error']:focus-visible:enabled {
    background: var(--wui-color-error-glass-015);
    box-shadow:
      inset 0 0 0 1px var(--wui-color-error-100),
      0 0 0 4px var(--wui-color-error-glass-020);
  }
  button[data-variant='accent-success']:focus-visible:enabled {
    background: var(--wui-color-success-glass-015);
    box-shadow:
      inset 0 0 0 1px var(--wui-color-success-100),
      0 0 0 4px var(--wui-color-success-glass-020);
  }
  button[data-variant='neutral']:focus-visible:enabled {
    background: var(--wui-color-gray-glass-005);
    box-shadow:
      inset 0 0 0 1px var(--wui-color-gray-glass-010),
      0 0 0 4px var(--wui-color-gray-glass-002);
  }

  /* -- Hover & Active states ----------------------------------------------------------- */
  @media (hover: hover) and (pointer: fine) {
    button[data-variant='main']:hover:enabled {
      background-color: var(--wui-color-accent-090);
    }

    button[data-variant='main']:active:enabled {
      background-color: var(--wui-color-accent-080);
    }

    button[data-variant='accent']:hover:enabled {
      background-color: var(--wui-color-accent-glass-015);
    }

    button[data-variant='accent']:active:enabled {
      background-color: var(--wui-color-accent-glass-020);
    }

    button[data-variant='accent-error']:hover:enabled {
      background: var(--wui-color-error-glass-020);
      color: var(--wui-color-error-100);
    }

    button[data-variant='accent-error']:active:enabled {
      background: var(--wui-color-error-glass-030);
      color: var(--wui-color-error-100);
    }

    button[data-variant='accent-success']:hover:enabled {
      background: var(--wui-color-success-glass-020);
      color: var(--wui-color-success-100);
    }

    button[data-variant='accent-success']:active:enabled {
      background: var(--wui-color-success-glass-030);
      color: var(--wui-color-success-100);
    }

    button[data-variant='neutral']:hover:enabled {
      background: var(--wui-color-gray-glass-002);
    }

    button[data-variant='neutral']:active:enabled {
      background: var(--wui-color-gray-glass-005);
    }

    button[data-size='lg'][data-icon-left='true'][data-icon-right='false'] {
      padding-left: var(--wui-spacing-m);
    }

    button[data-size='lg'][data-icon-right='true'][data-icon-left='false'] {
      padding-right: var(--wui-spacing-m);
    }
  }

  /* -- Disabled state --------------------------------------------------- */
  button:disabled {
    background-color: var(--wui-color-gray-glass-002);
    box-shadow: inset 0 0 0 1px var(--wui-color-gray-glass-002);
    color: var(--wui-color-gray-glass-020);
    cursor: not-allowed;
  }

  button > wui-text {
    transition: opacity var(--wui-ease-out-power-1) var(--wui-duration-md);
    will-change: opacity;
    opacity: var(--local-opacity-100);
  }

  ::slotted(*) {
    transition: opacity var(--wui-ease-out-power-1) var(--wui-duration-md);
    will-change: opacity;
    opacity: var(--local-opacity-100);
  }

  wui-loading-spinner {
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    opacity: var(--local-opacity-000);
  }
`;var ot=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Vo={main:"inverse-100",inverse:"inverse-000",accent:"accent-100","accent-error":"error-100","accent-success":"success-100",neutral:"fg-100",disabled:"gray-glass-020"},Ar={lg:"paragraph-600",md:"small-600"},Pr={lg:"md",md:"md"},G=class extends p{constructor(){super(...arguments),this.size="lg",this.disabled=!1,this.fullWidth=!1,this.loading=!1,this.variant="main",this.hasIconLeft=!1,this.hasIconRight=!1,this.borderRadius="m"}render(){this.style.cssText=`
    --local-width: ${this.fullWidth?"100%":"auto"};
    --local-opacity-100: ${this.loading?0:1};
    --local-opacity-000: ${this.loading?1:0};
    --local-border-radius: var(--wui-border-radius-${this.borderRadius});
    `;let t=this.textVariant??Ar[this.size];return l`
      <button
        data-variant=${this.variant}
        data-icon-left=${this.hasIconLeft}
        data-icon-right=${this.hasIconRight}
        data-size=${this.size}
        ?disabled=${this.disabled}
      >
        ${this.loadingTemplate()}
        <slot name="iconLeft" @slotchange=${()=>this.handleSlotLeftChange()}></slot>
        <wui-text variant=${t} color="inherit">
          <slot></slot>
        </wui-text>
        <slot name="iconRight" @slotchange=${()=>this.handleSlotRightChange()}></slot>
      </button>
    `}handleSlotLeftChange(){this.hasIconLeft=!0}handleSlotRightChange(){this.hasIconRight=!0}loadingTemplate(){if(this.loading){let t=Pr[this.size],e=this.disabled?Vo.disabled:Vo[this.variant];return l`<wui-loading-spinner color=${e} size=${t}></wui-loading-spinner>`}return l``}};G.styles=[y,_,Fo];ot([c()],G.prototype,"size",void 0);ot([c({type:Boolean})],G.prototype,"disabled",void 0);ot([c({type:Boolean})],G.prototype,"fullWidth",void 0);ot([c({type:Boolean})],G.prototype,"loading",void 0);ot([c()],G.prototype,"variant",void 0);ot([c({type:Boolean})],G.prototype,"hasIconLeft",void 0);ot([c({type:Boolean})],G.prototype,"hasIconRight",void 0);ot([c()],G.prototype,"borderRadius",void 0);ot([c()],G.prototype,"textVariant",void 0);G=ot([d("wui-button")],G);var Ho=g`
  button {
    padding: var(--wui-spacing-4xs) var(--wui-spacing-xxs);
    border-radius: var(--wui-border-radius-3xs);
    background-color: transparent;
    color: var(--wui-color-accent-100);
  }

  button:disabled {
    background-color: transparent;
    color: var(--wui-color-gray-glass-015);
  }

  button:hover {
    background-color: var(--wui-color-gray-glass-005);
  }
`;var Re=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Pt=class extends p{constructor(){super(...arguments),this.tabIdx=void 0,this.disabled=!1,this.color="inherit"}render(){return l`
      <button ?disabled=${this.disabled} tabindex=${h(this.tabIdx)}>
        <slot name="iconLeft"></slot>
        <wui-text variant="small-600" color=${this.color}>
          <slot></slot>
        </wui-text>
        <slot name="iconRight"></slot>
      </button>
    `}};Pt.styles=[y,_,Ho];Re([c()],Pt.prototype,"tabIdx",void 0);Re([c({type:Boolean})],Pt.prototype,"disabled",void 0);Re([c()],Pt.prototype,"color",void 0);Pt=Re([d("wui-link")],Pt);var Ko=g`
  :host {
    display: block;
    width: var(--wui-box-size-md);
    height: var(--wui-box-size-md);
  }

  svg {
    width: var(--wui-box-size-md);
    height: var(--wui-box-size-md);
  }

  rect {
    fill: none;
    stroke: var(--wui-color-accent-100);
    stroke-width: 4px;
    stroke-linecap: round;
    animation: dash 1s linear infinite;
  }

  @keyframes dash {
    to {
      stroke-dashoffset: 0px;
    }
  }
`;var Go=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},$e=class extends p{constructor(){super(...arguments),this.radius=36}render(){return this.svgLoaderTemplate()}svgLoaderTemplate(){let t=this.radius>50?50:this.radius,i=36-t,n=116+i,o=245+i,s=360+i*1.75;return l`
      <svg viewBox="0 0 110 110" width="110" height="110">
        <rect
          x="2"
          y="2"
          width="106"
          height="106"
          rx=${t}
          stroke-dasharray="${n} ${o}"
          stroke-dashoffset=${s}
        />
      </svg>
    `}};$e.styles=[y,Ko];Go([c({type:Number})],$e.prototype,"radius",void 0);$e=Go([d("wui-loading-thumbnail")],$e);var Yo=g`
  button {
    border: none;
    border-radius: var(--wui-border-radius-3xl);
  }

  button[data-variant='main'] {
    background-color: var(--wui-color-accent-100);
    color: var(--wui-color-inverse-100);
    box-shadow: inset 0 0 0 1px var(--wui-color-gray-glass-010);
  }

  button[data-variant='accent'] {
    background-color: var(--wui-color-accent-glass-010);
    color: var(--wui-color-accent-100);
    box-shadow: inset 0 0 0 1px var(--wui-color-gray-glass-005);
  }

  button[data-variant='gray'] {
    background-color: transparent;
    color: var(--wui-color-fg-200);
    box-shadow: inset 0 0 0 1px var(--wui-color-gray-glass-010);
  }

  button[data-variant='shade'] {
    background-color: transparent;
    color: var(--wui-color-accent-100);
    box-shadow: inset 0 0 0 1px var(--wui-color-gray-glass-010);
  }

  button[data-size='sm'] {
    height: 32px;
    padding: 0 var(--wui-spacing-s);
  }

  button[data-size='md'] {
    height: 40px;
    padding: 0 var(--wui-spacing-l);
  }

  button[data-size='sm'] > wui-image {
    width: 16px;
    height: 16px;
  }

  button[data-size='md'] > wui-image {
    width: 24px;
    height: 24px;
  }

  button[data-size='sm'] > wui-icon {
    width: 12px;
    height: 12px;
  }

  button[data-size='md'] > wui-icon {
    width: 14px;
    height: 14px;
  }

  wui-image {
    border-radius: var(--wui-border-radius-3xl);
    overflow: hidden;
  }

  button.disabled > wui-icon,
  button.disabled > wui-image {
    filter: grayscale(1);
  }

  button[data-variant='main'] > wui-image {
    box-shadow: inset 0 0 0 1px var(--wui-color-accent-090);
  }

  button[data-variant='shade'] > wui-image,
  button[data-variant='gray'] > wui-image {
    box-shadow: inset 0 0 0 1px var(--wui-color-gray-glass-010);
  }

  @media (hover: hover) and (pointer: fine) {
    button[data-variant='main']:focus-visible {
      background-color: var(--wui-color-accent-090);
    }

    button[data-variant='main']:hover:enabled {
      background-color: var(--wui-color-accent-090);
    }

    button[data-variant='main']:active:enabled {
      background-color: var(--wui-color-accent-080);
    }

    button[data-variant='accent']:hover:enabled {
      background-color: var(--wui-color-accent-glass-015);
    }

    button[data-variant='accent']:active:enabled {
      background-color: var(--wui-color-accent-glass-020);
    }

    button[data-variant='shade']:focus-visible,
    button[data-variant='gray']:focus-visible,
    button[data-variant='shade']:hover,
    button[data-variant='gray']:hover {
      background-color: var(--wui-color-gray-glass-002);
    }

    button[data-variant='gray']:active,
    button[data-variant='shade']:active {
      background-color: var(--wui-color-gray-glass-005);
    }
  }

  button.disabled {
    color: var(--wui-color-gray-glass-020);
    background-color: var(--wui-color-gray-glass-002);
    box-shadow: inset 0 0 0 1px var(--wui-color-gray-glass-002);
    pointer-events: none;
  }
`;var $t=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},lt=class extends p{constructor(){super(...arguments),this.variant="accent",this.imageSrc="",this.disabled=!1,this.icon="externalLink",this.size="md",this.text=""}render(){let t=this.size==="sm"?"small-600":"paragraph-600";return l`
      <button
        class=${this.disabled?"disabled":""}
        data-variant=${this.variant}
        data-size=${this.size}
      >
        ${this.imageSrc?l`<wui-image src=${this.imageSrc}></wui-image>`:null}
        <wui-text variant=${t} color="inherit"> ${this.text} </wui-text>
        <wui-icon name=${this.icon} color="inherit" size="inherit"></wui-icon>
      </button>
    `}};lt.styles=[y,_,Yo];$t([c()],lt.prototype,"variant",void 0);$t([c()],lt.prototype,"imageSrc",void 0);$t([c({type:Boolean})],lt.prototype,"disabled",void 0);$t([c()],lt.prototype,"icon",void 0);$t([c()],lt.prototype,"size",void 0);$t([c()],lt.prototype,"text",void 0);lt=$t([d("wui-chip-button")],lt);var Jo=g`
  wui-flex {
    width: 100%;
    background-color: var(--wui-color-gray-glass-002);
    border-radius: var(--wui-border-radius-xs);
  }
`;var Ie=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Dt=class extends p{constructor(){super(...arguments),this.disabled=!1,this.label="",this.buttonLabel=""}render(){return l`
      <wui-flex
        justifyContent="space-between"
        alignItems="center"
        .padding=${["1xs","2l","1xs","2l"]}
      >
        <wui-text variant="paragraph-500" color="fg-200">${this.label}</wui-text>
        <wui-chip-button size="sm" variant="shade" text=${this.buttonLabel} icon="chevronRight">
        </wui-chip-button>
      </wui-flex>
    `}};Dt.styles=[y,_,Jo];Ie([c({type:Boolean})],Dt.prototype,"disabled",void 0);Ie([c()],Dt.prototype,"label",void 0);Ie([c()],Dt.prototype,"buttonLabel",void 0);Dt=Ie([d("wui-cta-button")],Dt);var Qo=g`
  :host {
    display: block;
    padding: 0 var(--wui-spacing-xl) var(--wui-spacing-xl);
  }
`;var Xo=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},We=class extends p{constructor(){super(...arguments),this.wallet=void 0}render(){if(!this.wallet)return this.style.display="none",null;let{name:t,app_store:e,play_store:i,chrome_store:n,homepage:o}=this.wallet,s=f.isMobile(),a=f.isIos(),u=f.isAndroid(),b=[e,i,o,n].filter(Boolean).length>1,w=X.getTruncateString({string:t,charsStart:12,charsEnd:0,truncate:"end"});return b&&!s?l`
        <wui-cta-button
          label=${`Don't have ${w}?`}
          buttonLabel="Get"
          @click=${()=>C.push("Downloads",{wallet:this.wallet})}
        ></wui-cta-button>
      `:!b&&o?l`
        <wui-cta-button
          label=${`Don't have ${w}?`}
          buttonLabel="Get"
          @click=${this.onHomePage.bind(this)}
        ></wui-cta-button>
      `:e&&a?l`
        <wui-cta-button
          label=${`Don't have ${w}?`}
          buttonLabel="Get"
          @click=${this.onAppStore.bind(this)}
        ></wui-cta-button>
      `:i&&u?l`
        <wui-cta-button
          label=${`Don't have ${w}?`}
          buttonLabel="Get"
          @click=${this.onPlayStore.bind(this)}
        ></wui-cta-button>
      `:(this.style.display="none",null)}onAppStore(){this.wallet?.app_store&&f.openHref(this.wallet.app_store,"_blank")}onPlayStore(){this.wallet?.play_store&&f.openHref(this.wallet.play_store,"_blank")}onHomePage(){this.wallet?.homepage&&f.openHref(this.wallet.homepage,"_blank")}};We.styles=[Qo];Xo([c({type:Object})],We.prototype,"wallet",void 0);We=Xo([d("w3m-mobile-download-links")],We);var Zo=g`
  @keyframes shake {
    0% {
      transform: translateX(0);
    }
    25% {
      transform: translateX(3px);
    }
    50% {
      transform: translateX(-3px);
    }
    75% {
      transform: translateX(3px);
    }
    100% {
      transform: translateX(0);
    }
  }

  wui-flex:first-child:not(:only-child) {
    position: relative;
  }

  wui-loading-thumbnail {
    position: absolute;
  }

  wui-icon-box {
    position: absolute;
    right: calc(var(--wui-spacing-3xs) * -1);
    bottom: calc(var(--wui-spacing-3xs) * -1);
    opacity: 0;
    transform: scale(0.5);
    transition-property: opacity, transform;
    transition-duration: var(--wui-duration-lg);
    transition-timing-function: var(--wui-ease-out-power-2);
    will-change: opacity, transform;
  }

  wui-text[align='center'] {
    width: 100%;
    padding: 0px var(--wui-spacing-l);
  }

  [data-error='true'] wui-icon-box {
    opacity: 1;
    transform: scale(1);
  }

  [data-error='true'] > wui-flex:first-child {
    animation: shake 250ms cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
  }

  [data-retry='false'] wui-link {
    display: none;
  }

  [data-retry='true'] wui-link {
    display: block;
    opacity: 1;
  }
`;var it=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},A=class extends p{constructor(){super(),this.wallet=C.state.data?.wallet,this.connector=C.state.data?.connector,this.timeout=void 0,this.secondaryBtnIcon="refresh",this.onConnect=void 0,this.onRender=void 0,this.onAutoConnect=void 0,this.isWalletConnect=!0,this.unsubscribe=[],this.imageSrc=B.getWalletImage(this.wallet)??B.getConnectorImage(this.connector),this.name=this.wallet?.name??this.connector?.name??"Wallet",this.isRetrying=!1,this.uri=x.state.wcUri,this.error=x.state.wcError,this.ready=!1,this.showRetry=!1,this.secondaryBtnLabel="Try again",this.secondaryLabel="Accept connection request in the wallet",this.isLoading=!1,this.isMobile=!1,this.onRetry=void 0,this.unsubscribe.push(x.subscribeKey("wcUri",t=>{this.uri=t,this.isRetrying&&this.onRetry&&(this.isRetrying=!1,this.onConnect?.())}),x.subscribeKey("wcError",t=>this.error=t)),(f.isTelegram()||f.isSafari())&&f.isIos()&&x.state.wcUri&&this.onConnect?.()}firstUpdated(){this.onAutoConnect?.(),this.showRetry=!this.onAutoConnect}disconnectedCallback(){this.unsubscribe.forEach(t=>t()),x.setWcError(!1),clearTimeout(this.timeout)}render(){this.onRender?.(),this.onShowRetry();let t=this.error?"Connection can be declined if a previous request is still active":this.secondaryLabel,e=`Continue in ${this.name}`;return this.error&&(e="Connection declined"),l`
      <wui-flex
        data-error=${h(this.error)}
        data-retry=${this.showRetry}
        flexDirection="column"
        alignItems="center"
        .padding=${["3xl","xl","xl","xl"]}
        gap="xl"
      >
        <wui-flex justifyContent="center" alignItems="center">
          <wui-wallet-image size="lg" imageSrc=${h(this.imageSrc)}></wui-wallet-image>

          ${this.error?null:this.loaderTemplate()}

          <wui-icon-box
            backgroundColor="error-100"
            background="opaque"
            iconColor="error-100"
            icon="close"
            size="sm"
            border
            borderColor="wui-color-bg-125"
          ></wui-icon-box>
        </wui-flex>

        <wui-flex flexDirection="column" alignItems="center" gap="xs">
          <wui-text variant="paragraph-500" color=${this.error?"error-100":"fg-100"}>
            ${e}
          </wui-text>
          <wui-text align="center" variant="small-500" color="fg-200">${t}</wui-text>
        </wui-flex>

        ${this.secondaryBtnLabel?l`
              <wui-button
                variant="accent"
                size="md"
                ?disabled=${this.isRetrying||this.isLoading}
                @click=${this.onTryAgain.bind(this)}
                data-testid="w3m-connecting-widget-secondary-button"
              >
                <wui-icon color="inherit" slot="iconLeft" name=${this.secondaryBtnIcon}></wui-icon>
                ${this.secondaryBtnLabel}
              </wui-button>
            `:null}
      </wui-flex>

      ${this.isWalletConnect?l`
            <wui-flex .padding=${["0","xl","xl","xl"]} justifyContent="center">
              <wui-link @click=${this.onCopyUri} color="fg-200" data-testid="wui-link-copy">
                <wui-icon size="xs" color="fg-200" slot="iconLeft" name="copy"></wui-icon>
                Copy link
              </wui-link>
            </wui-flex>
          `:null}

      <w3m-mobile-download-links .wallet=${this.wallet}></w3m-mobile-download-links>
    `}onShowRetry(){this.error&&!this.showRetry&&(this.showRetry=!0,this.shadowRoot?.querySelector("wui-button")?.animate([{opacity:0},{opacity:1}],{fill:"forwards",easing:"ease"}))}onTryAgain(){x.setWcError(!1),this.onRetry?(this.isRetrying=!0,this.onRetry?.()):this.onConnect?.()}loaderTemplate(){let t=Gt.state.themeVariables["--w3m-border-radius-master"],e=t?parseInt(t.replace("px",""),10):4;return l`<wui-loading-thumbnail radius=${e*9}></wui-loading-thumbnail>`}onCopyUri(){try{this.uri&&(f.copyToClopboard(this.uri),yt.showSuccess("Link copied"))}catch{yt.showError("Failed to copy")}}};A.styles=Zo;it([m()],A.prototype,"isRetrying",void 0);it([m()],A.prototype,"uri",void 0);it([m()],A.prototype,"error",void 0);it([m()],A.prototype,"ready",void 0);it([m()],A.prototype,"showRetry",void 0);it([m()],A.prototype,"secondaryBtnLabel",void 0);it([m()],A.prototype,"secondaryLabel",void 0);it([m()],A.prototype,"isLoading",void 0);it([c({type:Boolean})],A.prototype,"isMobile",void 0);it([c()],A.prototype,"onRetry",void 0);var Dr=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},ti=class extends A{constructor(){if(super(),!this.wallet)throw new Error("w3m-connecting-wc-browser: No wallet provided");this.onConnect=this.onConnectProxy.bind(this),this.onAutoConnect=this.onConnectProxy.bind(this),U.sendEvent({type:"track",event:"SELECT_WALLET",properties:{name:this.wallet.name,platform:"browser"}})}async onConnectProxy(){try{this.error=!1;let{connectors:t}=v.state,e=t.find(i=>i.type==="ANNOUNCED"&&i.info?.rdns===this.wallet?.rdns||i.type==="INJECTED"||i.name===this.wallet?.name);if(e)await x.connectExternal(e,e.chain);else throw new Error("w3m-connecting-wc-browser: No connector found");pe.close(),U.sendEvent({type:"track",event:"CONNECT_SUCCESS",properties:{method:"browser",name:this.wallet?.name||"Unknown"}})}catch(t){U.sendEvent({type:"track",event:"CONNECT_ERROR",properties:{message:t?.message??"Unknown"}}),this.error=!0}}};ti=Dr([d("w3m-connecting-wc-browser")],ti);var jr=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},ei=class extends A{constructor(){if(super(),!this.wallet)throw new Error("w3m-connecting-wc-desktop: No wallet provided");this.onConnect=this.onConnectProxy.bind(this),this.onRender=this.onRenderProxy.bind(this),U.sendEvent({type:"track",event:"SELECT_WALLET",properties:{name:this.wallet.name,platform:"desktop"}})}onRenderProxy(){!this.ready&&this.uri&&(this.ready=!0,this.onConnect?.())}onConnectProxy(){if(this.wallet?.desktop_link&&this.uri)try{this.error=!1;let{desktop_link:t,name:e}=this.wallet,{redirect:i,href:n}=f.formatNativeUrl(t,this.uri);x.setWcLinking({name:e,href:n}),x.setRecentWallet(this.wallet),f.openHref(i,"_blank")}catch{this.error=!0}}};ei=jr([d("w3m-connecting-wc-desktop")],ei);var jt=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},It=class extends A{constructor(){if(super(),this.btnLabelTimeout=void 0,this.redirectDeeplink=void 0,this.redirectUniversalLink=void 0,this.target=void 0,this.preferUniversalLinks=N.state.experimental_preferUniversalLinks,this.isLoading=!0,this.onConnect=()=>{if(this.wallet?.mobile_link&&this.uri)try{this.error=!1;let{mobile_link:t,link_mode:e,name:i}=this.wallet,{redirect:n,redirectUniversalLink:o,href:s}=f.formatNativeUrl(t,this.uri,e);this.redirectDeeplink=n,this.redirectUniversalLink=o,this.target=f.isIframe()?"_top":"_self",x.setWcLinking({name:i,href:s}),x.setRecentWallet(this.wallet),this.preferUniversalLinks&&this.redirectUniversalLink?f.openHref(this.redirectUniversalLink,this.target):f.openHref(this.redirectDeeplink,this.target)}catch(t){U.sendEvent({type:"track",event:"CONNECT_PROXY_ERROR",properties:{message:t instanceof Error?t.message:"Error parsing the deeplink",uri:this.uri,mobile_link:this.wallet.mobile_link,name:this.wallet.name}}),this.error=!0}},!this.wallet)throw new Error("w3m-connecting-wc-mobile: No wallet provided");this.secondaryBtnLabel="Open",this.secondaryLabel=de.CONNECT_LABELS.MOBILE,this.secondaryBtnIcon="externalLink",this.onHandleURI(),this.unsubscribe.push(x.subscribeKey("wcUri",()=>{this.onHandleURI()})),U.sendEvent({type:"track",event:"SELECT_WALLET",properties:{name:this.wallet.name,platform:"mobile"}})}disconnectedCallback(){super.disconnectedCallback(),clearTimeout(this.btnLabelTimeout)}onHandleURI(){this.isLoading=!this.uri,!this.ready&&this.uri&&(this.ready=!0,this.onConnect?.())}onTryAgain(){x.setWcError(!1),this.onConnect?.()}};jt([m()],It.prototype,"redirectDeeplink",void 0);jt([m()],It.prototype,"redirectUniversalLink",void 0);jt([m()],It.prototype,"target",void 0);jt([m()],It.prototype,"preferUniversalLinks",void 0);jt([m()],It.prototype,"isLoading",void 0);It=jt([d("w3m-connecting-wc-mobile")],It);var rr=Br(or(),1);var On=.1,ir=2.5,ut=7;function Ro(r,t,e){return r===t?!1:(r-t<0?t-r:r-t)<=e+On}function An(r,t){let e=Array.prototype.slice.call(rr.default.create(r,{errorCorrectionLevel:t}).modules.data,0),i=Math.sqrt(e.length);return e.reduce((n,o,s)=>(s%i===0?n.push([o]):n[n.length-1].push(o))&&n,[])}var nr={generate({uri:r,size:t,logoSize:e,dotColor:i="#141414"}){let n="transparent",s=[],a=An(r,"Q"),u=t/a.length,b=[{x:0,y:0},{x:1,y:0},{x:0,y:1}];b.forEach(({x:L,y:$})=>{let k=(a.length-ut)*u*L,W=(a.length-ut)*u*$,z=.45;for(let P=0;P<b.length;P+=1){let D=u*(ut-P*2);s.push(mt`
            <rect
              fill=${P===2?i:n}
              width=${P===0?D-5:D}
              rx= ${P===0?(D-5)*z:D*z}
              ry= ${P===0?(D-5)*z:D*z}
              stroke=${i}
              stroke-width=${P===0?5:0}
              height=${P===0?D-5:D}
              x= ${P===0?W+u*P+5/2:W+u*P}
              y= ${P===0?k+u*P+5/2:k+u*P}
            />
          `)}});let w=Math.floor((e+25)/u),R=a.length/2-w/2,T=a.length/2+w/2-1,K=[];a.forEach((L,$)=>{L.forEach((k,W)=>{if(a[$][W]&&!($<ut&&W<ut||$>a.length-(ut+1)&&W<ut||$<ut&&W>a.length-(ut+1))&&!($>R&&$<T&&W>R&&W<T)){let z=$*u+u/2,P=W*u+u/2;K.push([z,P])}})});let V={};return K.forEach(([L,$])=>{V[L]?V[L]?.push($):V[L]=[$]}),Object.entries(V).map(([L,$])=>{let k=$.filter(W=>$.every(z=>!Ro(W,z,u)));return[Number(L),k]}).forEach(([L,$])=>{$.forEach(k=>{s.push(mt`<circle cx=${L} cy=${k} fill=${i} r=${u/ir} />`)})}),Object.entries(V).filter(([L,$])=>$.length>1).map(([L,$])=>{let k=$.filter(W=>$.some(z=>Ro(W,z,u)));return[Number(L),k]}).map(([L,$])=>{$.sort((W,z)=>W<z?-1:1);let k=[];for(let W of $){let z=k.find(P=>P.some(D=>Ro(W,D,u)));z?z.push(W):k.push([W])}return[L,k.map(W=>[W[0],W[W.length-1]])]}).forEach(([L,$])=>{$.forEach(([k,W])=>{s.push(mt`
              <line
                x1=${L}
                x2=${L}
                y1=${k}
                y2=${W}
                stroke=${i}
                stroke-width=${u/(ir/2)}
                stroke-linecap="round"
              />
            `)})}),s}};var sr=g`
  :host {
    position: relative;
    user-select: none;
    display: block;
    overflow: hidden;
    aspect-ratio: 1 / 1;
    width: var(--local-size);
  }

  :host([data-theme='dark']) {
    border-radius: clamp(0px, var(--wui-border-radius-l), 40px);
    background-color: var(--wui-color-inverse-100);
    padding: var(--wui-spacing-l);
  }

  :host([data-theme='light']) {
    box-shadow: 0 0 0 1px var(--wui-color-bg-125);
    background-color: var(--wui-color-bg-125);
  }

  :host([data-clear='true']) > wui-icon {
    display: none;
  }

  svg:first-child,
  wui-image,
  wui-icon {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translateY(-50%) translateX(-50%);
  }

  wui-image {
    width: 25%;
    height: 25%;
    border-radius: var(--wui-border-radius-xs);
  }

  wui-icon {
    width: 100%;
    height: 100%;
    color: var(--local-icon-color) !important;
    transform: translateY(-50%) translateX(-50%) scale(0.25);
  }
`;var dt=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Pn="#3396ff",Z=class extends p{constructor(){super(...arguments),this.uri="",this.size=0,this.theme="dark",this.imageSrc=void 0,this.alt=void 0,this.arenaClear=void 0,this.farcaster=void 0}render(){return this.dataset.theme=this.theme,this.dataset.clear=String(this.arenaClear),this.style.cssText=`
     --local-size: ${this.size}px;
     --local-icon-color: ${this.color??Pn}
    `,l`${this.templateVisual()} ${this.templateSvg()}`}templateSvg(){let t=this.theme==="light"?this.size:this.size-32;return mt`
      <svg height=${t} width=${t}>
        ${nr.generate({uri:this.uri,size:t,logoSize:this.arenaClear?0:t/4,dotColor:this.color})}
      </svg>
    `}templateVisual(){return this.imageSrc?l`<wui-image src=${this.imageSrc} alt=${this.alt??"logo"}></wui-image>`:this.farcaster?l`<wui-icon
        class="farcaster"
        size="inherit"
        color="inherit"
        name="farcaster"
      ></wui-icon>`:l`<wui-icon size="inherit" color="inherit" name="walletConnect"></wui-icon>`}};Z.styles=[y,sr];dt([c()],Z.prototype,"uri",void 0);dt([c({type:Number})],Z.prototype,"size",void 0);dt([c()],Z.prototype,"theme",void 0);dt([c()],Z.prototype,"imageSrc",void 0);dt([c()],Z.prototype,"alt",void 0);dt([c()],Z.prototype,"color",void 0);dt([c({type:Boolean})],Z.prototype,"arenaClear",void 0);dt([c({type:Boolean})],Z.prototype,"farcaster",void 0);Z=dt([d("wui-qr-code")],Z);var ar=g`
  :host {
    display: block;
    box-shadow: inset 0 0 0 1px var(--wui-color-gray-glass-005);
    background: linear-gradient(
      120deg,
      var(--wui-color-bg-200) 5%,
      var(--wui-color-bg-200) 48%,
      var(--wui-color-bg-300) 55%,
      var(--wui-color-bg-300) 60%,
      var(--wui-color-bg-300) calc(60% + 10px),
      var(--wui-color-bg-200) calc(60% + 12px),
      var(--wui-color-bg-200) 100%
    );
    background-size: 250%;
    animation: shimmer 3s linear infinite reverse;
  }

  :host([variant='light']) {
    background: linear-gradient(
      120deg,
      var(--wui-color-bg-150) 5%,
      var(--wui-color-bg-150) 48%,
      var(--wui-color-bg-200) 55%,
      var(--wui-color-bg-200) 60%,
      var(--wui-color-bg-200) calc(60% + 10px),
      var(--wui-color-bg-150) calc(60% + 12px),
      var(--wui-color-bg-150) 100%
    );
    background-size: 250%;
  }

  @keyframes shimmer {
    from {
      background-position: -250% 0;
    }
    to {
      background-position: 250% 0;
    }
  }
`;var le=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Lt=class extends p{constructor(){super(...arguments),this.width="",this.height="",this.borderRadius="m",this.variant="default"}render(){return this.style.cssText=`
      width: ${this.width};
      height: ${this.height};
      border-radius: ${`clamp(0px,var(--wui-border-radius-${this.borderRadius}), 40px)`};
    `,l`<slot></slot>`}};Lt.styles=[ar];le([c()],Lt.prototype,"width",void 0);le([c()],Lt.prototype,"height",void 0);le([c()],Lt.prototype,"borderRadius",void 0);le([c()],Lt.prototype,"variant",void 0);Lt=le([d("wui-shimmer")],Lt);var lr="https://reown.com";var cr=g`
  .reown-logo {
    height: var(--wui-spacing-xxl);
  }

  a {
    text-decoration: none;
    cursor: pointer;
  }

  a:hover {
    opacity: 0.9;
  }
`;var Dn=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},$o=class extends p{render(){return l`
      <a
        data-testid="ux-branding-reown"
        href=${lr}
        rel="noreferrer"
        target="_blank"
        style="text-decoration: none;"
      >
        <wui-flex
          justifyContent="center"
          alignItems="center"
          gap="xs"
          .padding=${["0","0","l","0"]}
        >
          <wui-text variant="small-500" color="fg-100"> UX by </wui-text>
          <wui-icon name="reown" size="xxxl" class="reown-logo"></wui-icon>
        </wui-flex>
      </a>
    `}};$o.styles=[y,_,cr];$o=Dn([d("wui-ux-by-reown")],$o);var ur=g`
  @keyframes fadein {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  wui-shimmer {
    width: 100%;
    aspect-ratio: 1 / 1;
    border-radius: clamp(0px, var(--wui-border-radius-l), 40px) !important;
  }

  wui-qr-code {
    opacity: 0;
    animation-duration: 200ms;
    animation-timing-function: ease;
    animation-name: fadein;
    animation-fill-mode: forwards;
  }
`;var jn=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Io=class extends A{constructor(){super(),this.forceUpdate=()=>{this.requestUpdate()},window.addEventListener("resize",this.forceUpdate),U.sendEvent({type:"track",event:"SELECT_WALLET",properties:{name:this.wallet?.name??"WalletConnect",platform:"qrcode"}})}disconnectedCallback(){super.disconnectedCallback(),this.unsubscribe?.forEach(t=>t()),window.removeEventListener("resize",this.forceUpdate)}render(){return this.onRenderProxy(),l`
      <wui-flex
        flexDirection="column"
        alignItems="center"
        .padding=${["0","xl","xl","xl"]}
        gap="xl"
      >
        <wui-shimmer borderRadius="l" width="100%"> ${this.qrCodeTemplate()} </wui-shimmer>

        <wui-text variant="paragraph-500" color="fg-100">
          Scan this QR Code with your phone
        </wui-text>
        ${this.copyTemplate()}
      </wui-flex>
      <w3m-mobile-download-links .wallet=${this.wallet}></w3m-mobile-download-links>
    `}onRenderProxy(){!this.ready&&this.uri&&(this.timeout=setTimeout(()=>{this.ready=!0},200))}qrCodeTemplate(){if(!this.uri||!this.ready)return null;let t=this.getBoundingClientRect().width-40,e=this.wallet?this.wallet.name:void 0;return x.setWcLinking(void 0),x.setRecentWallet(this.wallet),l` <wui-qr-code
      size=${t}
      theme=${Gt.state.themeMode}
      uri=${this.uri}
      imageSrc=${h(B.getWalletImage(this.wallet))}
      color=${h(Gt.state.themeVariables["--w3m-qr-color"])}
      alt=${h(e)}
      data-testid="wui-qr-code"
    ></wui-qr-code>`}copyTemplate(){let t=!this.uri||!this.ready;return l`<wui-link
      .disabled=${t}
      @click=${this.onCopyUri}
      color="fg-200"
      data-testid="copy-wc2-uri"
    >
      <wui-icon size="xs" color="fg-200" slot="iconLeft" name="copy"></wui-icon>
      Copy link
    </wui-link>`}};Io.styles=ur;Io=jn([d("w3m-connecting-wc-qrcode")],Io);var kn=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},dr=class extends p{constructor(){if(super(),this.wallet=C.state.data?.wallet,!this.wallet)throw new Error("w3m-connecting-wc-unsupported: No wallet provided");U.sendEvent({type:"track",event:"SELECT_WALLET",properties:{name:this.wallet.name,platform:"browser"}})}render(){return l`
      <wui-flex
        flexDirection="column"
        alignItems="center"
        .padding=${["3xl","xl","xl","xl"]}
        gap="xl"
      >
        <wui-wallet-image
          size="lg"
          imageSrc=${h(B.getWalletImage(this.wallet))}
        ></wui-wallet-image>

        <wui-text variant="paragraph-500" color="fg-100">Not Detected</wui-text>
      </wui-flex>

      <w3m-mobile-download-links .wallet=${this.wallet}></w3m-mobile-download-links>
    `}};dr=kn([d("w3m-connecting-wc-unsupported")],dr);var pr=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Wo=class extends A{constructor(){if(super(),this.isLoading=!0,!this.wallet)throw new Error("w3m-connecting-wc-web: No wallet provided");this.onConnect=this.onConnectProxy.bind(this),this.secondaryBtnLabel="Open",this.secondaryLabel=de.CONNECT_LABELS.MOBILE,this.secondaryBtnIcon="externalLink",this.updateLoadingState(),this.unsubscribe.push(x.subscribeKey("wcUri",()=>{this.updateLoadingState()})),U.sendEvent({type:"track",event:"SELECT_WALLET",properties:{name:this.wallet.name,platform:"web"}})}updateLoadingState(){this.isLoading=!this.uri}onConnectProxy(){if(this.wallet?.webapp_link&&this.uri)try{this.error=!1;let{webapp_link:t,name:e}=this.wallet,{redirect:i,href:n}=f.formatUniversalUrl(t,this.uri);x.setWcLinking({name:e,href:n}),x.setRecentWallet(this.wallet),f.openHref(i,"_blank")}catch{this.error=!0}}};pr([m()],Wo.prototype,"isLoading",void 0);Wo=pr([d("w3m-connecting-wc-web")],Wo);var ce=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},qt=class extends p{constructor(){super(),this.wallet=C.state.data?.wallet,this.unsubscribe=[],this.platform=void 0,this.platforms=[],this.isSiwxEnabled=!!N.state.siwx,this.remoteFeatures=N.state.remoteFeatures,this.determinePlatforms(),this.initializeConnection(),this.unsubscribe.push(N.subscribeKey("remoteFeatures",t=>this.remoteFeatures=t))}disconnectedCallback(){this.unsubscribe.forEach(t=>t())}render(){return l`
      ${this.headerTemplate()}
      <div>${this.platformTemplate()}</div>
      ${this.reownBrandingTemplate()}
    `}reownBrandingTemplate(){return this.remoteFeatures?.reownBranding?l`<wui-ux-by-reown></wui-ux-by-reown>`:null}async initializeConnection(t=!1){if(!(this.platform==="browser"||N.state.manualWCControl&&!t))try{let{wcPairingExpiry:e,status:i}=x.state;(t||N.state.enableEmbedded||f.isPairingExpired(e)||i==="connecting")&&(await x.connectWalletConnect(),this.isSiwxEnabled||pe.close())}catch(e){U.sendEvent({type:"track",event:"CONNECT_ERROR",properties:{message:e?.message??"Unknown"}}),x.setWcError(!0),yt.showError(e.message??"Connection error"),x.resetWcConnection(),C.goBack()}}determinePlatforms(){if(!this.wallet){this.platforms.push("qrcode"),this.platform="qrcode";return}if(this.platform)return;let{mobile_link:t,desktop_link:e,webapp_link:i,injected:n,rdns:o}=this.wallet,s=n?.map(({injected_id:V})=>V).filter(Boolean),a=[...o?[o]:s??[]],u=N.state.isUniversalProvider?!1:a.length,b=t,w=i,R=x.checkInstalled(a),T=u&&R,K=e&&!f.isMobile();T&&!Yt.state.noAdapters&&this.platforms.push("browser"),b&&this.platforms.push(f.isMobile()?"mobile":"qrcode"),w&&this.platforms.push("web"),K&&this.platforms.push("desktop"),!T&&u&&!Yt.state.noAdapters&&this.platforms.push("unsupported"),this.platform=this.platforms[0]}platformTemplate(){switch(this.platform){case"browser":return l`<w3m-connecting-wc-browser></w3m-connecting-wc-browser>`;case"web":return l`<w3m-connecting-wc-web></w3m-connecting-wc-web>`;case"desktop":return l`
          <w3m-connecting-wc-desktop .onRetry=${()=>this.initializeConnection(!0)}>
          </w3m-connecting-wc-desktop>
        `;case"mobile":return l`
          <w3m-connecting-wc-mobile isMobile .onRetry=${()=>this.initializeConnection(!0)}>
          </w3m-connecting-wc-mobile>
        `;case"qrcode":return l`<w3m-connecting-wc-qrcode></w3m-connecting-wc-qrcode>`;default:return l`<w3m-connecting-wc-unsupported></w3m-connecting-wc-unsupported>`}}headerTemplate(){return this.platforms.length>1?l`
      <w3m-connecting-header
        .platforms=${this.platforms}
        .onSelectPlatfrom=${this.onSelectPlatform.bind(this)}
      >
      </w3m-connecting-header>
    `:null}async onSelectPlatform(t){let e=this.shadowRoot?.querySelector("div");e&&(await e.animate([{opacity:1},{opacity:0}],{duration:200,fill:"forwards",easing:"ease"}).finished,this.platform=t,e.animate([{opacity:0},{opacity:1}],{duration:200,fill:"forwards",easing:"ease"}))}};ce([m()],qt.prototype,"platform",void 0);ce([m()],qt.prototype,"platforms",void 0);ce([m()],qt.prototype,"isSiwxEnabled",void 0);ce([m()],qt.prototype,"remoteFeatures",void 0);qt=ce([d("w3m-connecting-wc-view")],qt);var hr=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},So=class extends p{constructor(){super(...arguments),this.isMobile=f.isMobile()}render(){if(this.isMobile){let{featured:t,recommended:e}=E.state,{customWallets:i}=N.state,n=pt.getRecentWallets(),o=t.length||e.length||i?.length||n.length;return l`<wui-flex
        flexDirection="column"
        gap="xs"
        .margin=${["3xs","s","s","s"]}
      >
        ${o?l`<w3m-connector-list></w3m-connector-list>`:null}
        <w3m-all-wallets-widget></w3m-all-wallets-widget>
      </wui-flex>`}return l`<wui-flex flexDirection="column" .padding=${["0","0","l","0"]}>
      <w3m-connecting-wc-view></w3m-connecting-wc-view>
      <wui-flex flexDirection="column" .padding=${["0","m","0","m"]}>
        <w3m-all-wallets-widget></w3m-all-wallets-widget> </wui-flex
    ></wui-flex>`}};hr([m()],So.prototype,"isMobile",void 0);So=hr([d("w3m-connecting-wc-basic-view")],So);var Ft=()=>new To,To=class{},_o=new WeakMap,Vt=Po(class extends Do{render(r){return Ke}update(r,[t]){let e=t!==this.G;return e&&this.G!==void 0&&this.rt(void 0),(e||this.lt!==this.ct)&&(this.G=t,this.ht=r.options?.host,this.rt(this.ct=r.element)),Ke}rt(r){if(this.isConnected||(r=void 0),typeof this.G=="function"){let t=this.ht??globalThis,e=_o.get(t);e===void 0&&(e=new WeakMap,_o.set(t,e)),e.get(this.G)!==void 0&&this.G.call(this.ht,void 0),e.set(this.G,r),r!==void 0&&this.G.call(this.ht,r)}else this.G.value=r}get lt(){return typeof this.G=="function"?_o.get(this.ht??globalThis)?.get(this.G):this.G?.value}disconnected(){this.lt===this.ct&&this.rt(void 0)}reconnected(){this.rt(this.ct)}});var mr=g`
  :host {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  label {
    position: relative;
    display: inline-block;
    width: 32px;
    height: 22px;
  }

  input {
    width: 0;
    height: 0;
    opacity: 0;
  }

  span {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: var(--wui-color-blue-100);
    border-width: 1px;
    border-style: solid;
    border-color: var(--wui-color-gray-glass-002);
    border-radius: 999px;
    transition:
      background-color var(--wui-ease-inout-power-1) var(--wui-duration-md),
      border-color var(--wui-ease-inout-power-1) var(--wui-duration-md);
    will-change: background-color, border-color;
  }

  span:before {
    position: absolute;
    content: '';
    height: 16px;
    width: 16px;
    left: 3px;
    top: 2px;
    background-color: var(--wui-color-inverse-100);
    transition: transform var(--wui-ease-inout-power-1) var(--wui-duration-lg);
    will-change: transform;
    border-radius: 50%;
  }

  input:checked + span {
    border-color: var(--wui-color-gray-glass-005);
    background-color: var(--wui-color-blue-100);
  }

  input:not(:checked) + span {
    background-color: var(--wui-color-gray-glass-010);
  }

  input:checked + span:before {
    transform: translateX(calc(100% - 7px));
  }
`;var fr=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},ze=class extends p{constructor(){super(...arguments),this.inputElementRef=Ft(),this.checked=void 0}render(){return l`
      <label>
        <input
          ${Vt(this.inputElementRef)}
          type="checkbox"
          ?checked=${h(this.checked)}
          @change=${this.dispatchChangeEvent.bind(this)}
        />
        <span></span>
      </label>
    `}dispatchChangeEvent(){this.dispatchEvent(new CustomEvent("switchChange",{detail:this.inputElementRef.value?.checked,bubbles:!0,composed:!0}))}};ze.styles=[y,_,Ao,mr];fr([c({type:Boolean})],ze.prototype,"checked",void 0);ze=fr([d("wui-switch")],ze);var gr=g`
  :host {
    height: 100%;
  }

  button {
    display: flex;
    align-items: center;
    justify-content: center;
    column-gap: var(--wui-spacing-1xs);
    padding: var(--wui-spacing-xs) var(--wui-spacing-s);
    background-color: var(--wui-color-gray-glass-002);
    border-radius: var(--wui-border-radius-xs);
    box-shadow: inset 0 0 0 1px var(--wui-color-gray-glass-002);
    transition: background-color var(--wui-ease-out-power-1) var(--wui-duration-md);
    will-change: background-color;
    cursor: pointer;
  }

  wui-switch {
    pointer-events: none;
  }
`;var wr=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Ue=class extends p{constructor(){super(...arguments),this.checked=void 0}render(){return l`
      <button>
        <wui-icon size="xl" name="walletConnectBrown"></wui-icon>
        <wui-switch ?checked=${h(this.checked)}></wui-switch>
      </button>
    `}};Ue.styles=[y,_,gr];wr([c({type:Boolean})],Ue.prototype,"checked",void 0);Ue=wr([d("wui-certified-switch")],Ue);var br=g`
  button {
    background-color: var(--wui-color-fg-300);
    border-radius: var(--wui-border-radius-4xs);
    width: 16px;
    height: 16px;
  }

  button:disabled {
    background-color: var(--wui-color-bg-300);
  }

  wui-icon {
    color: var(--wui-color-bg-200) !important;
  }

  button:focus-visible {
    background-color: var(--wui-color-fg-250);
    border: 1px solid var(--wui-color-accent-100);
  }

  @media (hover: hover) and (pointer: fine) {
    button:hover:enabled {
      background-color: var(--wui-color-fg-250);
    }

    button:active:enabled {
      background-color: var(--wui-color-fg-225);
    }
  }
`;var vr=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Ne=class extends p{constructor(){super(...arguments),this.icon="copy"}render(){return l`
      <button>
        <wui-icon color="inherit" size="xxs" name=${this.icon}></wui-icon>
      </button>
    `}};Ne.styles=[y,_,br];vr([c()],Ne.prototype,"icon",void 0);Ne=vr([d("wui-input-element")],Ne);var xr=g`
  :host {
    position: relative;
    width: 100%;
    display: inline-block;
    color: var(--wui-color-fg-275);
  }

  input {
    width: 100%;
    border-radius: var(--wui-border-radius-xs);
    box-shadow: inset 0 0 0 1px var(--wui-color-gray-glass-002);
    background: var(--wui-color-gray-glass-002);
    font-size: var(--wui-font-size-paragraph);
    letter-spacing: var(--wui-letter-spacing-paragraph);
    color: var(--wui-color-fg-100);
    transition:
      background-color var(--wui-ease-inout-power-1) var(--wui-duration-md),
      border-color var(--wui-ease-inout-power-1) var(--wui-duration-md),
      box-shadow var(--wui-ease-inout-power-1) var(--wui-duration-md);
    will-change: background-color, border-color, box-shadow;
    caret-color: var(--wui-color-accent-100);
  }

  input:disabled {
    cursor: not-allowed;
    border: 1px solid var(--wui-color-gray-glass-010);
  }

  input:disabled::placeholder,
  input:disabled + wui-icon {
    color: var(--wui-color-fg-300);
  }

  input::placeholder {
    color: var(--wui-color-fg-275);
  }

  input:focus:enabled {
    background-color: var(--wui-color-gray-glass-005);
    -webkit-box-shadow:
      inset 0 0 0 1px var(--wui-color-accent-100),
      0px 0px 0px 4px var(--wui-box-shadow-blue);
    -moz-box-shadow:
      inset 0 0 0 1px var(--wui-color-accent-100),
      0px 0px 0px 4px var(--wui-box-shadow-blue);
    box-shadow:
      inset 0 0 0 1px var(--wui-color-accent-100),
      0px 0px 0px 4px var(--wui-box-shadow-blue);
  }

  input:hover:enabled {
    background-color: var(--wui-color-gray-glass-005);
  }

  wui-icon {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    pointer-events: none;
  }

  .wui-size-sm {
    padding: 9px var(--wui-spacing-m) 10px var(--wui-spacing-s);
  }

  wui-icon + .wui-size-sm {
    padding: 9px var(--wui-spacing-m) 10px 36px;
  }

  wui-icon[data-input='sm'] {
    left: var(--wui-spacing-s);
  }

  .wui-size-md {
    padding: 15px var(--wui-spacing-m) var(--wui-spacing-l) var(--wui-spacing-m);
  }

  wui-icon + .wui-size-md,
  wui-loading-spinner + .wui-size-md {
    padding: 10.5px var(--wui-spacing-3xl) 10.5px var(--wui-spacing-3xl);
  }

  wui-icon[data-input='md'] {
    left: var(--wui-spacing-l);
  }

  .wui-size-lg {
    padding: var(--wui-spacing-s) var(--wui-spacing-s) var(--wui-spacing-s) var(--wui-spacing-l);
    letter-spacing: var(--wui-letter-spacing-medium-title);
    font-size: var(--wui-font-size-medium-title);
    font-weight: var(--wui-font-weight-light);
    line-height: 130%;
    color: var(--wui-color-fg-100);
    height: 64px;
  }

  .wui-padding-right-xs {
    padding-right: var(--wui-spacing-xs);
  }

  .wui-padding-right-s {
    padding-right: var(--wui-spacing-s);
  }

  .wui-padding-right-m {
    padding-right: var(--wui-spacing-m);
  }

  .wui-padding-right-l {
    padding-right: var(--wui-spacing-l);
  }

  .wui-padding-right-xl {
    padding-right: var(--wui-spacing-xl);
  }

  .wui-padding-right-2xl {
    padding-right: var(--wui-spacing-2xl);
  }

  .wui-padding-right-3xl {
    padding-right: var(--wui-spacing-3xl);
  }

  .wui-padding-right-4xl {
    padding-right: var(--wui-spacing-4xl);
  }

  .wui-padding-right-5xl {
    padding-right: var(--wui-spacing-5xl);
  }

  wui-icon + .wui-size-lg,
  wui-loading-spinner + .wui-size-lg {
    padding-left: 50px;
  }

  wui-icon[data-input='lg'] {
    left: var(--wui-spacing-l);
  }

  .wui-size-mdl {
    padding: 17.25px var(--wui-spacing-m) 17.25px var(--wui-spacing-m);
  }
  wui-icon + .wui-size-mdl,
  wui-loading-spinner + .wui-size-mdl {
    padding: 17.25px var(--wui-spacing-3xl) 17.25px 40px;
  }
  wui-icon[data-input='mdl'] {
    left: var(--wui-spacing-m);
  }

  input:placeholder-shown ~ ::slotted(wui-input-element),
  input:placeholder-shown ~ ::slotted(wui-icon) {
    opacity: 0;
    pointer-events: none;
  }

  input::-webkit-outer-spin-button,
  input::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }

  input[type='number'] {
    -moz-appearance: textfield;
  }

  ::slotted(wui-input-element),
  ::slotted(wui-icon) {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
  }

  ::slotted(wui-input-element) {
    right: var(--wui-spacing-m);
  }

  ::slotted(wui-icon) {
    right: 0px;
  }
`;var rt=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},J=class extends p{constructor(){super(...arguments),this.inputElementRef=Ft(),this.size="md",this.disabled=!1,this.placeholder="",this.type="text",this.value=""}render(){let t=`wui-padding-right-${this.inputRightPadding}`,i={[`wui-size-${this.size}`]:!0,[t]:!!this.inputRightPadding};return l`${this.templateIcon()}
      <input
        data-testid="wui-input-text"
        ${Vt(this.inputElementRef)}
        class=${jo(i)}
        type=${this.type}
        enterkeyhint=${h(this.enterKeyHint)}
        ?disabled=${this.disabled}
        placeholder=${this.placeholder}
        @input=${this.dispatchInputChangeEvent.bind(this)}
        .value=${this.value||""}
        tabindex=${h(this.tabIdx)}
      />
      <slot></slot>`}templateIcon(){return this.icon?l`<wui-icon
        data-input=${this.size}
        size=${this.size}
        color="inherit"
        name=${this.icon}
      ></wui-icon>`:null}dispatchInputChangeEvent(){this.dispatchEvent(new CustomEvent("inputChange",{detail:this.inputElementRef.value?.value,bubbles:!0,composed:!0}))}};J.styles=[y,_,xr];rt([c()],J.prototype,"size",void 0);rt([c()],J.prototype,"icon",void 0);rt([c({type:Boolean})],J.prototype,"disabled",void 0);rt([c()],J.prototype,"placeholder",void 0);rt([c()],J.prototype,"type",void 0);rt([c()],J.prototype,"keyHint",void 0);rt([c()],J.prototype,"value",void 0);rt([c()],J.prototype,"inputRightPadding",void 0);rt([c()],J.prototype,"tabIdx",void 0);J=rt([d("wui-input-text")],J);var yr=g`
  :host {
    position: relative;
    display: inline-block;
    width: 100%;
  }
`;var zn=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Lo=class extends p{constructor(){super(...arguments),this.inputComponentRef=Ft()}render(){return l`
      <wui-input-text
        ${Vt(this.inputComponentRef)}
        placeholder="Search wallet"
        icon="search"
        type="search"
        enterKeyHint="search"
        size="sm"
      >
        <wui-input-element @click=${this.clearValue} icon="close"></wui-input-element>
      </wui-input-text>
    `}clearValue(){let e=this.inputComponentRef.value?.inputElementRef.value;e&&(e.value="",e.focus(),e.dispatchEvent(new Event("input")))}};Lo.styles=[y,yr];Lo=zn([d("wui-search-bar")],Lo);var Cr=mt`<svg  viewBox="0 0 48 54" fill="none">
  <path
    d="M43.4605 10.7248L28.0485 1.61089C25.5438 0.129705 22.4562 0.129705 19.9515 1.61088L4.53951 10.7248C2.03626 12.2051 0.5 14.9365 0.5 17.886V36.1139C0.5 39.0635 2.03626 41.7949 4.53951 43.2752L19.9515 52.3891C22.4562 53.8703 25.5438 53.8703 28.0485 52.3891L43.4605 43.2752C45.9637 41.7949 47.5 39.0635 47.5 36.114V17.8861C47.5 14.9365 45.9637 12.2051 43.4605 10.7248Z"
  />
</svg>`;var Er=g`
  :host {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 104px;
    row-gap: var(--wui-spacing-xs);
    padding: var(--wui-spacing-xs) 10px;
    background-color: var(--wui-color-gray-glass-002);
    border-radius: clamp(0px, var(--wui-border-radius-xs), 20px);
    position: relative;
  }

  wui-shimmer[data-type='network'] {
    border: none;
    -webkit-clip-path: var(--wui-path-network);
    clip-path: var(--wui-path-network);
  }

  svg {
    position: absolute;
    width: 48px;
    height: 54px;
    z-index: 1;
  }

  svg > path {
    stroke: var(--wui-color-gray-glass-010);
    stroke-width: 1px;
  }

  @media (max-width: 350px) {
    :host {
      width: 100%;
    }
  }
`;var Rr=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Me=class extends p{constructor(){super(...arguments),this.type="wallet"}render(){return l`
      ${this.shimmerTemplate()}
      <wui-shimmer width="56px" height="20px" borderRadius="xs"></wui-shimmer>
    `}shimmerTemplate(){return this.type==="network"?l` <wui-shimmer
          data-type=${this.type}
          width="48px"
          height="54px"
          borderRadius="xs"
        ></wui-shimmer>
        ${Cr}`:l`<wui-shimmer width="56px" height="56px" borderRadius="xs"></wui-shimmer>`}};Me.styles=[y,_,Er];Rr([c()],Me.prototype,"type",void 0);Me=Rr([d("wui-card-select-loader")],Me);var $r=g`
  :host {
    display: grid;
    width: inherit;
    height: inherit;
  }
`;var Q=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},F=class extends p{render(){return this.style.cssText=`
      grid-template-rows: ${this.gridTemplateRows};
      grid-template-columns: ${this.gridTemplateColumns};
      justify-items: ${this.justifyItems};
      align-items: ${this.alignItems};
      justify-content: ${this.justifyContent};
      align-content: ${this.alignContent};
      column-gap: ${this.columnGap&&`var(--wui-spacing-${this.columnGap})`};
      row-gap: ${this.rowGap&&`var(--wui-spacing-${this.rowGap})`};
      gap: ${this.gap&&`var(--wui-spacing-${this.gap})`};
      padding-top: ${this.padding&&X.getSpacingStyles(this.padding,0)};
      padding-right: ${this.padding&&X.getSpacingStyles(this.padding,1)};
      padding-bottom: ${this.padding&&X.getSpacingStyles(this.padding,2)};
      padding-left: ${this.padding&&X.getSpacingStyles(this.padding,3)};
      margin-top: ${this.margin&&X.getSpacingStyles(this.margin,0)};
      margin-right: ${this.margin&&X.getSpacingStyles(this.margin,1)};
      margin-bottom: ${this.margin&&X.getSpacingStyles(this.margin,2)};
      margin-left: ${this.margin&&X.getSpacingStyles(this.margin,3)};
    `,l`<slot></slot>`}};F.styles=[y,$r];Q([c()],F.prototype,"gridTemplateRows",void 0);Q([c()],F.prototype,"gridTemplateColumns",void 0);Q([c()],F.prototype,"justifyItems",void 0);Q([c()],F.prototype,"alignItems",void 0);Q([c()],F.prototype,"justifyContent",void 0);Q([c()],F.prototype,"alignContent",void 0);Q([c()],F.prototype,"columnGap",void 0);Q([c()],F.prototype,"rowGap",void 0);Q([c()],F.prototype,"gap",void 0);Q([c()],F.prototype,"padding",void 0);Q([c()],F.prototype,"margin",void 0);F=Q([d("wui-grid")],F);var Ir=g`
  button {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    cursor: pointer;
    width: 104px;
    row-gap: var(--wui-spacing-xs);
    padding: var(--wui-spacing-s) var(--wui-spacing-0);
    background-color: var(--wui-color-gray-glass-002);
    border-radius: clamp(0px, var(--wui-border-radius-xs), 20px);
    transition:
      color var(--wui-duration-lg) var(--wui-ease-out-power-1),
      background-color var(--wui-duration-lg) var(--wui-ease-out-power-1),
      border-radius var(--wui-duration-lg) var(--wui-ease-out-power-1);
    will-change: background-color, color, border-radius;
    outline: none;
    border: none;
  }

  button > wui-flex > wui-text {
    color: var(--wui-color-fg-100);
    max-width: 86px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    justify-content: center;
  }

  button > wui-flex > wui-text.certified {
    max-width: 66px;
  }

  button:hover:enabled {
    background-color: var(--wui-color-gray-glass-005);
  }

  button:disabled > wui-flex > wui-text {
    color: var(--wui-color-gray-glass-015);
  }

  [data-selected='true'] {
    background-color: var(--wui-color-accent-glass-020);
  }

  @media (hover: hover) and (pointer: fine) {
    [data-selected='true']:hover:enabled {
      background-color: var(--wui-color-accent-glass-015);
    }
  }

  [data-selected='true']:active:enabled {
    background-color: var(--wui-color-accent-glass-010);
  }

  @media (max-width: 350px) {
    button {
      width: 100%;
    }
  }
`;var ue=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Bt=class extends p{constructor(){super(),this.observer=new IntersectionObserver(()=>{}),this.visible=!1,this.imageSrc=void 0,this.imageLoading=!1,this.wallet=void 0,this.observer=new IntersectionObserver(t=>{t.forEach(e=>{e.isIntersecting?(this.visible=!0,this.fetchImageSrc()):this.visible=!1})},{threshold:.01})}firstUpdated(){this.observer.observe(this)}disconnectedCallback(){this.observer.disconnect()}render(){let t=this.wallet?.badge_type==="certified";return l`
      <button>
        ${this.imageTemplate()}
        <wui-flex flexDirection="row" alignItems="center" justifyContent="center" gap="3xs">
          <wui-text
            variant="tiny-500"
            color="inherit"
            class=${h(t?"certified":void 0)}
            >${this.wallet?.name}</wui-text
          >
          ${t?l`<wui-icon size="sm" name="walletConnectBrown"></wui-icon>`:null}
        </wui-flex>
      </button>
    `}imageTemplate(){return!this.visible&&!this.imageSrc||this.imageLoading?this.shimmerTemplate():l`
      <wui-wallet-image
        size="md"
        imageSrc=${h(this.imageSrc)}
        name=${this.wallet?.name}
        .installed=${this.wallet?.installed}
        badgeSize="sm"
      >
      </wui-wallet-image>
    `}shimmerTemplate(){return l`<wui-shimmer width="56px" height="56px" borderRadius="xs"></wui-shimmer>`}async fetchImageSrc(){this.wallet&&(this.imageSrc=B.getWalletImage(this.wallet),!this.imageSrc&&(this.imageLoading=!0,this.imageSrc=await B.fetchWalletImage(this.wallet.image_id),this.imageLoading=!1))}};Bt.styles=Ir;ue([m()],Bt.prototype,"visible",void 0);ue([m()],Bt.prototype,"imageSrc",void 0);ue([m()],Bt.prototype,"imageLoading",void 0);ue([c()],Bt.prototype,"wallet",void 0);Bt=ue([d("w3m-all-wallets-list-item")],Bt);var Wr=g`
  wui-grid {
    max-height: clamp(360px, 400px, 80vh);
    overflow: scroll;
    scrollbar-width: none;
    grid-auto-rows: min-content;
    grid-template-columns: repeat(auto-fill, 104px);
  }

  @media (max-width: 350px) {
    wui-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  wui-grid[data-scroll='false'] {
    overflow: hidden;
  }

  wui-grid::-webkit-scrollbar {
    display: none;
  }

  wui-loading-spinner {
    padding-top: var(--wui-spacing-l);
    padding-bottom: var(--wui-spacing-l);
    justify-content: center;
    grid-column: 1 / span 4;
  }
`;var Ht=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Sr="local-paginator",xt=class extends p{constructor(){super(),this.unsubscribe=[],this.paginationObserver=void 0,this.loading=!E.state.wallets.length,this.wallets=E.state.wallets,this.recommended=E.state.recommended,this.featured=E.state.featured,this.filteredWallets=E.state.filteredWallets,this.unsubscribe.push(E.subscribeKey("wallets",t=>this.wallets=t),E.subscribeKey("recommended",t=>this.recommended=t),E.subscribeKey("featured",t=>this.featured=t),E.subscribeKey("filteredWallets",t=>this.filteredWallets=t))}firstUpdated(){this.initialFetch(),this.createPaginationObserver()}disconnectedCallback(){this.unsubscribe.forEach(t=>t()),this.paginationObserver?.disconnect()}render(){return l`
      <wui-grid
        data-scroll=${!this.loading}
        .padding=${["0","s","s","s"]}
        columnGap="xxs"
        rowGap="l"
        justifyContent="space-between"
      >
        ${this.loading?this.shimmerTemplate(16):this.walletsTemplate()}
        ${this.paginationLoaderTemplate()}
      </wui-grid>
    `}async initialFetch(){this.loading=!0;let t=this.shadowRoot?.querySelector("wui-grid");t&&(await E.fetchWalletsByPage({page:1}),await t.animate([{opacity:1},{opacity:0}],{duration:200,fill:"forwards",easing:"ease"}).finished,this.loading=!1,t.animate([{opacity:0},{opacity:1}],{duration:200,fill:"forwards",easing:"ease"}))}shimmerTemplate(t,e){return[...Array(t)].map(()=>l`
        <wui-card-select-loader type="wallet" id=${h(e)}></wui-card-select-loader>
      `)}walletsTemplate(){let t=this.filteredWallets?.length>0?f.uniqueBy([...this.featured,...this.recommended,...this.filteredWallets],"id"):f.uniqueBy([...this.featured,...this.recommended,...this.wallets],"id");return ht.markWalletsAsInstalled(t).map(i=>l`
        <w3m-all-wallets-list-item
          @click=${()=>this.onConnectWallet(i)}
          .wallet=${i}
        ></w3m-all-wallets-list-item>
      `)}paginationLoaderTemplate(){let{wallets:t,recommended:e,featured:i,count:n}=E.state,o=window.innerWidth<352?3:4,s=t.length+e.length,u=Math.ceil(s/o)*o-s+o;return u-=t.length?i.length%o:0,n===0&&i.length>0?null:n===0||[...i,...t,...e].length<n?this.shimmerTemplate(u,Sr):null}createPaginationObserver(){let t=this.shadowRoot?.querySelector(`#${Sr}`);t&&(this.paginationObserver=new IntersectionObserver(([e])=>{if(e?.isIntersecting&&!this.loading){let{page:i,count:n,wallets:o}=E.state;o.length<n&&E.fetchWalletsByPage({page:i+1})}}),this.paginationObserver.observe(t))}onConnectWallet(t){v.selectWalletConnector(t)}};xt.styles=Wr;Ht([m()],xt.prototype,"loading",void 0);Ht([m()],xt.prototype,"wallets",void 0);Ht([m()],xt.prototype,"recommended",void 0);Ht([m()],xt.prototype,"featured",void 0);Ht([m()],xt.prototype,"filteredWallets",void 0);xt=Ht([d("w3m-all-wallets-list")],xt);var _r=g`
  wui-grid,
  wui-loading-spinner,
  wui-flex {
    height: 360px;
  }

  wui-grid {
    overflow: scroll;
    scrollbar-width: none;
    grid-auto-rows: min-content;
    grid-template-columns: repeat(auto-fill, 104px);
  }

  wui-grid[data-scroll='false'] {
    overflow: hidden;
  }

  wui-grid::-webkit-scrollbar {
    display: none;
  }

  wui-loading-spinner {
    justify-content: center;
    align-items: center;
  }

  @media (max-width: 350px) {
    wui-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }
`;var qe=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Kt=class extends p{constructor(){super(...arguments),this.prevQuery="",this.prevBadge=void 0,this.loading=!0,this.query=""}render(){return this.onSearch(),this.loading?l`<wui-loading-spinner color="accent-100"></wui-loading-spinner>`:this.walletsTemplate()}async onSearch(){(this.query.trim()!==this.prevQuery.trim()||this.badge!==this.prevBadge)&&(this.prevQuery=this.query,this.prevBadge=this.badge,this.loading=!0,await E.searchWallet({search:this.query,badge:this.badge}),this.loading=!1)}walletsTemplate(){let{search:t}=E.state,e=ht.markWalletsAsInstalled(t);return t.length?l`
      <wui-grid
        data-testid="wallet-list"
        .padding=${["0","s","s","s"]}
        rowGap="l"
        columnGap="xs"
        justifyContent="space-between"
      >
        ${e.map(i=>l`
            <w3m-all-wallets-list-item
              @click=${()=>this.onConnectWallet(i)}
              .wallet=${i}
              data-testid="wallet-search-item-${i.id}"
            ></w3m-all-wallets-list-item>
          `)}
      </wui-grid>
    `:l`
        <wui-flex
          data-testid="no-wallet-found"
          justifyContent="center"
          alignItems="center"
          gap="s"
          flexDirection="column"
        >
          <wui-icon-box
            size="lg"
            iconColor="fg-200"
            backgroundColor="fg-300"
            icon="wallet"
            background="transparent"
          ></wui-icon-box>
          <wui-text data-testid="no-wallet-found-text" color="fg-200" variant="paragraph-500">
            No Wallet found
          </wui-text>
        </wui-flex>
      `}onConnectWallet(t){v.selectWalletConnector(t)}};Kt.styles=_r;qe([m()],Kt.prototype,"loading",void 0);qe([c()],Kt.prototype,"query",void 0);qe([c()],Kt.prototype,"badge",void 0);Kt=qe([d("w3m-all-wallets-search")],Kt);var Bo=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Fe=class extends p{constructor(){super(...arguments),this.search="",this.onDebouncedSearch=f.debounce(t=>{this.search=t})}render(){let t=this.search.length>=2;return l`
      <wui-flex .padding=${["0","s","s","s"]} gap="xs">
        <wui-search-bar @inputChange=${this.onInputChange.bind(this)}></wui-search-bar>
        <wui-certified-switch
          ?checked=${this.badge}
          @click=${this.onClick.bind(this)}
          data-testid="wui-certified-switch"
        ></wui-certified-switch>
        ${this.qrButtonTemplate()}
      </wui-flex>
      ${t||this.badge?l`<w3m-all-wallets-search
            query=${this.search}
            badge=${h(this.badge)}
          ></w3m-all-wallets-search>`:l`<w3m-all-wallets-list badge=${h(this.badge)}></w3m-all-wallets-list>`}
    `}onInputChange(t){this.onDebouncedSearch(t.detail)}onClick(){if(this.badge==="certified"){this.badge=void 0;return}this.badge="certified",yt.showSvg("Only WalletConnect certified",{icon:"walletConnectBrown",iconColor:"accent-100"})}qrButtonTemplate(){return f.isMobile()?l`
        <wui-icon-box
          size="lg"
          iconSize="xl"
          iconColor="accent-100"
          backgroundColor="accent-100"
          icon="qrCode"
          background="transparent"
          border
          borderColor="wui-accent-glass-010"
          @click=${this.onWalletConnectQr.bind(this)}
        ></wui-icon-box>
      `:null}onWalletConnectQr(){C.push("ConnectingWalletConnect")}};Bo([m()],Fe.prototype,"search",void 0);Bo([m()],Fe.prototype,"badge",void 0);Fe=Bo([d("w3m-all-wallets-view")],Fe);var Tr=g`
  button {
    column-gap: var(--wui-spacing-s);
    padding: 11px 18px 11px var(--wui-spacing-s);
    width: 100%;
    background-color: var(--wui-color-gray-glass-002);
    border-radius: var(--wui-border-radius-xs);
    color: var(--wui-color-fg-250);
    transition:
      color var(--wui-ease-out-power-1) var(--wui-duration-md),
      background-color var(--wui-ease-out-power-1) var(--wui-duration-md);
    will-change: color, background-color;
  }

  button[data-iconvariant='square'],
  button[data-iconvariant='square-blue'] {
    padding: 6px 18px 6px 9px;
  }

  button > wui-flex {
    flex: 1;
  }

  button > wui-image {
    width: 32px;
    height: 32px;
    box-shadow: 0 0 0 2px var(--wui-color-gray-glass-005);
    border-radius: var(--wui-border-radius-3xl);
  }

  button > wui-icon {
    width: 36px;
    height: 36px;
    transition: opacity var(--wui-ease-out-power-1) var(--wui-duration-md);
    will-change: opacity;
  }

  button > wui-icon-box[data-variant='blue'] {
    box-shadow: 0 0 0 2px var(--wui-color-accent-glass-005);
  }

  button > wui-icon-box[data-variant='overlay'] {
    box-shadow: 0 0 0 2px var(--wui-color-gray-glass-005);
  }

  button > wui-icon-box[data-variant='square-blue'] {
    border-radius: var(--wui-border-radius-3xs);
    position: relative;
    border: none;
    width: 36px;
    height: 36px;
  }

  button > wui-icon-box[data-variant='square-blue']::after {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    right: 0;
    border-radius: inherit;
    border: 1px solid var(--wui-color-accent-glass-010);
    pointer-events: none;
  }

  button > wui-icon:last-child {
    width: 14px;
    height: 14px;
  }

  button:disabled {
    color: var(--wui-color-gray-glass-020);
  }

  button[data-loading='true'] > wui-icon {
    opacity: 0;
  }

  wui-loading-spinner {
    position: absolute;
    right: 18px;
    top: 50%;
    transform: translateY(-50%);
  }
`;var tt=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},H=class extends p{constructor(){super(...arguments),this.tabIdx=void 0,this.variant="icon",this.disabled=!1,this.imageSrc=void 0,this.alt=void 0,this.chevron=!1,this.loading=!1}render(){return l`
      <button
        ?disabled=${this.loading?!0:!!this.disabled}
        data-loading=${this.loading}
        data-iconvariant=${h(this.iconVariant)}
        tabindex=${h(this.tabIdx)}
      >
        ${this.loadingTemplate()} ${this.visualTemplate()}
        <wui-flex gap="3xs">
          <slot></slot>
        </wui-flex>
        ${this.chevronTemplate()}
      </button>
    `}visualTemplate(){if(this.variant==="image"&&this.imageSrc)return l`<wui-image src=${this.imageSrc} alt=${this.alt??"list item"}></wui-image>`;if(this.iconVariant==="square"&&this.icon&&this.variant==="icon")return l`<wui-icon name=${this.icon}></wui-icon>`;if(this.variant==="icon"&&this.icon&&this.iconVariant){let t=["blue","square-blue"].includes(this.iconVariant)?"accent-100":"fg-200",e=this.iconVariant==="square-blue"?"mdl":"md",i=this.iconSize?this.iconSize:e;return l`
        <wui-icon-box
          data-variant=${this.iconVariant}
          icon=${this.icon}
          iconSize=${i}
          background="transparent"
          iconColor=${t}
          backgroundColor=${t}
          size=${e}
        ></wui-icon-box>
      `}return null}loadingTemplate(){return this.loading?l`<wui-loading-spinner
        data-testid="wui-list-item-loading-spinner"
        color="fg-300"
      ></wui-loading-spinner>`:l``}chevronTemplate(){return this.chevron?l`<wui-icon size="inherit" color="fg-200" name="chevronRight"></wui-icon>`:null}};H.styles=[y,_,Tr];tt([c()],H.prototype,"icon",void 0);tt([c()],H.prototype,"iconSize",void 0);tt([c()],H.prototype,"tabIdx",void 0);tt([c()],H.prototype,"variant",void 0);tt([c()],H.prototype,"iconVariant",void 0);tt([c({type:Boolean})],H.prototype,"disabled",void 0);tt([c()],H.prototype,"imageSrc",void 0);tt([c()],H.prototype,"alt",void 0);tt([c({type:Boolean})],H.prototype,"chevron",void 0);tt([c({type:Boolean})],H.prototype,"loading",void 0);H=tt([d("wui-list-item")],H);var Un=function(r,t,e,i){var n=arguments.length,o=n<3?t:i===null?i=Object.getOwnPropertyDescriptor(t,e):i,s;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")o=Reflect.decorate(r,t,e,i);else for(var a=r.length-1;a>=0;a--)(s=r[a])&&(o=(n<3?s(o):n>3?s(t,e,o):s(t,e))||o);return n>3&&o&&Object.defineProperty(t,e,o),o},Lr=class extends p{constructor(){super(...arguments),this.wallet=C.state.data?.wallet}render(){if(!this.wallet)throw new Error("w3m-downloads-view");return l`
      <wui-flex gap="xs" flexDirection="column" .padding=${["s","s","l","s"]}>
        ${this.chromeTemplate()} ${this.iosTemplate()} ${this.androidTemplate()}
        ${this.homepageTemplate()}
      </wui-flex>
    `}chromeTemplate(){return this.wallet?.chrome_store?l`<wui-list-item
      variant="icon"
      icon="chromeStore"
      iconVariant="square"
      @click=${this.onChromeStore.bind(this)}
      chevron
    >
      <wui-text variant="paragraph-500" color="fg-100">Chrome Extension</wui-text>
    </wui-list-item>`:null}iosTemplate(){return this.wallet?.app_store?l`<wui-list-item
      variant="icon"
      icon="appStore"
      iconVariant="square"
      @click=${this.onAppStore.bind(this)}
      chevron
    >
      <wui-text variant="paragraph-500" color="fg-100">iOS App</wui-text>
    </wui-list-item>`:null}androidTemplate(){return this.wallet?.play_store?l`<wui-list-item
      variant="icon"
      icon="playStore"
      iconVariant="square"
      @click=${this.onPlayStore.bind(this)}
      chevron
    >
      <wui-text variant="paragraph-500" color="fg-100">Android App</wui-text>
    </wui-list-item>`:null}homepageTemplate(){return this.wallet?.homepage?l`
      <wui-list-item
        variant="icon"
        icon="browser"
        iconVariant="square-blue"
        @click=${this.onHomePage.bind(this)}
        chevron
      >
        <wui-text variant="paragraph-500" color="fg-100">Website</wui-text>
      </wui-list-item>
    `:null}onChromeStore(){this.wallet?.chrome_store&&f.openHref(this.wallet.chrome_store,"_blank")}onAppStore(){this.wallet?.app_store&&f.openHref(this.wallet.app_store,"_blank")}onPlayStore(){this.wallet?.play_store&&f.openHref(this.wallet.play_store,"_blank")}onHomePage(){this.wallet?.homepage&&f.openHref(this.wallet.homepage,"_blank")}};Lr=Un([d("w3m-downloads-view")],Lr);export{Fe as W3mAllWalletsView,So as W3mConnectingWcBasicView,Lr as W3mDownloadsView};
/*! Bundled license information:

lit-html/directives/ref.js:
  (**
   * @license
   * Copyright 2020 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)
*/

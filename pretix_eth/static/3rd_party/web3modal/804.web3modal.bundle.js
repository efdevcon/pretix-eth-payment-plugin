(self.webpackChunkbuild_web3modal=self.webpackChunkbuild_web3modal||[]).push([[804],{926:(t,e,r)=>{"use strict";function n(){return(null===r.g||void 0===r.g?void 0:r.g.crypto)||(null===r.g||void 0===r.g?void 0:r.g.msCrypto)||{}}function s(){const t=n();return t.subtle||t.webkitSubtle}Object.defineProperty(e,"__esModule",{value:!0}),e.isBrowserCryptoAvailable=e.getSubtleCrypto=e.getBrowerCrypto=void 0,e.getBrowerCrypto=n,e.getSubtleCrypto=s,e.isBrowserCryptoAvailable=function(){return!!n()&&!!s()}},8618:(t,e)=>{"use strict";function r(){return"undefined"==typeof document&&"undefined"!=typeof navigator&&"ReactNative"===navigator.product}function n(){return"undefined"!=typeof process&&void 0!==process.versions&&void 0!==process.versions.node}Object.defineProperty(e,"__esModule",{value:!0}),e.isBrowser=e.isNode=e.isReactNative=void 0,e.isReactNative=r,e.isNode=n,e.isBrowser=function(){return!r()&&!n()}},1468:(t,e,r)=>{"use strict";Object.defineProperty(e,"__esModule",{value:!0});const n=r(655);n.__exportStar(r(926),e),n.__exportStar(r(8618),e)},4497:(t,e,r)=>{"use strict";r.d(e,{k:()=>u,Z:()=>p});var n=r(7187),s=r(4098),o=r.n(s),i=r(5094),c=r(6186);const a={headers:{Accept:"application/json","Content-Type":"application/json"},method:"POST"};class u{constructor(t){if(this.url=t,this.events=new n.EventEmitter,this.isAvailable=!1,this.registering=!1,!(0,c.isHttpUrl)(t))throw new Error(`Provided URL is not compatible with HTTP connection: ${t}`);this.url=t}get connected(){return this.isAvailable}get connecting(){return this.registering}on(t,e){this.events.on(t,e)}once(t,e){this.events.once(t,e)}off(t,e){this.events.off(t,e)}removeListener(t,e){this.events.removeListener(t,e)}async open(t=this.url){await this.register(t)}async close(){if(!this.isAvailable)throw new Error("Connection already closed");this.onClose()}async send(t,e){this.isAvailable||await this.register();try{const e=(0,i.u)(t),r=await o()(this.url,Object.assign(Object.assign({},a),{body:e})),n=await r.json();this.onPayload({data:n})}catch(e){this.onError(t.id,e)}}async register(t=this.url){if(!(0,c.isHttpUrl)(t))throw new Error(`Provided URL is not compatible with HTTP connection: ${t}`);if(this.registering){const t=this.events.getMaxListeners();return(this.events.listenerCount("register_error")>=t||this.events.listenerCount("open")>=t)&&this.events.setMaxListeners(t+1),new Promise(((t,e)=>{this.events.once("register_error",(t=>{this.resetMaxListeners(),e(t)})),this.events.once("open",(()=>{if(this.resetMaxListeners(),void 0===this.isAvailable)return e(new Error("HTTP connection is missing or invalid"));t()}))}))}this.url=t,this.registering=!0;try{const e=(0,i.u)({id:1,jsonrpc:"2.0",method:"test",params:[]});await o()(t,Object.assign(Object.assign({},a),{body:e})),this.onOpen()}catch(t){const e=this.parseError(t);throw this.events.emit("register_error",e),this.onClose(),e}}onOpen(){this.isAvailable=!0,this.registering=!1,this.events.emit("open")}onClose(){this.isAvailable=!1,this.registering=!1,this.events.emit("close")}onPayload(t){if(void 0===t.data)return;const e="string"==typeof t.data?(0,i.D)(t.data):t.data;this.events.emit("payload",e)}onError(t,e){const r=this.parseError(e),n=r.message||r.toString(),s=(0,c.formatJsonRpcError)(t,n);this.events.emit("payload",s)}parseError(t,e=this.url){return(0,c.parseConnectionError)(t,e,"HTTP")}resetMaxListeners(){this.events.getMaxListeners()>10&&this.events.setMaxListeners(10)}}const p=u},9303:(t,e,r)=>{"use strict";r.d(e,{r:()=>o});var n=r(7187),s=r(6186);class o extends s.IJsonRpcProvider{constructor(t){super(t),this.events=new n.EventEmitter,this.hasRegisteredEventListeners=!1,this.connection=this.setConnection(t),this.connection.connected&&this.registerEventListeners()}async connect(t=this.connection){await this.open(t)}async disconnect(){await this.close()}on(t,e){this.events.on(t,e)}once(t,e){this.events.once(t,e)}off(t,e){this.events.off(t,e)}removeListener(t,e){this.events.removeListener(t,e)}async request(t,e){return this.requestStrict((0,s.formatJsonRpcRequest)(t.method,t.params||[]),e)}async requestStrict(t,e){return new Promise((async(r,n)=>{if(!this.connection.connected)try{await this.open()}catch(t){n(t)}this.events.on(`${t.id}`,(t=>{(0,s.isJsonRpcError)(t)?n(t.error):r(t.result)}));try{await this.connection.send(t,e)}catch(t){n(t)}}))}setConnection(t=this.connection){return t}onPayload(t){this.events.emit("payload",t),(0,s.isJsonRpcResponse)(t)?this.events.emit(`${t.id}`,t):this.events.emit("message",{type:t.method,data:t.params})}async open(t=this.connection){this.connection===t&&this.connection.connected||(this.connection.connected&&this.close(),"string"==typeof t&&(await this.connection.open(t),t=this.connection),this.connection=this.setConnection(t),await this.connection.open(),this.registerEventListeners(),this.events.emit("connect"))}async close(){await this.connection.close()}registerEventListeners(){this.hasRegisteredEventListeners||(this.connection.on("payload",(t=>this.onPayload(t))),this.connection.on("close",(()=>this.events.emit("disconnect"))),this.connection.on("error",(t=>this.events.emit("error",t))),this.hasRegisteredEventListeners=!0)}}},5885:(t,e,r)=>{"use strict";r.d(e,{IJsonRpcProvider:()=>s.x0});var n=r(4057);r.o(n,"IJsonRpcProvider")&&r.d(e,{IJsonRpcProvider:function(){return n.IJsonRpcProvider}}),r.o(n,"isHttpUrl")&&r.d(e,{isHttpUrl:function(){return n.isHttpUrl}}),r.o(n,"isJsonRpcError")&&r.d(e,{isJsonRpcError:function(){return n.isJsonRpcError}}),r.o(n,"isJsonRpcRequest")&&r.d(e,{isJsonRpcRequest:function(){return n.isJsonRpcRequest}}),r.o(n,"isJsonRpcResponse")&&r.d(e,{isJsonRpcResponse:function(){return n.isJsonRpcResponse}}),r.o(n,"isJsonRpcResult")&&r.d(e,{isJsonRpcResult:function(){return n.isJsonRpcResult}}),r.o(n,"isLocalhostUrl")&&r.d(e,{isLocalhostUrl:function(){return n.isLocalhostUrl}}),r.o(n,"isReactNative")&&r.d(e,{isReactNative:function(){return n.isReactNative}}),r.o(n,"isWsUrl")&&r.d(e,{isWsUrl:function(){return n.isWsUrl}});var s=r(7826),o=r(1948);r.o(o,"isHttpUrl")&&r.d(e,{isHttpUrl:function(){return o.isHttpUrl}}),r.o(o,"isJsonRpcError")&&r.d(e,{isJsonRpcError:function(){return o.isJsonRpcError}}),r.o(o,"isJsonRpcRequest")&&r.d(e,{isJsonRpcRequest:function(){return o.isJsonRpcRequest}}),r.o(o,"isJsonRpcResponse")&&r.d(e,{isJsonRpcResponse:function(){return o.isJsonRpcResponse}}),r.o(o,"isJsonRpcResult")&&r.d(e,{isJsonRpcResult:function(){return o.isJsonRpcResult}}),r.o(o,"isLocalhostUrl")&&r.d(e,{isLocalhostUrl:function(){return o.isLocalhostUrl}}),r.o(o,"isReactNative")&&r.d(e,{isReactNative:function(){return o.isReactNative}}),r.o(o,"isWsUrl")&&r.d(e,{isWsUrl:function(){return o.isWsUrl}})},4057:()=>{},7826:(t,e,r)=>{"use strict";r.d(e,{XR:()=>s,x0:()=>i});class n{}class s extends n{constructor(t){super()}}class o extends n{constructor(){super()}}class i extends o{constructor(t){super()}}},1948:()=>{},9806:(t,e,r)=>{"use strict";r.d(e,{CA:()=>s,JV:()=>c,O4:()=>n,dQ:()=>o,xK:()=>i});const n="INTERNAL_ERROR",s="SERVER_ERROR",o=[-32700,-32600,-32601,-32602,-32603],i={PARSE_ERROR:{code:-32700,message:"Parse error"},INVALID_REQUEST:{code:-32600,message:"Invalid Request"},METHOD_NOT_FOUND:{code:-32601,message:"Method not found"},INVALID_PARAMS:{code:-32602,message:"Invalid params"},[n]:{code:-32603,message:"Internal error"},[s]:{code:-32e3,message:"Server error"}},c=s},9698:(t,e,r)=>{"use strict";var n=r(1468);r.o(n,"IJsonRpcProvider")&&r.d(e,{IJsonRpcProvider:function(){return n.IJsonRpcProvider}}),r.o(n,"formatJsonRpcError")&&r.d(e,{formatJsonRpcError:function(){return n.formatJsonRpcError}}),r.o(n,"formatJsonRpcRequest")&&r.d(e,{formatJsonRpcRequest:function(){return n.formatJsonRpcRequest}}),r.o(n,"formatJsonRpcResult")&&r.d(e,{formatJsonRpcResult:function(){return n.formatJsonRpcResult}}),r.o(n,"isHttpUrl")&&r.d(e,{isHttpUrl:function(){return n.isHttpUrl}}),r.o(n,"isJsonRpcError")&&r.d(e,{isJsonRpcError:function(){return n.isJsonRpcError}}),r.o(n,"isJsonRpcRequest")&&r.d(e,{isJsonRpcRequest:function(){return n.isJsonRpcRequest}}),r.o(n,"isJsonRpcResponse")&&r.d(e,{isJsonRpcResponse:function(){return n.isJsonRpcResponse}}),r.o(n,"isJsonRpcResult")&&r.d(e,{isJsonRpcResult:function(){return n.isJsonRpcResult}}),r.o(n,"isLocalhostUrl")&&r.d(e,{isLocalhostUrl:function(){return n.isLocalhostUrl}}),r.o(n,"isReactNative")&&r.d(e,{isReactNative:function(){return n.isReactNative}}),r.o(n,"isWsUrl")&&r.d(e,{isWsUrl:function(){return n.isWsUrl}}),r.o(n,"payloadId")&&r.d(e,{payloadId:function(){return n.payloadId}})},110:(t,e,r)=>{"use strict";r.d(e,{CX:()=>c,L2:()=>i,by:()=>o,i5:()=>s});var n=r(9806);function s(t){return n.dQ.includes(t)}function o(t){return Object.keys(n.xK).includes(t)?n.xK[t]:n.xK[n.JV]}function i(t){return Object.values(n.xK).find((e=>e.code===t))||n.xK[n.JV]}function c(t,e,r){return t.message.includes("getaddrinfo ENOTFOUND")||t.message.includes("connect ECONNREFUSED")?new Error(`Unavailable ${r} RPC url at ${e}`):t}},1937:(t,e,r)=>{"use strict";r.d(e,{RI:()=>a,o0:()=>o,sT:()=>i,tm:()=>c});var n=r(110),s=r(9806);function o(){return Date.now()*Math.pow(10,3)+Math.floor(Math.random()*Math.pow(10,3))}function i(t,e,r){return{id:r||o(),jsonrpc:"2.0",method:t,params:e}}function c(t,e){return{id:t,jsonrpc:"2.0",result:e}}function a(t,e,r){return{id:t,jsonrpc:"2.0",error:u(e,r)}}function u(t,e){return void 0===t?(0,n.by)(s.O4):("string"==typeof t&&(t=Object.assign(Object.assign({},(0,n.by)(s.CA)),{message:t})),void 0!==e&&(t.data=e),(0,n.i5)(t.code)&&(t=(0,n.L2)(t.code)),t)}},6186:(t,e,r)=>{"use strict";r.d(e,{formatJsonRpcError:()=>o.RI,formatJsonRpcRequest:()=>o.sT,formatJsonRpcResult:()=>o.tm,isHttpUrl:()=>c.jK,isJsonRpcError:()=>a.jg,isJsonRpcRequest:()=>a.DW,isJsonRpcResponse:()=>a.u,isJsonRpcResult:()=>a.k4,isLocalhostUrl:()=>c.JF,isWsUrl:()=>c.UZ,parseConnectionError:()=>n.CX,payloadId:()=>o.o0}),r(9806);var n=r(110),s=r(9698);r.o(s,"IJsonRpcProvider")&&r.d(e,{IJsonRpcProvider:function(){return s.IJsonRpcProvider}}),r.o(s,"formatJsonRpcError")&&r.d(e,{formatJsonRpcError:function(){return s.formatJsonRpcError}}),r.o(s,"formatJsonRpcRequest")&&r.d(e,{formatJsonRpcRequest:function(){return s.formatJsonRpcRequest}}),r.o(s,"formatJsonRpcResult")&&r.d(e,{formatJsonRpcResult:function(){return s.formatJsonRpcResult}}),r.o(s,"isHttpUrl")&&r.d(e,{isHttpUrl:function(){return s.isHttpUrl}}),r.o(s,"isJsonRpcError")&&r.d(e,{isJsonRpcError:function(){return s.isJsonRpcError}}),r.o(s,"isJsonRpcRequest")&&r.d(e,{isJsonRpcRequest:function(){return s.isJsonRpcRequest}}),r.o(s,"isJsonRpcResponse")&&r.d(e,{isJsonRpcResponse:function(){return s.isJsonRpcResponse}}),r.o(s,"isJsonRpcResult")&&r.d(e,{isJsonRpcResult:function(){return s.isJsonRpcResult}}),r.o(s,"isLocalhostUrl")&&r.d(e,{isLocalhostUrl:function(){return s.isLocalhostUrl}}),r.o(s,"isReactNative")&&r.d(e,{isReactNative:function(){return s.isReactNative}}),r.o(s,"isWsUrl")&&r.d(e,{isWsUrl:function(){return s.isWsUrl}}),r.o(s,"payloadId")&&r.d(e,{payloadId:function(){return s.payloadId}});var o=r(1937),i=r(6043);r.o(i,"IJsonRpcProvider")&&r.d(e,{IJsonRpcProvider:function(){return i.IJsonRpcProvider}}),r.o(i,"isHttpUrl")&&r.d(e,{isHttpUrl:function(){return i.isHttpUrl}}),r.o(i,"isJsonRpcError")&&r.d(e,{isJsonRpcError:function(){return i.isJsonRpcError}}),r.o(i,"isJsonRpcRequest")&&r.d(e,{isJsonRpcRequest:function(){return i.isJsonRpcRequest}}),r.o(i,"isJsonRpcResponse")&&r.d(e,{isJsonRpcResponse:function(){return i.isJsonRpcResponse}}),r.o(i,"isJsonRpcResult")&&r.d(e,{isJsonRpcResult:function(){return i.isJsonRpcResult}}),r.o(i,"isLocalhostUrl")&&r.d(e,{isLocalhostUrl:function(){return i.isLocalhostUrl}}),r.o(i,"isReactNative")&&r.d(e,{isReactNative:function(){return i.isReactNative}}),r.o(i,"isWsUrl")&&r.d(e,{isWsUrl:function(){return i.isWsUrl}});var c=r(6119),a=r(4733)},6043:(t,e,r)=>{"use strict";r.d(e,{IJsonRpcProvider:()=>n.IJsonRpcProvider});var n=r(5885);r.o(n,"isHttpUrl")&&r.d(e,{isHttpUrl:function(){return n.isHttpUrl}}),r.o(n,"isJsonRpcError")&&r.d(e,{isJsonRpcError:function(){return n.isJsonRpcError}}),r.o(n,"isJsonRpcRequest")&&r.d(e,{isJsonRpcRequest:function(){return n.isJsonRpcRequest}}),r.o(n,"isJsonRpcResponse")&&r.d(e,{isJsonRpcResponse:function(){return n.isJsonRpcResponse}}),r.o(n,"isJsonRpcResult")&&r.d(e,{isJsonRpcResult:function(){return n.isJsonRpcResult}}),r.o(n,"isLocalhostUrl")&&r.d(e,{isLocalhostUrl:function(){return n.isLocalhostUrl}}),r.o(n,"isReactNative")&&r.d(e,{isReactNative:function(){return n.isReactNative}}),r.o(n,"isWsUrl")&&r.d(e,{isWsUrl:function(){return n.isWsUrl}})},6119:(t,e,r)=>{"use strict";function n(t,e){const r=function(t){const e=t.match(new RegExp(/^\w+:/,"gi"));if(e&&e.length)return e[0]}(t);return void 0!==r&&new RegExp(e).test(r)}function s(t){return n(t,"^https?:")}function o(t){return n(t,"^wss?:")}function i(t){return new RegExp("wss?://localhost(:d{2,5})?").test(t)}r.d(e,{JF:()=>i,UZ:()=>o,jK:()=>s})},4733:(t,e,r)=>{"use strict";function n(t){return"object"==typeof t&&"id"in t&&"jsonrpc"in t&&"2.0"===t.jsonrpc}function s(t){return n(t)&&"method"in t}function o(t){return n(t)&&(i(t)||c(t))}function i(t){return"result"in t}function c(t){return"error"in t}r.d(e,{DW:()=>s,jg:()=>c,k4:()=>i,u:()=>o})},5094:(t,e,r)=>{"use strict";function n(t){if("string"!=typeof t)throw new Error("Cannot safe json parse value of type "+typeof t);try{return JSON.parse(t)}catch(e){return t}}function s(t){return"string"==typeof t?t:JSON.stringify(t)}r.d(e,{D:()=>n,u:()=>s})},4098:function(t,e){var r="undefined"!=typeof self?self:this,n=function(){function t(){this.fetch=!1,this.DOMException=r.DOMException}return t.prototype=r,new t}();!function(t){!function(e){var r="URLSearchParams"in t,n="Symbol"in t&&"iterator"in Symbol,s="FileReader"in t&&"Blob"in t&&function(){try{return new Blob,!0}catch(t){return!1}}(),o="FormData"in t,i="ArrayBuffer"in t;if(i)var c=["[object Int8Array]","[object Uint8Array]","[object Uint8ClampedArray]","[object Int16Array]","[object Uint16Array]","[object Int32Array]","[object Uint32Array]","[object Float32Array]","[object Float64Array]"],a=ArrayBuffer.isView||function(t){return t&&c.indexOf(Object.prototype.toString.call(t))>-1};function u(t){if("string"!=typeof t&&(t=String(t)),/[^a-z0-9\-#$%&'*+.^_`|~]/i.test(t))throw new TypeError("Invalid character in header field name");return t.toLowerCase()}function p(t){return"string"!=typeof t&&(t=String(t)),t}function d(t){var e={next:function(){var e=t.shift();return{done:void 0===e,value:e}}};return n&&(e[Symbol.iterator]=function(){return e}),e}function l(t){this.map={},t instanceof l?t.forEach((function(t,e){this.append(e,t)}),this):Array.isArray(t)?t.forEach((function(t){this.append(t[0],t[1])}),this):t&&Object.getOwnPropertyNames(t).forEach((function(e){this.append(e,t[e])}),this)}function h(t){if(t.bodyUsed)return Promise.reject(new TypeError("Already read"));t.bodyUsed=!0}function f(t){return new Promise((function(e,r){t.onload=function(){e(t.result)},t.onerror=function(){r(t.error)}}))}function R(t){var e=new FileReader,r=f(e);return e.readAsArrayBuffer(t),r}function y(t){if(t.slice)return t.slice(0);var e=new Uint8Array(t.byteLength);return e.set(new Uint8Array(t)),e.buffer}function v(){return this.bodyUsed=!1,this._initBody=function(t){var e;this._bodyInit=t,t?"string"==typeof t?this._bodyText=t:s&&Blob.prototype.isPrototypeOf(t)?this._bodyBlob=t:o&&FormData.prototype.isPrototypeOf(t)?this._bodyFormData=t:r&&URLSearchParams.prototype.isPrototypeOf(t)?this._bodyText=t.toString():i&&s&&(e=t)&&DataView.prototype.isPrototypeOf(e)?(this._bodyArrayBuffer=y(t.buffer),this._bodyInit=new Blob([this._bodyArrayBuffer])):i&&(ArrayBuffer.prototype.isPrototypeOf(t)||a(t))?this._bodyArrayBuffer=y(t):this._bodyText=t=Object.prototype.toString.call(t):this._bodyText="",this.headers.get("content-type")||("string"==typeof t?this.headers.set("content-type","text/plain;charset=UTF-8"):this._bodyBlob&&this._bodyBlob.type?this.headers.set("content-type",this._bodyBlob.type):r&&URLSearchParams.prototype.isPrototypeOf(t)&&this.headers.set("content-type","application/x-www-form-urlencoded;charset=UTF-8"))},s&&(this.blob=function(){var t=h(this);if(t)return t;if(this._bodyBlob)return Promise.resolve(this._bodyBlob);if(this._bodyArrayBuffer)return Promise.resolve(new Blob([this._bodyArrayBuffer]));if(this._bodyFormData)throw new Error("could not read FormData body as blob");return Promise.resolve(new Blob([this._bodyText]))},this.arrayBuffer=function(){return this._bodyArrayBuffer?h(this)||Promise.resolve(this._bodyArrayBuffer):this.blob().then(R)}),this.text=function(){var t,e,r,n=h(this);if(n)return n;if(this._bodyBlob)return t=this._bodyBlob,r=f(e=new FileReader),e.readAsText(t),r;if(this._bodyArrayBuffer)return Promise.resolve(function(t){for(var e=new Uint8Array(t),r=new Array(e.length),n=0;n<e.length;n++)r[n]=String.fromCharCode(e[n]);return r.join("")}(this._bodyArrayBuffer));if(this._bodyFormData)throw new Error("could not read FormData body as text");return Promise.resolve(this._bodyText)},o&&(this.formData=function(){return this.text().then(g)}),this.json=function(){return this.text().then(JSON.parse)},this}l.prototype.append=function(t,e){t=u(t),e=p(e);var r=this.map[t];this.map[t]=r?r+", "+e:e},l.prototype.delete=function(t){delete this.map[u(t)]},l.prototype.get=function(t){return t=u(t),this.has(t)?this.map[t]:null},l.prototype.has=function(t){return this.map.hasOwnProperty(u(t))},l.prototype.set=function(t,e){this.map[u(t)]=p(e)},l.prototype.forEach=function(t,e){for(var r in this.map)this.map.hasOwnProperty(r)&&t.call(e,this.map[r],r,this)},l.prototype.keys=function(){var t=[];return this.forEach((function(e,r){t.push(r)})),d(t)},l.prototype.values=function(){var t=[];return this.forEach((function(e){t.push(e)})),d(t)},l.prototype.entries=function(){var t=[];return this.forEach((function(e,r){t.push([r,e])})),d(t)},n&&(l.prototype[Symbol.iterator]=l.prototype.entries);var m=["DELETE","GET","HEAD","OPTIONS","POST","PUT"];function b(t,e){var r,n,s=(e=e||{}).body;if(t instanceof b){if(t.bodyUsed)throw new TypeError("Already read");this.url=t.url,this.credentials=t.credentials,e.headers||(this.headers=new l(t.headers)),this.method=t.method,this.mode=t.mode,this.signal=t.signal,s||null==t._bodyInit||(s=t._bodyInit,t.bodyUsed=!0)}else this.url=String(t);if(this.credentials=e.credentials||this.credentials||"same-origin",!e.headers&&this.headers||(this.headers=new l(e.headers)),this.method=(n=(r=e.method||this.method||"GET").toUpperCase(),m.indexOf(n)>-1?n:r),this.mode=e.mode||this.mode||null,this.signal=e.signal||this.signal,this.referrer=null,("GET"===this.method||"HEAD"===this.method)&&s)throw new TypeError("Body not allowed for GET or HEAD requests");this._initBody(s)}function g(t){var e=new FormData;return t.trim().split("&").forEach((function(t){if(t){var r=t.split("="),n=r.shift().replace(/\+/g," "),s=r.join("=").replace(/\+/g," ");e.append(decodeURIComponent(n),decodeURIComponent(s))}})),e}function J(t,e){e||(e={}),this.type="default",this.status=void 0===e.status?200:e.status,this.ok=this.status>=200&&this.status<300,this.statusText="statusText"in e?e.statusText:"OK",this.headers=new l(e.headers),this.url=e.url||"",this._initBody(t)}b.prototype.clone=function(){return new b(this,{body:this._bodyInit})},v.call(b.prototype),v.call(J.prototype),J.prototype.clone=function(){return new J(this._bodyInit,{status:this.status,statusText:this.statusText,headers:new l(this.headers),url:this.url})},J.error=function(){var t=new J(null,{status:0,statusText:""});return t.type="error",t};var E=[301,302,303,307,308];J.redirect=function(t,e){if(-1===E.indexOf(e))throw new RangeError("Invalid status code");return new J(null,{status:e,headers:{location:t}})},e.DOMException=t.DOMException;try{new e.DOMException}catch(t){e.DOMException=function(t,e){this.message=t,this.name=e;var r=Error(t);this.stack=r.stack},e.DOMException.prototype=Object.create(Error.prototype),e.DOMException.prototype.constructor=e.DOMException}function w(t,r){return new Promise((function(n,o){var i=new b(t,r);if(i.signal&&i.signal.aborted)return o(new e.DOMException("Aborted","AbortError"));var c=new XMLHttpRequest;function a(){c.abort()}c.onload=function(){var t,e,r={status:c.status,statusText:c.statusText,headers:(t=c.getAllResponseHeaders()||"",e=new l,t.replace(/\r?\n[\t ]+/g," ").split(/\r?\n/).forEach((function(t){var r=t.split(":"),n=r.shift().trim();if(n){var s=r.join(":").trim();e.append(n,s)}})),e)};r.url="responseURL"in c?c.responseURL:r.headers.get("X-Request-URL");var s="response"in c?c.response:c.responseText;n(new J(s,r))},c.onerror=function(){o(new TypeError("Network request failed"))},c.ontimeout=function(){o(new TypeError("Network request failed"))},c.onabort=function(){o(new e.DOMException("Aborted","AbortError"))},c.open(i.method,i.url,!0),"include"===i.credentials?c.withCredentials=!0:"omit"===i.credentials&&(c.withCredentials=!1),"responseType"in c&&s&&(c.responseType="blob"),i.headers.forEach((function(t,e){c.setRequestHeader(e,t)})),i.signal&&(i.signal.addEventListener("abort",a),c.onreadystatechange=function(){4===c.readyState&&i.signal.removeEventListener("abort",a)}),c.send(void 0===i._bodyInit?null:i._bodyInit)}))}w.polyfill=!0,t.fetch||(t.fetch=w,t.Headers=l,t.Request=b,t.Response=J),e.Headers=l,e.Request=b,e.Response=J,e.fetch=w,Object.defineProperty(e,"__esModule",{value:!0})}({})}(n),n.fetch.ponyfill=!0,delete n.fetch.polyfill;var s=n;(e=s.fetch).default=s.fetch,e.fetch=s.fetch,e.Headers=s.Headers,e.Request=s.Request,e.Response=s.Response,t.exports=e},4020:t=>{"use strict";var e="%[a-f0-9]{2}",r=new RegExp("("+e+")|([^%]+?)","gi"),n=new RegExp("("+e+")+","gi");function s(t,e){try{return[decodeURIComponent(t.join(""))]}catch(t){}if(1===t.length)return t;e=e||1;var r=t.slice(0,e),n=t.slice(e);return Array.prototype.concat.call([],s(r),s(n))}function o(t){try{return decodeURIComponent(t)}catch(o){for(var e=t.match(r)||[],n=1;n<e.length;n++)e=(t=s(e,n).join("")).match(r)||[];return t}}t.exports=function(t){if("string"!=typeof t)throw new TypeError("Expected `encodedURI` to be of type `string`, got `"+typeof t+"`");try{return t=t.replace(/\+/g," "),decodeURIComponent(t)}catch(e){return function(t){for(var e={"%FE%FF":"��","%FF%FE":"��"},r=n.exec(t);r;){try{e[r[0]]=decodeURIComponent(r[0])}catch(t){var s=o(r[0]);s!==r[0]&&(e[r[0]]=s)}r=n.exec(t)}e["%C2"]="�";for(var i=Object.keys(e),c=0;c<i.length;c++){var a=i[c];t=t.replace(new RegExp(a,"g"),e[a])}return t}(t)}}},500:t=>{"use strict";t.exports=(t,e)=>{if("string"!=typeof t||"string"!=typeof e)throw new TypeError("Expected the arguments to be of type `string`");if(""===e)return[t];const r=t.indexOf(e);return-1===r?[t]:[t.slice(0,r),t.slice(r+e.length)]}},610:t=>{"use strict";t.exports=t=>encodeURIComponent(t).replace(/[!'()*]/g,(t=>`%${t.charCodeAt(0).toString(16).toUpperCase()}`))}}]);
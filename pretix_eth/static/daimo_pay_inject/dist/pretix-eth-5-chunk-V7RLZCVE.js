import{t as Vt}from"./pretix-eth-5-chunk-MCYRL7OX.js";import{a as se,b as Pe}from"./pretix-eth-5-chunk-TH6XAEVV.js";import{qa as vt}from"./pretix-eth-5-chunk-ZCL5HT24.js";import{a as Kt}from"./pretix-eth-5-chunk-64QJEAS7.js";import{f as qt}from"./pretix-eth-5-chunk-BIK4PATU.js";var W={WC_NAME_SUFFIX:".reown.id",WC_NAME_SUFFIX_LEGACY:".wcn.id",BLOCKCHAIN_API_RPC_URL:"https://rpc.walletconnect.org",PULSE_API_URL:"https://pulse.walletconnect.org",W3M_API_URL:"https://api.web3modal.org",CONNECTOR_ID:{WALLET_CONNECT:"walletConnect",INJECTED:"injected",WALLET_STANDARD:"announced",COINBASE:"coinbaseWallet",COINBASE_SDK:"coinbaseWalletSDK",SAFE:"safe",LEDGER:"ledger",OKX:"okx",EIP6963:"eip6963",AUTH:"ID_AUTH"},CONNECTOR_NAMES:{AUTH:"Auth"},AUTH_CONNECTOR_SUPPORTED_CHAINS:["eip155","solana"],LIMITS:{PENDING_TRANSACTIONS:99},CHAIN:{EVM:"eip155",SOLANA:"solana",POLKADOT:"polkadot",BITCOIN:"bip122"},CHAIN_NAME_MAP:{eip155:"EVM Networks",solana:"Solana",polkadot:"Polkadot",bip122:"Bitcoin",cosmos:"Cosmos"},ADAPTER_TYPES:{BITCOIN:"bitcoin",SOLANA:"solana",WAGMI:"wagmi",ETHERS:"ethers",ETHERS5:"ethers5"},USDT_CONTRACT_ADDRESSES:["0xdac17f958d2ee523a2206206994597c13d831ec7","0xc2132d05d31c914a87c6611c10748aeb04b58e8f","0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7","0x919C1c267BC06a7039e03fcc2eF738525769109c","0x48065fbBE25f71C9282ddf5e1cD6D6A887483D5e","0x55d398326f99059fF775485246999027B3197955","0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9"],HTTP_STATUS_CODES:{SERVICE_UNAVAILABLE:503,FORBIDDEN:403},UNSUPPORTED_NETWORK_NAME:"Unknown Network",SECURE_SITE_SDK_ORIGIN:(typeof process<"u"&&typeof process.env<"u"?process.env.NEXT_PUBLIC_SECURE_SITE_ORIGIN:void 0)||"https://secure.walletconnect.org"};var st={caipNetworkIdToNumber(e){return e?Number(e.split(":")[1]):void 0},parseEvmChainId(e){return typeof e=="string"?this.caipNetworkIdToNumber(e):e},getNetworksByNamespace(e,t){return e?.filter(r=>r.chainNamespace===t)||[]},getFirstNetworkByNamespace(e,t){return this.getNetworksByNamespace(e,t)[0]},getNetworkNameByCaipNetworkId(e,t){if(!t)return;let r=e.find(o=>o.caipNetworkId===t);if(r)return r.name;let[n]=t.split(":");return W.CHAIN_NAME_MAP?.[n]||void 0}};var Gt=20,zt=1,Re=1e6,At=1e6,Yt=-7,Xt=21,Jt=!1,Ve="[big.js] ",Oe=Ve+"Invalid ",et=Oe+"decimal places",Qt=Oe+"rounding mode",St=Ve+"Division by zero",D={},me=void 0,Zt=/^-?(\d+(\.\d*)?|\.\d+)(e[+-]?\d+)?$/i;function Nt(){function e(t){var r=this;if(!(r instanceof e))return t===me?Nt():new e(t);if(t instanceof e)r.s=t.s,r.e=t.e,r.c=t.c.slice();else{if(typeof t!="string"){if(e.strict===!0&&typeof t!="bigint")throw TypeError(Oe+"value");t=t===0&&1/t<0?"-0":String(t)}er(r,t)}r.constructor=e}return e.prototype=D,e.DP=Gt,e.RM=zt,e.NE=Yt,e.PE=Xt,e.strict=Jt,e.roundDown=0,e.roundHalfUp=1,e.roundHalfEven=2,e.roundUp=3,e}function er(e,t){var r,n,o;if(!Zt.test(t))throw Error(Oe+"number");for(e.s=t.charAt(0)=="-"?(t=t.slice(1),-1):1,(r=t.indexOf("."))>-1&&(t=t.replace(".","")),(n=t.search(/e/i))>0?(r<0&&(r=n),r+=+t.slice(n+1),t=t.substring(0,n)):r<0&&(r=t.length),o=t.length,n=0;n<o&&t.charAt(n)=="0";)++n;if(n==o)e.c=[e.e=0];else{for(;o>0&&t.charAt(--o)=="0";);for(e.e=r-n-1,e.c=[],r=0;n<=o;)e.c[r++]=+t.charAt(n++)}return e}function ke(e,t,r,n){var o=e.c;if(r===me&&(r=e.constructor.RM),r!==0&&r!==1&&r!==2&&r!==3)throw Error(Qt);if(t<1)n=r===3&&(n||!!o[0])||t===0&&(r===1&&o[0]>=5||r===2&&(o[0]>5||o[0]===5&&(n||o[1]!==me))),o.length=1,n?(e.e=e.e-t+1,o[0]=1):o[0]=e.e=0;else if(t<o.length){if(n=r===1&&o[t]>=5||r===2&&(o[t]>5||o[t]===5&&(n||o[t+1]!==me||o[t-1]&1))||r===3&&(n||!!o[0]),o.length=t,n){for(;++o[--t]>9;)if(o[t]=0,t===0){++e.e,o.unshift(1);break}}for(t=o.length;!o[--t];)o.pop()}return e}function xe(e,t,r){var n=e.e,o=e.c.join(""),s=o.length;if(t)o=o.charAt(0)+(s>1?"."+o.slice(1):"")+(n<0?"e":"e+")+n;else if(n<0){for(;++n;)o="0"+o;o="0."+o}else if(n>0)if(++n>s)for(n-=s;n--;)o+="0";else n<s&&(o=o.slice(0,n)+"."+o.slice(n));else s>1&&(o=o.charAt(0)+"."+o.slice(1));return e.s<0&&r?"-"+o:o}D.abs=function(){var e=new this.constructor(this);return e.s=1,e};D.cmp=function(e){var t,r=this,n=r.c,o=(e=new r.constructor(e)).c,s=r.s,a=e.s,c=r.e,u=e.e;if(!n[0]||!o[0])return n[0]?s:o[0]?-a:0;if(s!=a)return s;if(t=s<0,c!=u)return c>u^t?1:-1;for(a=(c=n.length)<(u=o.length)?c:u,s=-1;++s<a;)if(n[s]!=o[s])return n[s]>o[s]^t?1:-1;return c==u?0:c>u^t?1:-1};D.div=function(e){var t=this,r=t.constructor,n=t.c,o=(e=new r(e)).c,s=t.s==e.s?1:-1,a=r.DP;if(a!==~~a||a<0||a>Re)throw Error(et);if(!o[0])throw Error(St);if(!n[0])return e.s=s,e.c=[e.e=0],e;var c,u,l,d,b,K=o.slice(),J=c=o.length,fe=n.length,L=n.slice(0,c),X=L.length,V=e,Ie=V.c=[],Ee=0,Te=a+(V.e=t.e-e.e)+1;for(V.s=s,s=Te<0?0:Te,K.unshift(0);X++<c;)L.push(0);do{for(l=0;l<10;l++){if(c!=(X=L.length))d=c>X?1:-1;else for(b=-1,d=0;++b<c;)if(o[b]!=L[b]){d=o[b]>L[b]?1:-1;break}if(d<0){for(u=X==c?o:K;X;){if(L[--X]<u[X]){for(b=X;b&&!L[--b];)L[b]=9;--L[b],L[X]+=10}L[X]-=u[X]}for(;!L[0];)L.shift()}else break}Ie[Ee++]=d?l:++l,L[0]&&d?L[X]=n[J]||0:L=[n[J]]}while((J++<fe||L[0]!==me)&&s--);return!Ie[0]&&Ee!=1&&(Ie.shift(),V.e--,Te--),Ee>Te&&ke(V,Te,r.RM,L[0]!==me),V};D.eq=function(e){return this.cmp(e)===0};D.gt=function(e){return this.cmp(e)>0};D.gte=function(e){return this.cmp(e)>-1};D.lt=function(e){return this.cmp(e)<0};D.lte=function(e){return this.cmp(e)<1};D.minus=D.sub=function(e){var t,r,n,o,s=this,a=s.constructor,c=s.s,u=(e=new a(e)).s;if(c!=u)return e.s=-u,s.plus(e);var l=s.c.slice(),d=s.e,b=e.c,K=e.e;if(!l[0]||!b[0])return b[0]?e.s=-u:l[0]?e=new a(s):e.s=1,e;if(c=d-K){for((o=c<0)?(c=-c,n=l):(K=d,n=b),n.reverse(),u=c;u--;)n.push(0);n.reverse()}else for(r=((o=l.length<b.length)?l:b).length,c=u=0;u<r;u++)if(l[u]!=b[u]){o=l[u]<b[u];break}if(o&&(n=l,l=b,b=n,e.s=-e.s),(u=(r=b.length)-(t=l.length))>0)for(;u--;)l[t++]=0;for(u=t;r>c;){if(l[--r]<b[r]){for(t=r;t&&!l[--t];)l[t]=9;--l[t],l[r]+=10}l[r]-=b[r]}for(;l[--u]===0;)l.pop();for(;l[0]===0;)l.shift(),--K;return l[0]||(e.s=1,l=[K=0]),e.c=l,e.e=K,e};D.mod=function(e){var t,r=this,n=r.constructor,o=r.s,s=(e=new n(e)).s;if(!e.c[0])throw Error(St);return r.s=e.s=1,t=e.cmp(r)==1,r.s=o,e.s=s,t?new n(r):(o=n.DP,s=n.RM,n.DP=n.RM=0,r=r.div(e),n.DP=o,n.RM=s,this.minus(r.times(e)))};D.neg=function(){var e=new this.constructor(this);return e.s=-e.s,e};D.plus=D.add=function(e){var t,r,n,o=this,s=o.constructor;if(e=new s(e),o.s!=e.s)return e.s=-e.s,o.minus(e);var a=o.e,c=o.c,u=e.e,l=e.c;if(!c[0]||!l[0])return l[0]||(c[0]?e=new s(o):e.s=o.s),e;if(c=c.slice(),t=a-u){for(t>0?(u=a,n=l):(t=-t,n=c),n.reverse();t--;)n.push(0);n.reverse()}for(c.length-l.length<0&&(n=l,l=c,c=n),t=l.length,r=0;t;c[t]%=10)r=(c[--t]=c[t]+l[t]+r)/10|0;for(r&&(c.unshift(r),++u),t=c.length;c[--t]===0;)c.pop();return e.c=c,e.e=u,e};D.pow=function(e){var t=this,r=new t.constructor("1"),n=r,o=e<0;if(e!==~~e||e<-At||e>At)throw Error(Oe+"exponent");for(o&&(e=-e);e&1&&(n=n.times(t)),e>>=1,!!e;)t=t.times(t);return o?r.div(n):n};D.prec=function(e,t){if(e!==~~e||e<1||e>Re)throw Error(Oe+"precision");return ke(new this.constructor(this),e,t)};D.round=function(e,t){if(e===me)e=0;else if(e!==~~e||e<-Re||e>Re)throw Error(et);return ke(new this.constructor(this),e+this.e+1,t)};D.sqrt=function(){var e,t,r,n=this,o=n.constructor,s=n.s,a=n.e,c=new o("0.5");if(!n.c[0])return new o(n);if(s<0)throw Error(Ve+"No square root");s=Math.sqrt(+xe(n,!0,!0)),s===0||s===1/0?(t=n.c.join(""),t.length+a&1||(t+="0"),s=Math.sqrt(t),a=((a+1)/2|0)-(a<0||a&1),e=new o((s==1/0?"5e":(s=s.toExponential()).slice(0,s.indexOf("e")+1))+a)):e=new o(s+""),a=e.e+(o.DP+=4);do r=e,e=c.times(r.plus(n.div(r)));while(r.c.slice(0,a).join("")!==e.c.slice(0,a).join(""));return ke(e,(o.DP-=4)+e.e+1,o.RM)};D.times=D.mul=function(e){var t,r=this,n=r.constructor,o=r.c,s=(e=new n(e)).c,a=o.length,c=s.length,u=r.e,l=e.e;if(e.s=r.s==e.s?1:-1,!o[0]||!s[0])return e.c=[e.e=0],e;for(e.e=u+l,a<c&&(t=o,o=s,s=t,l=a,a=c,c=l),t=new Array(l=a+c);l--;)t[l]=0;for(u=c;u--;){for(c=0,l=a+u;l>u;)c=t[l]+s[u]*o[l-u-1]+c,t[l--]=c%10,c=c/10|0;t[l]=c}for(c?++e.e:t.shift(),u=t.length;!t[--u];)t.pop();return e.c=t,e};D.toExponential=function(e,t){var r=this,n=r.c[0];if(e!==me){if(e!==~~e||e<0||e>Re)throw Error(et);for(r=ke(new r.constructor(r),++e,t);r.c.length<e;)r.c.push(0)}return xe(r,!0,!!n)};D.toFixed=function(e,t){var r=this,n=r.c[0];if(e!==me){if(e!==~~e||e<0||e>Re)throw Error(et);for(r=ke(new r.constructor(r),e+r.e+1,t),e=e+r.e+1;r.c.length<e;)r.c.push(0)}return xe(r,!1,!!n)};D[Symbol.for("nodejs.util.inspect.custom")]=D.toJSON=D.toString=function(){var e=this,t=e.constructor;return xe(e,e.e<=t.NE||e.e>=t.PE,!!e.c[0])};D.toNumber=function(){var e=+xe(this,!0,!0);if(this.constructor.strict===!0&&!this.eq(e.toString()))throw Error(Ve+"Imprecise conversion");return e};D.toPrecision=function(e,t){var r=this,n=r.constructor,o=r.c[0];if(e!==me){if(e!==~~e||e<1||e>Re)throw Error(Oe+"precision");for(r=ke(new n(r),e,t);r.c.length<e;)r.c.push(0)}return xe(r,e<=r.e||r.e<=n.NE||r.e>=n.PE,!!o)};D.valueOf=function(){var e=this,t=e.constructor;if(t.strict===!0)throw Error(Ve+"valueOf disallowed");return xe(e,e.e<=t.NE||e.e>=t.PE,!0)};var tr=Nt(),Be=tr;var it={bigNumber(e){return e?new Be(e):new Be(0)},multiply(e,t){if(e===void 0||t===void 0)return new Be(0);let r=new Be(e),n=new Be(t);return r.times(n)},formatNumberToLocalString(e,t=2){return e===void 0?"0.00":typeof e=="number"?e.toLocaleString("en-US",{maximumFractionDigits:t,minimumFractionDigits:t}):parseFloat(e).toLocaleString("en-US",{maximumFractionDigits:t,minimumFractionDigits:t})},parseLocalStringToNumber(e){return e===void 0?0:parseFloat(e.replace(/,/gu,""))}};var yt=[{type:"function",name:"transfer",stateMutability:"nonpayable",inputs:[{name:"_to",type:"address"},{name:"_value",type:"uint256"}],outputs:[{name:"",type:"bool"}]},{type:"function",name:"transferFrom",stateMutability:"nonpayable",inputs:[{name:"_from",type:"address"},{name:"_to",type:"address"},{name:"_value",type:"uint256"}],outputs:[{name:"",type:"bool"}]}];var _t=[{type:"function",name:"approve",stateMutability:"nonpayable",inputs:[{name:"spender",type:"address"},{name:"amount",type:"uint256"}],outputs:[{type:"bool"}]}];var It=[{type:"function",name:"transfer",stateMutability:"nonpayable",inputs:[{name:"recipient",type:"address"},{name:"amount",type:"uint256"}],outputs:[]},{type:"function",name:"transferFrom",stateMutability:"nonpayable",inputs:[{name:"sender",type:"address"},{name:"recipient",type:"address"},{name:"amount",type:"uint256"}],outputs:[{name:"",type:"bool"}]}];var at={getERC20Abi:e=>W.USDT_CONTRACT_ADDRESSES.includes(e)?It:yt,getSwapAbi:()=>_t};var rr={validateCaipAddress(e){if(e.split(":")?.length!==3)throw new Error("Invalid CAIP Address");return e},parseCaipAddress(e){let t=e.split(":");if(t.length!==3)throw new Error(`Invalid CAIP-10 address: ${e}`);let[r,n,o]=t;if(!r||!n||!o)throw new Error(`Invalid CAIP-10 address: ${e}`);return{chainNamespace:r,chainId:n,address:o}},parseCaipNetworkId(e){let t=e.split(":");if(t.length!==2)throw new Error(`Invalid CAIP-2 network id: ${e}`);let[r,n]=t;if(!r||!n)throw new Error(`Invalid CAIP-2 network id: ${e}`);return{chainNamespace:r,chainId:n}}};var y={WALLET_ID:"@appkit/wallet_id",WALLET_NAME:"@appkit/wallet_name",SOLANA_WALLET:"@appkit/solana_wallet",SOLANA_CAIP_CHAIN:"@appkit/solana_caip_chain",ACTIVE_CAIP_NETWORK_ID:"@appkit/active_caip_network_id",CONNECTED_SOCIAL:"@appkit/connected_social",CONNECTED_SOCIAL_USERNAME:"@appkit-wallet/SOCIAL_USERNAME",RECENT_WALLETS:"@appkit/recent_wallets",DEEPLINK_CHOICE:"WALLETCONNECT_DEEPLINK_CHOICE",ACTIVE_NAMESPACE:"@appkit/active_namespace",CONNECTED_NAMESPACES:"@appkit/connected_namespaces",CONNECTION_STATUS:"@appkit/connection_status",SIWX_AUTH_TOKEN:"@appkit/siwx-auth-token",SIWX_NONCE_TOKEN:"@appkit/siwx-nonce-token",TELEGRAM_SOCIAL_PROVIDER:"@appkit/social_provider",NATIVE_BALANCE_CACHE:"@appkit/native_balance_cache",PORTFOLIO_CACHE:"@appkit/portfolio_cache",ENS_CACHE:"@appkit/ens_cache",IDENTITY_CACHE:"@appkit/identity_cache",PREFERRED_ACCOUNT_TYPES:"@appkit/preferred_account_types",CONNECTIONS:"@appkit/connections"};function Ge(e){if(!e)throw new Error("Namespace is required for CONNECTED_CONNECTOR_ID");return`@appkit/${e}:connected_connector_id`}var A={setItem(e,t){Ue()&&t!==void 0&&localStorage.setItem(e,t)},getItem(e){if(Ue())return localStorage.getItem(e)||void 0},removeItem(e){Ue()&&localStorage.removeItem(e)},clear(){Ue()&&localStorage.clear()}};function Ue(){return typeof window<"u"&&typeof localStorage<"u"}function ie(e,t){return t==="light"?{"--w3m-accent":e?.["--w3m-accent"]||"hsla(231, 100%, 70%, 1)","--w3m-background":"#fff"}:{"--w3m-accent":e?.["--w3m-accent"]||"hsla(230, 100%, 67%, 1)","--w3m-background":"#121313"}}var f={cacheExpiry:{portfolio:3e4,nativeBalance:3e4,ens:3e5,identity:3e5},isCacheExpired(e,t){return Date.now()-e>t},getActiveNetworkProps(){let e=f.getActiveNamespace(),t=f.getActiveCaipNetworkId(),r=t?t.split(":")[1]:void 0,n=r?isNaN(Number(r))?r:Number(r):void 0;return{namespace:e,caipNetworkId:t,chainId:n}},setWalletConnectDeepLink({name:e,href:t}){try{A.setItem(y.DEEPLINK_CHOICE,JSON.stringify({href:t,name:e}))}catch{console.info("Unable to set WalletConnect deep link")}},getWalletConnectDeepLink(){try{let e=A.getItem(y.DEEPLINK_CHOICE);if(e)return JSON.parse(e)}catch{console.info("Unable to get WalletConnect deep link")}},deleteWalletConnectDeepLink(){try{A.removeItem(y.DEEPLINK_CHOICE)}catch{console.info("Unable to delete WalletConnect deep link")}},setActiveNamespace(e){try{A.setItem(y.ACTIVE_NAMESPACE,e)}catch{console.info("Unable to set active namespace")}},setActiveCaipNetworkId(e){try{A.setItem(y.ACTIVE_CAIP_NETWORK_ID,e),f.setActiveNamespace(e.split(":")[0])}catch{console.info("Unable to set active caip network id")}},getActiveCaipNetworkId(){try{return A.getItem(y.ACTIVE_CAIP_NETWORK_ID)}catch{console.info("Unable to get active caip network id");return}},deleteActiveCaipNetworkId(){try{A.removeItem(y.ACTIVE_CAIP_NETWORK_ID)}catch{console.info("Unable to delete active caip network id")}},deleteConnectedConnectorId(e){try{let t=Ge(e);A.removeItem(t)}catch{console.info("Unable to delete connected connector id")}},setAppKitRecent(e){try{let t=f.getRecentWallets();t.find(n=>n.id===e.id)||(t.unshift(e),t.length>2&&t.pop(),A.setItem(y.RECENT_WALLETS,JSON.stringify(t)))}catch{console.info("Unable to set AppKit recent")}},getRecentWallets(){try{let e=A.getItem(y.RECENT_WALLETS);return e?JSON.parse(e):[]}catch{console.info("Unable to get AppKit recent")}return[]},setConnectedConnectorId(e,t){try{let r=Ge(e);A.setItem(r,t)}catch{console.info("Unable to set Connected Connector Id")}},getActiveNamespace(){try{return A.getItem(y.ACTIVE_NAMESPACE)}catch{console.info("Unable to get active namespace")}},getConnectedConnectorId(e){if(e)try{let t=Ge(e);return A.getItem(t)}catch{console.info("Unable to get connected connector id in namespace ",e)}},setConnectedSocialProvider(e){try{A.setItem(y.CONNECTED_SOCIAL,e)}catch{console.info("Unable to set connected social provider")}},getConnectedSocialProvider(){try{return A.getItem(y.CONNECTED_SOCIAL)}catch{console.info("Unable to get connected social provider")}},deleteConnectedSocialProvider(){try{A.removeItem(y.CONNECTED_SOCIAL)}catch{console.info("Unable to delete connected social provider")}},getConnectedSocialUsername(){try{return A.getItem(y.CONNECTED_SOCIAL_USERNAME)}catch{console.info("Unable to get connected social username")}},getStoredActiveCaipNetworkId(){return A.getItem(y.ACTIVE_CAIP_NETWORK_ID)?.split(":")?.[1]},setConnectionStatus(e){try{A.setItem(y.CONNECTION_STATUS,e)}catch{console.info("Unable to set connection status")}},getConnectionStatus(){try{return A.getItem(y.CONNECTION_STATUS)}catch{return}},getConnectedNamespaces(){try{let e=A.getItem(y.CONNECTED_NAMESPACES);return e?.length?e.split(","):[]}catch{return[]}},setConnectedNamespaces(e){try{let t=Array.from(new Set(e));A.setItem(y.CONNECTED_NAMESPACES,t.join(","))}catch{console.info("Unable to set namespaces in storage")}},addConnectedNamespace(e){try{let t=f.getConnectedNamespaces();t.includes(e)||(t.push(e),f.setConnectedNamespaces(t))}catch{console.info("Unable to add connected namespace")}},removeConnectedNamespace(e){try{let t=f.getConnectedNamespaces(),r=t.indexOf(e);r>-1&&(t.splice(r,1),f.setConnectedNamespaces(t))}catch{console.info("Unable to remove connected namespace")}},getTelegramSocialProvider(){try{return A.getItem(y.TELEGRAM_SOCIAL_PROVIDER)}catch{return console.info("Unable to get telegram social provider"),null}},setTelegramSocialProvider(e){try{A.setItem(y.TELEGRAM_SOCIAL_PROVIDER,e)}catch{console.info("Unable to set telegram social provider")}},removeTelegramSocialProvider(){try{A.removeItem(y.TELEGRAM_SOCIAL_PROVIDER)}catch{console.info("Unable to remove telegram social provider")}},getBalanceCache(){let e={};try{let t=A.getItem(y.PORTFOLIO_CACHE);e=t?JSON.parse(t):{}}catch{console.info("Unable to get balance cache")}return e},removeAddressFromBalanceCache(e){try{let t=f.getBalanceCache();A.setItem(y.PORTFOLIO_CACHE,JSON.stringify({...t,[e]:void 0}))}catch{console.info("Unable to remove address from balance cache",e)}},getBalanceCacheForCaipAddress(e){try{let r=f.getBalanceCache()[e];if(r&&!this.isCacheExpired(r.timestamp,this.cacheExpiry.portfolio))return r.balance;f.removeAddressFromBalanceCache(e)}catch{console.info("Unable to get balance cache for address",e)}},updateBalanceCache(e){try{let t=f.getBalanceCache();t[e.caipAddress]=e,A.setItem(y.PORTFOLIO_CACHE,JSON.stringify(t))}catch{console.info("Unable to update balance cache",e)}},getNativeBalanceCache(){let e={};try{let t=A.getItem(y.NATIVE_BALANCE_CACHE);e=t?JSON.parse(t):{}}catch{console.info("Unable to get balance cache")}return e},removeAddressFromNativeBalanceCache(e){try{let t=f.getBalanceCache();A.setItem(y.NATIVE_BALANCE_CACHE,JSON.stringify({...t,[e]:void 0}))}catch{console.info("Unable to remove address from balance cache",e)}},getNativeBalanceCacheForCaipAddress(e){try{let r=f.getNativeBalanceCache()[e];if(r&&!this.isCacheExpired(r.timestamp,this.cacheExpiry.nativeBalance))return r;console.info("Discarding cache for address",e),f.removeAddressFromBalanceCache(e)}catch{console.info("Unable to get balance cache for address",e)}},updateNativeBalanceCache(e){try{let t=f.getNativeBalanceCache();t[e.caipAddress]=e,A.setItem(y.NATIVE_BALANCE_CACHE,JSON.stringify(t))}catch{console.info("Unable to update balance cache",e)}},getEnsCache(){let e={};try{let t=A.getItem(y.ENS_CACHE);e=t?JSON.parse(t):{}}catch{console.info("Unable to get ens name cache")}return e},getEnsFromCacheForAddress(e){try{let r=f.getEnsCache()[e];if(r&&!this.isCacheExpired(r.timestamp,this.cacheExpiry.ens))return r.ens;f.removeEnsFromCache(e)}catch{console.info("Unable to get ens name from cache",e)}},updateEnsCache(e){try{let t=f.getEnsCache();t[e.address]=e,A.setItem(y.ENS_CACHE,JSON.stringify(t))}catch{console.info("Unable to update ens name cache",e)}},removeEnsFromCache(e){try{let t=f.getEnsCache();A.setItem(y.ENS_CACHE,JSON.stringify({...t,[e]:void 0}))}catch{console.info("Unable to remove ens name from cache",e)}},getIdentityCache(){let e={};try{let t=A.getItem(y.IDENTITY_CACHE);e=t?JSON.parse(t):{}}catch{console.info("Unable to get identity cache")}return e},getIdentityFromCacheForAddress(e){try{let r=f.getIdentityCache()[e];if(r&&!this.isCacheExpired(r.timestamp,this.cacheExpiry.identity))return r.identity;f.removeIdentityFromCache(e)}catch{console.info("Unable to get identity from cache",e)}},updateIdentityCache(e){try{let t=f.getIdentityCache();t[e.address]={identity:e.identity,timestamp:e.timestamp},A.setItem(y.IDENTITY_CACHE,JSON.stringify(t))}catch{console.info("Unable to update identity cache",e)}},removeIdentityFromCache(e){try{let t=f.getIdentityCache();A.setItem(y.IDENTITY_CACHE,JSON.stringify({...t,[e]:void 0}))}catch{console.info("Unable to remove identity from cache",e)}},clearAddressCache(){try{A.removeItem(y.PORTFOLIO_CACHE),A.removeItem(y.NATIVE_BALANCE_CACHE),A.removeItem(y.ENS_CACHE),A.removeItem(y.IDENTITY_CACHE)}catch{console.info("Unable to clear address cache")}},setPreferredAccountTypes(e){try{A.setItem(y.PREFERRED_ACCOUNT_TYPES,JSON.stringify(e))}catch{console.info("Unable to set preferred account types",e)}},getPreferredAccountTypes(){try{let e=A.getItem(y.PREFERRED_ACCOUNT_TYPES);return e?JSON.parse(e):{}}catch{console.info("Unable to get preferred account types")}return{}},setConnections(e,t){try{let r={...f.getConnections(),[t]:e};A.setItem(y.CONNECTIONS,JSON.stringify(r))}catch(r){console.error("Unable to sync connections to storage",r)}},getConnections(){try{let e=A.getItem(y.CONNECTIONS);return e?JSON.parse(e):{}}catch(e){return console.error("Unable to get connections from storage",e),{}}}};var ct=(typeof process<"u"&&typeof process.env<"u"?process.env.NEXT_PUBLIC_SECURE_SITE_ORIGIN:void 0)||"https://secure.walletconnect.org",lt=[{label:"Coinbase",name:"coinbase",feeRange:"1-2%",url:"",supportedChains:["eip155"]},{label:"Meld.io",name:"meld",feeRange:"1-2%",url:"https://meldcrypto.com",supportedChains:["eip155","solana"]}],Tt="WXETMuFUQmqqybHuRkSgxv:25B8LJHSfpG6LVjR2ytU5Cwh7Z4Sch2ocoU",z={FOUR_MINUTES_MS:24e4,TEN_SEC_MS:1e4,FIVE_SEC_MS:5e3,THREE_SEC_MS:3e3,ONE_SEC_MS:1e3,SECURE_SITE:ct,SECURE_SITE_DASHBOARD:`${ct}/dashboard`,SECURE_SITE_FAVICON:`${ct}/images/favicon.png`,RESTRICTED_TIMEZONES:["ASIA/SHANGHAI","ASIA/URUMQI","ASIA/CHONGQING","ASIA/HARBIN","ASIA/KASHGAR","ASIA/MACAU","ASIA/HONG_KONG","ASIA/MACAO","ASIA/BEIJING","ASIA/HARBIN"],WC_COINBASE_PAY_SDK_CHAINS:["ethereum","arbitrum","polygon","berachain","avalanche-c-chain","optimism","celo","base"],WC_COINBASE_PAY_SDK_FALLBACK_CHAIN:"ethereum",WC_COINBASE_PAY_SDK_CHAIN_NAME_MAP:{Ethereum:"ethereum","Arbitrum One":"arbitrum",Polygon:"polygon",Berachain:"berachain",Avalanche:"avalanche-c-chain","OP Mainnet":"optimism",Celo:"celo",Base:"base"},WC_COINBASE_ONRAMP_APP_ID:"bf18c88d-495a-463b-b249-0b9d3656cf5e",SWAP_SUGGESTED_TOKENS:["ETH","UNI","1INCH","AAVE","SOL","ADA","AVAX","DOT","LINK","NITRO","GAIA","MILK","TRX","NEAR","GNO","WBTC","DAI","WETH","USDC","USDT","ARB","BAL","BICO","CRV","ENS","MATIC","OP"],SWAP_POPULAR_TOKENS:["ETH","UNI","1INCH","AAVE","SOL","ADA","AVAX","DOT","LINK","NITRO","GAIA","MILK","TRX","NEAR","GNO","WBTC","DAI","WETH","USDC","USDT","ARB","BAL","BICO","CRV","ENS","MATIC","OP","METAL","DAI","CHAMP","WOLF","SALE","BAL","BUSD","MUST","BTCpx","ROUTE","HEX","WELT","amDAI","VSQ","VISION","AURUM","pSP","SNX","VC","LINK","CHP","amUSDT","SPHERE","FOX","GIDDY","GFC","OMEN","OX_OLD","DE","WNT"],BALANCE_SUPPORTED_CHAINS:["eip155","solana"],SWAP_SUPPORTED_NETWORKS:["eip155:1","eip155:42161","eip155:10","eip155:324","eip155:8453","eip155:56","eip155:137","eip155:100","eip155:43114","eip155:250","eip155:8217","eip155:1313161554"],NAMES_SUPPORTED_CHAIN_NAMESPACES:["eip155"],ONRAMP_SUPPORTED_CHAIN_NAMESPACES:["eip155","solana"],ACTIVITY_ENABLED_CHAIN_NAMESPACES:["eip155"],NATIVE_TOKEN_ADDRESS:{eip155:"0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",solana:"So11111111111111111111111111111111111111111",polkadot:"0x",bip122:"0x",cosmos:"0x"},CONVERT_SLIPPAGE_TOLERANCE:1,CONNECT_LABELS:{MOBILE:"Open and continue in the wallet app",WEB:"Open and continue in the wallet app"},SEND_SUPPORTED_NAMESPACES:["eip155","solana"],DEFAULT_REMOTE_FEATURES:{swaps:["1inch"],onramp:["coinbase","meld"],email:!0,socials:["google","x","discord","farcaster","github","apple","facebook"],activity:!0,reownBranding:!0},DEFAULT_REMOTE_FEATURES_DISABLED:{email:!1,socials:!1,swaps:!1,onramp:!1,activity:!1,reownBranding:!1},DEFAULT_FEATURES:{receive:!0,send:!0,emailShowWallets:!0,connectorTypeOrder:["walletConnect","recent","injected","featured","custom","external","recommended"],analytics:!0,allWallets:!0,legalCheckbox:!1,smartSessions:!1,collapseWallets:!1,walletFeaturesOrder:["onramp","swaps","receive","send"],connectMethodsOrder:void 0,pay:!1},DEFAULT_SOCIALS:["google","x","farcaster","discord","apple","github","facebook"],DEFAULT_ACCOUNT_TYPES:{bip122:"payment",eip155:"smartAccount",polkadot:"eoa",solana:"eoa"},ADAPTER_TYPES:{UNIVERSAL:"universal",SOLANA:"solana",WAGMI:"wagmi",ETHERS:"ethers",ETHERS5:"ethers5",BITCOIN:"bitcoin"}};var E={isMobile(){return this.isClient()?!!(typeof window?.matchMedia=="function"&&window?.matchMedia("(pointer:coarse)")?.matches||/Android|webOS|iPhone|iPad|iPod|BlackBerry|Opera Mini/u.test(navigator.userAgent)):!1},checkCaipNetwork(e,t=""){return e?.caipNetworkId.toLocaleLowerCase().includes(t.toLowerCase())},isAndroid(){if(!this.isMobile())return!1;let e=window?.navigator.userAgent.toLowerCase();return E.isMobile()&&e.includes("android")},isIos(){if(!this.isMobile())return!1;let e=window?.navigator.userAgent.toLowerCase();return e.includes("iphone")||e.includes("ipad")},isSafari(){return this.isClient()?(window?.navigator.userAgent.toLowerCase()).includes("safari"):!1},isClient(){return typeof window<"u"},isPairingExpired(e){return e?e-Date.now()<=z.TEN_SEC_MS:!0},isAllowedRetry(e,t=z.ONE_SEC_MS){return Date.now()-e>=t},copyToClopboard(e){navigator.clipboard.writeText(e)},isIframe(){try{return window?.self!==window?.top}catch{return!1}},isSafeApp(){if(E.isClient()&&window.self!==window.top)try{let e=window?.location?.ancestorOrigins?.[0],t="https://app.safe.global";if(e){let r=new URL(e),n=new URL(t);return r.hostname===n.hostname}}catch{return!1}return!1},getPairingExpiry(){return Date.now()+z.FOUR_MINUTES_MS},getNetworkId(e){return e?.split(":")[1]},getPlainAddress(e){return e?.split(":")[2]},async wait(e){return new Promise(t=>{setTimeout(t,e)})},debounce(e,t=500){let r;return(...n)=>{function o(){e(...n)}r&&clearTimeout(r),r=setTimeout(o,t)}},isHttpUrl(e){return e.startsWith("http://")||e.startsWith("https://")},formatNativeUrl(e,t,r=null){if(E.isHttpUrl(e))return this.formatUniversalUrl(e,t);let n=e,o=r;n.includes("://")||(n=e.replaceAll("/","").replaceAll(":",""),n=`${n}://`),n.endsWith("/")||(n=`${n}/`),o&&!o?.endsWith("/")&&(o=`${o}/`),this.isTelegram()&&this.isAndroid()&&(t=encodeURIComponent(t));let s=encodeURIComponent(t);return{redirect:`${n}wc?uri=${s}`,redirectUniversalLink:o?`${o}wc?uri=${s}`:void 0,href:n}},formatUniversalUrl(e,t){if(!E.isHttpUrl(e))return this.formatNativeUrl(e,t);let r=e;r.endsWith("/")||(r=`${r}/`);let n=encodeURIComponent(t);return{redirect:`${r}wc?uri=${n}`,href:r}},getOpenTargetForPlatform(e){return e==="popupWindow"?e:this.isTelegram()?f.getTelegramSocialProvider()?"_top":"_blank":e},openHref(e,t,r){window?.open(e,this.getOpenTargetForPlatform(t),r||"noreferrer noopener")},returnOpenHref(e,t,r){return window?.open(e,this.getOpenTargetForPlatform(t),r||"noreferrer noopener")},isTelegram(){return typeof window<"u"&&(!!window.TelegramWebviewProxy||!!window.Telegram||!!window.TelegramWebviewProxyProto)},isPWA(){if(typeof window>"u")return!1;let e=window.matchMedia?.("(display-mode: standalone)")?.matches,t=window?.navigator?.standalone;return!!(e||t)},async preloadImage(e){let t=new Promise((r,n)=>{let o=new Image;o.onload=r,o.onerror=n,o.crossOrigin="anonymous",o.src=e});return Promise.race([t,E.wait(2e3)])},formatBalance(e,t){let r="0.000";if(typeof e=="string"){let n=Number(e);if(n){let o=Math.floor(n*1e3)/1e3;o&&(r=o.toString())}}return`${r}${t?` ${t}`:""}`},formatBalance2(e,t){let r;if(e==="0")r="0";else if(typeof e=="string"){let n=Number(e);n&&(r=n.toString().match(/^-?\d+(?:\.\d{0,3})?/u)?.[0])}return{value:r??"0",rest:r==="0"?"000":"",symbol:t}},getApiUrl(){return W.W3M_API_URL},getBlockchainApiUrl(){return W.BLOCKCHAIN_API_RPC_URL},getAnalyticsUrl(){return W.PULSE_API_URL},getUUID(){return crypto?.randomUUID?crypto.randomUUID():"xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/gu,e=>{let t=Math.random()*16|0;return(e==="x"?t:t&3|8).toString(16)})},parseError(e){return typeof e=="string"?e:typeof e?.issues?.[0]?.message=="string"?e.issues[0].message:e instanceof Error?e.message:"Unknown error"},sortRequestedNetworks(e,t=[]){let r={};return t&&e&&(e.forEach((n,o)=>{r[n]=o}),t.sort((n,o)=>{let s=r[n.id],a=r[o.id];return s!==void 0&&a!==void 0?s-a:s!==void 0?-1:a!==void 0?1:0})),t},calculateBalance(e){let t=0;for(let r of e)t+=r.value??0;return t},formatTokenBalance(e){let t=e.toFixed(2),[r,n]=t.split(".");return{dollars:r,pennies:n}},isAddress(e,t="eip155"){switch(t){case"eip155":if(/^(?:0x)?[0-9a-f]{40}$/iu.test(e)){if(/^(?:0x)?[0-9a-f]{40}$/iu.test(e)||/^(?:0x)?[0-9A-F]{40}$/iu.test(e))return!0}else return!1;return!1;case"solana":return/[1-9A-HJ-NP-Za-km-z]{32,44}$/iu.test(e);default:return!1}},uniqueBy(e,t){let r=new Set;return e.filter(n=>{let o=n[t];return r.has(o)?!1:(r.add(o),!0)})},generateSdkVersion(e,t,r){let o=e.length===0?z.ADAPTER_TYPES.UNIVERSAL:e.map(s=>s.adapterType).join(",");return`${t}-${o}-${r}`},createAccount(e,t,r,n,o){return{namespace:e,address:t,type:r,publicKey:n,path:o}},isCaipAddress(e){if(typeof e!="string")return!1;let t=e.split(":"),r=t[0];return t.filter(Boolean).length===3&&r in W.CHAIN_NAME_MAP},isMac(){let e=window?.navigator.userAgent.toLowerCase();return e.includes("macintosh")&&!e.includes("safari")},formatTelegramSocialLoginUrl(e){let t=`--${encodeURIComponent(window?.location.href)}`,r="state=";if(new URL(e).host==="auth.magic.link"){let o="provider_authorization_url=",s=e.substring(e.indexOf(o)+o.length),a=this.injectIntoUrl(decodeURIComponent(s),r,t);return e.replace(s,encodeURIComponent(a))}return this.injectIntoUrl(e,r,t)},injectIntoUrl(e,t,r){let n=e.indexOf(t);if(n===-1)throw new Error(`${t} parameter not found in the URL: ${e}`);let o=e.indexOf("&",n),s=t.length,a=o!==-1?o:e.length,c=e.substring(0,n+s),u=e.substring(n+s,a),l=e.substring(o),d=u+r;return c+d+l}};var In=Symbol(),nr=Symbol();var Pt=Object.getPrototypeOf,ut=new WeakMap,or=e=>e&&(ut.has(e)?ut.get(e):Pt(e)===Object.prototype||Pt(e)===Array.prototype);var Rt=e=>or(e)&&e[nr]||null,pt=(e,t=!0)=>{ut.set(e,t)};var dt=e=>typeof e=="object"&&e!==null,Ae=new WeakMap,ze=new WeakSet,sr=(e=Object.is,t=(l,d)=>new Proxy(l,d),r=l=>dt(l)&&!ze.has(l)&&(Array.isArray(l)||!(Symbol.iterator in l))&&!(l instanceof WeakMap)&&!(l instanceof WeakSet)&&!(l instanceof Error)&&!(l instanceof Number)&&!(l instanceof Date)&&!(l instanceof String)&&!(l instanceof RegExp)&&!(l instanceof ArrayBuffer),n=l=>{switch(l.status){case"fulfilled":return l.value;case"rejected":throw l.reason;default:throw l}},o=new WeakMap,s=(l,d,b=n)=>{let K=o.get(l);if(K?.[0]===d)return K[1];let J=Array.isArray(l)?[]:Object.create(Object.getPrototypeOf(l));return pt(J,!0),o.set(l,[d,J]),Reflect.ownKeys(l).forEach(fe=>{if(Object.getOwnPropertyDescriptor(J,fe))return;let L=Reflect.get(l,fe),{enumerable:X}=Reflect.getOwnPropertyDescriptor(l,fe),V={value:L,enumerable:X,configurable:!0};if(ze.has(L))pt(L,!1);else if(L instanceof Promise)delete V.value,V.get=()=>b(L);else if(Ae.has(L)){let[Ie,Ee]=Ae.get(L);V.value=s(Ie,Ee(),b)}Object.defineProperty(J,fe,V)}),Object.preventExtensions(J)},a=new WeakMap,c=[1,1],u=l=>{if(!dt(l))throw new Error("object required");let d=a.get(l);if(d)return d;let b=c[0],K=new Set,J=(U,P=++c[0])=>{b!==P&&(b=P,K.forEach(T=>T(U,P)))},fe=c[1],L=(U=++c[1])=>(fe!==U&&!K.size&&(fe=U,V.forEach(([P])=>{let T=P[1](U);T>b&&(b=T)})),b),X=U=>(P,T)=>{let Z=[...P];Z[1]=[U,...Z[1]],J(Z,T)},V=new Map,Ie=(U,P)=>{if((import.meta.env?import.meta.env.MODE:void 0)!=="production"&&V.has(U))throw new Error("prop listener already exists");if(K.size){let T=P[3](X(U));V.set(U,[P,T])}else V.set(U,[P])},Ee=U=>{var P;let T=V.get(U);T&&(V.delete(U),(P=T[1])==null||P.call(T))},Te=U=>(K.add(U),K.size===1&&V.forEach(([T,Z],Le)=>{if((import.meta.env?import.meta.env.MODE:void 0)!=="production"&&Z)throw new Error("remove already exists");let Ke=T[3](X(Le));V.set(Le,[T,Ke])}),()=>{K.delete(U),K.size===0&&V.forEach(([T,Z],Le)=>{Z&&(Z(),V.set(Le,[T]))})}),ot=Array.isArray(l)?[]:Object.create(Object.getPrototypeOf(l)),Qe=t(ot,{deleteProperty(U,P){let T=Reflect.get(U,P);Ee(P);let Z=Reflect.deleteProperty(U,P);return Z&&J(["delete",[P],T]),Z},set(U,P,T,Z){let Le=Reflect.has(U,P),Ke=Reflect.get(U,P,Z);if(Le&&(e(Ke,T)||a.has(T)&&e(Ke,a.get(T))))return!0;Ee(P),dt(T)&&(T=Rt(T)||T);let Ze=T;if(T instanceof Promise)T.then(ve=>{T.status="fulfilled",T.value=ve,J(["resolve",[P],ve])}).catch(ve=>{T.status="rejected",T.reason=ve,J(["reject",[P],ve])});else{!Ae.has(T)&&r(T)&&(Ze=u(T));let ve=!ze.has(Ze)&&Ae.get(Ze);ve&&Ie(P,ve)}return Reflect.set(U,P,Ze,Z),J(["set",[P],T,Ke]),!0}});a.set(l,Qe);let jt=[ot,L,s,Te];return Ae.set(Qe,jt),Reflect.ownKeys(l).forEach(U=>{let P=Object.getOwnPropertyDescriptor(l,U);"value"in P&&(Qe[U]=l[U],delete P.value,delete P.writable),Object.defineProperty(ot,U,P)}),Qe})=>[u,Ae,ze,e,t,r,n,o,s,a,c],[ir]=sr();function v(e={}){return ir(e)}function B(e,t,r){let n=Ae.get(e);(import.meta.env?import.meta.env.MODE:void 0)!=="production"&&!n&&console.warn("Please use proxy object");let o,s=[],a=n[3],c=!1,l=a(d=>{if(s.push(d),r){t(s.splice(0));return}o||(o=Promise.resolve().then(()=>{o=void 0,c&&t(s.splice(0))}))});return c=!0,()=>{c=!1,l()}}function he(e,t){let r=Ae.get(e);(import.meta.env?import.meta.env.MODE:void 0)!=="production"&&!r&&console.warn("Please use proxy object");let[n,o,s]=r;return s(n,o(),t)}function le(e){return ze.add(e),e}function O(e,t,r,n){let o=e[t];return B(e,()=>{let s=e[t];Object.is(o,s)||r(o=s)},n)}var xn=Symbol();function Ot(e){let t=v({data:Array.from(e||[]),has(r){return this.data.some(n=>n[0]===r)},set(r,n){let o=this.data.find(s=>s[0]===r);return o?o[1]=n:this.data.push([r,n]),this},get(r){var n;return(n=this.data.find(o=>o[0]===r))==null?void 0:n[1]},delete(r){let n=this.data.findIndex(o=>o[0]===r);return n===-1?!1:(this.data.splice(n,1),!0)},clear(){this.data.splice(0)},get size(){return this.data.length},toJSON(){return new Map(this.data)},forEach(r){this.data.forEach(n=>{r(n[1],n[0],this)})},keys(){return this.data.map(r=>r[0]).values()},values(){return this.data.map(r=>r[1]).values()},entries(){return new Map(this.data).entries()},get[Symbol.toStringTag](){return"Map"},[Symbol.iterator](){return this.entries()}});return Object.defineProperties(t,{data:{enumerable:!1},size:{enumerable:!1},toJSON:{enumerable:!1}}),Object.seal(t),t}var kt={getFeatureValue(e,t){let r=t?.[e];return r===void 0?z.DEFAULT_FEATURES[e]:r},filterSocialsByPlatform(e){if(!e||!e.length)return e;if(E.isTelegram()){if(E.isIos())return e.filter(t=>t!=="google");if(E.isMac())return e.filter(t=>t!=="x");if(E.isAndroid())return e.filter(t=>!["facebook","x"].includes(t))}return e}};var h=v({features:z.DEFAULT_FEATURES,projectId:"",sdkType:"appkit",sdkVersion:"html-wagmi-undefined",defaultAccountTypes:z.DEFAULT_ACCOUNT_TYPES,enableNetworkSwitch:!0,experimental_preferUniversalLinks:!1,remoteFeatures:{}}),S={state:h,subscribeKey(e,t){return O(h,e,t)},setOptions(e){Object.assign(h,e)},setRemoteFeatures(e){if(!e)return;let t={...h.remoteFeatures,...e};h.remoteFeatures=t,h.remoteFeatures?.socials&&(h.remoteFeatures.socials=kt.filterSocialsByPlatform(h.remoteFeatures.socials))},setFeatures(e){if(!e)return;h.features||(h.features=z.DEFAULT_FEATURES);let t={...h.features,...e};h.features=t},setProjectId(e){h.projectId=e},setCustomRpcUrls(e){h.customRpcUrls=e},setAllWallets(e){h.allWallets=e},setIncludeWalletIds(e){h.includeWalletIds=e},setExcludeWalletIds(e){h.excludeWalletIds=e},setFeaturedWalletIds(e){h.featuredWalletIds=e},setTokens(e){h.tokens=e},setTermsConditionsUrl(e){h.termsConditionsUrl=e},setPrivacyPolicyUrl(e){h.privacyPolicyUrl=e},setCustomWallets(e){h.customWallets=e},setIsSiweEnabled(e){h.isSiweEnabled=e},setIsUniversalProvider(e){h.isUniversalProvider=e},setSdkVersion(e){h.sdkVersion=e},setMetadata(e){h.metadata=e},setDisableAppend(e){h.disableAppend=e},setEIP6963Enabled(e){h.enableEIP6963=e},setDebug(e){h.debug=e},setEnableWalletConnect(e){h.enableWalletConnect=e},setEnableWalletGuide(e){h.enableWalletGuide=e},setEnableAuthLogger(e){h.enableAuthLogger=e},setEnableWallets(e){h.enableWallets=e},setPreferUniversalLinks(e){h.experimental_preferUniversalLinks=e},setHasMultipleAddresses(e){h.hasMultipleAddresses=e},setSIWX(e){h.siwx=e},setConnectMethodsOrder(e){h.features={...h.features,connectMethodsOrder:e}},setWalletFeaturesOrder(e){h.features={...h.features,walletFeaturesOrder:e}},setSocialsOrder(e){h.remoteFeatures={...h.remoteFeatures,socials:e}},setCollapseWallets(e){h.features={...h.features,collapseWallets:e}},setEnableEmbedded(e){h.enableEmbedded=e},setAllowUnsupportedChain(e){h.allowUnsupportedChain=e},setManualWCControl(e){h.manualWCControl=e},setEnableNetworkSwitch(e){h.enableNetworkSwitch=e},setDefaultAccountTypes(e={}){Object.entries(e).forEach(([t,r])=>{r&&(h.defaultAccountTypes[t]=r)})},setUniversalProviderConfigOverride(e){h.universalProviderConfigOverride=e},getUniversalProviderConfigOverride(){return h.universalProviderConfigOverride},getSnapshot(){return he(h)}};async function Ye(...e){let t=await fetch(...e);if(!t.ok)throw new Error(`HTTP status code: ${t.status}`,{cause:t});return t}var ue=class{constructor({baseUrl:t,clientId:r}){this.baseUrl=t,this.clientId=r}async get({headers:t,signal:r,cache:n,...o}){let s=this.createUrl(o);return(await Ye(s,{method:"GET",headers:t,signal:r,cache:n})).json()}async getBlob({headers:t,signal:r,...n}){let o=this.createUrl(n);return(await Ye(o,{method:"GET",headers:t,signal:r})).blob()}async post({body:t,headers:r,signal:n,...o}){let s=this.createUrl(o);return(await Ye(s,{method:"POST",headers:r,body:t?JSON.stringify(t):void 0,signal:n})).json()}async put({body:t,headers:r,signal:n,...o}){let s=this.createUrl(o);return(await Ye(s,{method:"PUT",headers:r,body:t?JSON.stringify(t):void 0,signal:n})).json()}async delete({body:t,headers:r,signal:n,...o}){let s=this.createUrl(o);return(await Ye(s,{method:"DELETE",headers:r,body:t?JSON.stringify(t):void 0,signal:n})).json()}createUrl({path:t,params:r}){let n=new URL(t,this.baseUrl);return r&&Object.entries(r).forEach(([o,s])=>{s&&n.searchParams.append(o,s)}),this.clientId&&n.searchParams.append("clientId",this.clientId),n}};var ar=Object.freeze({enabled:!0,events:[]}),cr=new ue({baseUrl:E.getAnalyticsUrl(),clientId:null}),lr=5,ur=60*1e3,Se=v({...ar}),xt={state:Se,subscribeKey(e,t){return O(Se,e,t)},async sendError(e,t){if(!Se.enabled)return;let r=Date.now();if(Se.events.filter(s=>{let a=new Date(s.properties.timestamp||"").getTime();return r-a<ur}).length>=lr)return;let o={type:"error",event:t,properties:{errorType:e.name,errorMessage:e.message,stackTrace:e.stack,timestamp:new Date().toISOString()}};Se.events.push(o);try{if(typeof window>"u")return;let{projectId:s,sdkType:a,sdkVersion:c}=S.state;await cr.post({path:"/e",params:{projectId:s,st:a,sv:c||"html-wagmi-4.2.2"},body:{eventId:E.getUUID(),url:window.location.href,domain:window.location.hostname,timestamp:new Date().toISOString(),props:{type:"error",event:t,errorType:e.name,errorMessage:e.message,stackTrace:e.stack}}})}catch{}},enable(){Se.enabled=!0},disable(){Se.enabled=!1},clearEvents(){Se.events=[]}};var He=class e extends Error{constructor(t,r,n){super(t),this.name="AppKitError",this.category=r,this.originalError=n,Object.setPrototypeOf(this,e.prototype);let o=!1;if(n instanceof Error&&typeof n.stack=="string"&&n.stack){let s=n.stack,a=s.indexOf(`
`);if(a>-1){let c=s.substring(a+1);this.stack=`${this.name}: ${this.message}
${c}`,o=!0}}o||(Error.captureStackTrace?Error.captureStackTrace(this,e):this.stack||(this.stack=`${this.name}: ${this.message}`))}};function Ut(e,t){let r=e instanceof He?e:new He(e instanceof Error?e.message:String(e),t,e);throw xt.sendError(r,r.category),r}function H(e,t="INTERNAL_SDK_ERROR"){let r={};return Object.keys(e).forEach(n=>{let o=e[n];if(typeof o=="function"){let s=o;o.constructor.name==="AsyncFunction"?s=async(...a)=>{try{return await o(...a)}catch(c){return Ut(c,t)}}:s=(...a)=>{try{return o(...a)}catch(c){return Ut(c,t)}},r[n]=s}else r[n]=o}),r}var oe=v({walletImages:{},networkImages:{},chainImages:{},connectorImages:{},tokenImages:{},currencyImages:{}}),pr={state:oe,subscribeNetworkImages(e){return B(oe.networkImages,()=>e(oe.networkImages))},subscribeKey(e,t){return O(oe,e,t)},subscribe(e){return B(oe,()=>e(oe))},setWalletImage(e,t){oe.walletImages[e]=t},setNetworkImage(e,t){oe.networkImages[e]=t},setChainImage(e,t){oe.chainImages[e]=t},setConnectorImage(e,t){oe.connectorImages={...oe.connectorImages,[e]:t}},setTokenImage(e,t){oe.tokenImages[e]=t},setCurrencyImage(e,t){oe.currencyImages[e]=t}},ee=H(pr);var dr={eip155:"ba0ba0cd-17c6-4806-ad93-f9d174f17900",solana:"a1b58899-f671-4276-6a5e-56ca5bd59700",polkadot:"",bip122:"0b4838db-0161-4ffe-022d-532bf03dba00",cosmos:""},mt=v({networkImagePromises:{}}),ht={async fetchWalletImage(e){if(e)return await g._fetchWalletImage(e),this.getWalletImageById(e)},async fetchNetworkImage(e){if(!e)return;let t=this.getNetworkImageById(e);return t||(mt.networkImagePromises[e]||(mt.networkImagePromises[e]=g._fetchNetworkImage(e)),await mt.networkImagePromises[e],this.getNetworkImageById(e))},getWalletImageById(e){if(e)return ee.state.walletImages[e]},getWalletImage(e){if(e?.image_url)return e?.image_url;if(e?.image_id)return ee.state.walletImages[e.image_id]},getNetworkImage(e){if(e?.assets?.imageUrl)return e?.assets?.imageUrl;if(e?.assets?.imageId)return ee.state.networkImages[e.assets.imageId]},getNetworkImageById(e){if(e)return ee.state.networkImages[e]},getConnectorImage(e){if(e?.imageUrl)return e.imageUrl;if(e?.imageId)return ee.state.connectorImages[e.imageId]},getChainImage(e){return ee.state.networkImages[dr[e]]}};var pe={PHANTOM:{id:"a797aa35c0fadbfc1a53e7f675162ed5226968b44a19ee3d24385c64d1d3c393",url:"https://phantom.app"},SOLFLARE:{id:"1ca0bdd4747578705b1939af023d120677c64fe6ca76add81fda36e350605e79",url:"https://solflare.com"},COINBASE:{id:"fd20dc426fb37566d803205b19bbc1d4096b248ac04548e3cfb6b3a38bd033aa",url:"https://go.cb-w.com"}},Dt={handleMobileDeeplinkRedirect(e,t){let r=window.location.href,n=encodeURIComponent(r);if(e===pe.PHANTOM.id&&!("phantom"in window)){let o=r.startsWith("https")?"https":"http",s=r.split("/")[2],a=encodeURIComponent(`${o}://${s}`);window.location.href=`${pe.PHANTOM.url}/ul/browse/${n}?ref=${a}`}e===pe.SOLFLARE.id&&!("solflare"in window)&&(window.location.href=`${pe.SOLFLARE.url}/ul/v1/browse/${n}?ref=${n}`),t===W.CHAIN.SOLANA&&e===pe.COINBASE.id&&!("coinbaseSolana"in window)&&(window.location.href=`${pe.COINBASE.url}/dapp?cb_url=${n}`)}};var De=Object.freeze({message:"",variant:"success",svg:void 0,open:!1,autoClose:!0}),Y=v({...De}),mr={state:Y,subscribeKey(e,t){return O(Y,e,t)},showLoading(e,t={}){this._showMessage({message:e,variant:"loading",...t})},showSuccess(e){this._showMessage({message:e,variant:"success"})},showSvg(e,t){this._showMessage({message:e,svg:t})},showError(e){let t=E.parseError(e);this._showMessage({message:t,variant:"error"})},hide(){Y.message=De.message,Y.variant=De.variant,Y.svg=De.svg,Y.open=De.open,Y.autoClose=De.autoClose},_showMessage({message:e,svg:t,variant:r="success",autoClose:n=De.autoClose}){Y.open?(Y.open=!1,setTimeout(()=>{Y.message=e,Y.variant=r,Y.svg=t,Y.open=!0,Y.autoClose=n},150)):(Y.message=e,Y.variant=r,Y.svg=t,Y.open=!0,Y.autoClose=n)}},Q=mr;var hr={purchaseCurrencies:[{id:"2b92315d-eab7-5bef-84fa-089a131333f5",name:"USD Coin",symbol:"USDC",networks:[{name:"ethereum-mainnet",display_name:"Ethereum",chain_id:"1",contract_address:"0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"},{name:"polygon-mainnet",display_name:"Polygon",chain_id:"137",contract_address:"0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"}]},{id:"2b92315d-eab7-5bef-84fa-089a131333f5",name:"Ether",symbol:"ETH",networks:[{name:"ethereum-mainnet",display_name:"Ethereum",chain_id:"1",contract_address:"0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"},{name:"polygon-mainnet",display_name:"Polygon",chain_id:"137",contract_address:"0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"}]}],paymentCurrencies:[{id:"USD",payment_method_limits:[{id:"card",min:"10.00",max:"7500.00"},{id:"ach_bank_account",min:"10.00",max:"25000.00"}]},{id:"EUR",payment_method_limits:[{id:"card",min:"10.00",max:"7500.00"},{id:"ach_bank_account",min:"10.00",max:"25000.00"}]}]},Mt=E.getBlockchainApiUrl(),te=v({clientId:null,api:new ue({baseUrl:Mt,clientId:null}),supportedChains:{http:[],ws:[]}}),m={state:te,async get(e){let{st:t,sv:r}=m.getSdkProperties(),n=S.state.projectId,o={...e.params||{},st:t,sv:r,projectId:n};return te.api.get({...e,params:o})},getSdkProperties(){let{sdkType:e,sdkVersion:t}=S.state;return{st:e||"unknown",sv:t||"unknown"}},async isNetworkSupported(e){if(!e)return!1;try{te.supportedChains.http.length||await m.getSupportedNetworks()}catch{return!1}return te.supportedChains.http.includes(e)},async getSupportedNetworks(){try{let e=await m.get({path:"v1/supported-chains"});return te.supportedChains=e,e}catch{return te.supportedChains}},async fetchIdentity({address:e,caipNetworkId:t}){if(!await m.isNetworkSupported(t))return{avatar:"",name:""};let n=f.getIdentityFromCacheForAddress(e);if(n)return n;let o=await m.get({path:`/v1/identity/${e}`,params:{sender:i.state.activeCaipAddress?E.getPlainAddress(i.state.activeCaipAddress):void 0}});return f.updateIdentityCache({address:e,identity:o,timestamp:Date.now()}),o},async fetchTransactions({account:e,cursor:t,onramp:r,signal:n,cache:o,chainId:s}){return await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId)?m.get({path:`/v1/account/${e}/history`,params:{cursor:t,onramp:r,chainId:s},signal:n,cache:o}):{data:[],next:void 0}},async fetchSwapQuote({amount:e,userAddress:t,from:r,to:n,gasPrice:o}){return await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId)?m.get({path:"/v1/convert/quotes",headers:{"Content-Type":"application/json"},params:{amount:e,userAddress:t,from:r,to:n,gasPrice:o}}):{quotes:[]}},async fetchSwapTokens({chainId:e}){return await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId)?m.get({path:"/v1/convert/tokens",params:{chainId:e}}):{tokens:[]}},async fetchTokenPrice({addresses:e}){return await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId)?te.api.post({path:"/v1/fungible/price",body:{currency:"usd",addresses:e,projectId:S.state.projectId},headers:{"Content-Type":"application/json"}}):{fungibles:[]}},async fetchSwapAllowance({tokenAddress:e,userAddress:t}){return await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId)?m.get({path:"/v1/convert/allowance",params:{tokenAddress:e,userAddress:t},headers:{"Content-Type":"application/json"}}):{allowance:"0"}},async fetchGasPrice({chainId:e}){let{st:t,sv:r}=m.getSdkProperties();if(!await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId))throw new Error("Network not supported for Gas Price");return m.get({path:"/v1/convert/gas-price",headers:{"Content-Type":"application/json"},params:{chainId:e,st:t,sv:r}})},async generateSwapCalldata({amount:e,from:t,to:r,userAddress:n,disableEstimate:o}){if(!await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId))throw new Error("Network not supported for Swaps");return te.api.post({path:"/v1/convert/build-transaction",headers:{"Content-Type":"application/json"},body:{amount:e,eip155:{slippage:z.CONVERT_SLIPPAGE_TOLERANCE},projectId:S.state.projectId,from:t,to:r,userAddress:n,disableEstimate:o}})},async generateApproveCalldata({from:e,to:t,userAddress:r}){let{st:n,sv:o}=m.getSdkProperties();if(!await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId))throw new Error("Network not supported for Swaps");return m.get({path:"/v1/convert/build-approve",headers:{"Content-Type":"application/json"},params:{userAddress:r,from:e,to:t,st:n,sv:o}})},async getBalance(e,t,r){let{st:n,sv:o}=m.getSdkProperties();if(!await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId))return Q.showError("Token Balance Unavailable"),{balances:[]};let a=`${t}:${e}`,c=f.getBalanceCacheForCaipAddress(a);if(c)return c;let u=await m.get({path:`/v1/account/${e}/balance`,params:{currency:"usd",chainId:t,forceUpdate:r,st:n,sv:o}});return f.updateBalanceCache({caipAddress:a,balance:u,timestamp:Date.now()}),u},async lookupEnsName(e){return await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId)?m.get({path:`/v1/profile/account/${e}`,params:{apiVersion:"2"}}):{addresses:{},attributes:[]}},async reverseLookupEnsName({address:e}){return await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId)?m.get({path:`/v1/profile/reverse/${e}`,params:{sender:I.state.address,apiVersion:"2"}}):[]},async getEnsNameSuggestions(e){return await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId)?m.get({path:`/v1/profile/suggestions/${e}`,params:{zone:"reown.id"}}):{suggestions:[]}},async registerEnsName({coinType:e,address:t,message:r,signature:n}){return await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId)?te.api.post({path:"/v1/profile/account",body:{coin_type:e,address:t,message:r,signature:n},headers:{"Content-Type":"application/json"}}):{success:!1}},async generateOnRampURL({destinationWallets:e,partnerUserId:t,defaultNetwork:r,purchaseAmount:n,paymentAmount:o}){return await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId)?(await te.api.post({path:"/v1/generators/onrampurl",params:{projectId:S.state.projectId},body:{destinationWallets:e,defaultNetwork:r,partnerUserId:t,defaultExperience:"buy",presetCryptoAmount:n,presetFiatAmount:o}})).url:""},async getOnrampOptions(){if(!await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId))return{paymentCurrencies:[],purchaseCurrencies:[]};try{return await m.get({path:"/v1/onramp/options"})}catch{return hr}},async getOnrampQuote({purchaseCurrency:e,paymentCurrency:t,amount:r,network:n}){try{return await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId)?await te.api.post({path:"/v1/onramp/quote",params:{projectId:S.state.projectId},body:{purchaseCurrency:e,paymentCurrency:t,amount:r,network:n}}):null}catch{return{coinbaseFee:{amount:r,currency:t.id},networkFee:{amount:r,currency:t.id},paymentSubtotal:{amount:r,currency:t.id},paymentTotal:{amount:r,currency:t.id},purchaseAmount:{amount:r,currency:t.id},quoteId:"mocked-quote-id"}}},async getSmartSessions(e){return await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId)?m.get({path:`/v1/sessions/${e}`}):[]},async revokeSmartSession(e,t,r){return await m.isNetworkSupported(i.state.activeCaipNetwork?.caipNetworkId)?te.api.post({path:`/v1/sessions/${e}/revoke`,params:{projectId:S.state.projectId},body:{pci:t,signature:r}}):{success:!1}},setClientId(e){te.clientId=e,te.api=new ue({baseUrl:Mt,clientId:e})}};var ae=v({currentTab:0,tokenBalance:[],smartAccountDeployed:!1,addressLabels:new Map,allAccounts:[]}),fr={state:ae,replaceState(e){e&&Object.assign(ae,le(e))},subscribe(e){return i.subscribeChainProp("accountState",t=>{if(t)return e(t)})},subscribeKey(e,t,r){let n;return i.subscribeChainProp("accountState",o=>{if(o){let s=o[e];n!==s&&(n=s,t(s))}},r)},setStatus(e,t){i.setAccountProp("status",e,t)},getCaipAddress(e){return i.getAccountProp("caipAddress",e)},setCaipAddress(e,t){let r=e?E.getPlainAddress(e):void 0;t===i.state.activeChain&&(i.state.activeCaipAddress=e),i.setAccountProp("caipAddress",e,t),i.setAccountProp("address",r,t)},setBalance(e,t,r){i.setAccountProp("balance",e,r),i.setAccountProp("balanceSymbol",t,r)},setProfileName(e,t){i.setAccountProp("profileName",e,t)},setProfileImage(e,t){i.setAccountProp("profileImage",e,t)},setUser(e,t){i.setAccountProp("user",e,t)},setAddressExplorerUrl(e,t){i.setAccountProp("addressExplorerUrl",e,t)},setSmartAccountDeployed(e,t){i.setAccountProp("smartAccountDeployed",e,t)},setCurrentTab(e){i.setAccountProp("currentTab",e,i.state.activeChain)},setTokenBalance(e,t){e&&i.setAccountProp("tokenBalance",e,t)},setShouldUpdateToAddress(e,t){i.setAccountProp("shouldUpdateToAddress",e,t)},setAllAccounts(e,t){i.setAccountProp("allAccounts",e,t)},addAddressLabel(e,t,r){let n=i.getAccountProp("addressLabels",r)||new Map;n.set(e,t),i.setAccountProp("addressLabels",n,r)},removeAddressLabel(e,t){let r=i.getAccountProp("addressLabels",t)||new Map;r.delete(e),i.setAccountProp("addressLabels",r,t)},setConnectedWalletInfo(e,t){i.setAccountProp("connectedWalletInfo",e,t,!1)},setPreferredAccountType(e,t){i.setAccountProp("preferredAccountTypes",{...ae.preferredAccountTypes,[t]:e},t)},setPreferredAccountTypes(e){ae.preferredAccountTypes=e},setSocialProvider(e,t){e&&i.setAccountProp("socialProvider",e,t)},setSocialWindow(e,t){i.setAccountProp("socialWindow",e?le(e):void 0,t)},setFarcasterUrl(e,t){i.setAccountProp("farcasterUrl",e,t)},async fetchTokenBalance(e){ae.balanceLoading=!0;let t=i.state.activeCaipNetwork?.caipNetworkId,r=i.state.activeCaipNetwork?.chainNamespace,n=i.state.activeCaipAddress,o=n?E.getPlainAddress(n):void 0;if(ae.lastRetry&&!E.isAllowedRetry(ae.lastRetry,30*z.ONE_SEC_MS))return ae.balanceLoading=!1,[];try{if(o&&t&&r){let a=(await m.getBalance(o,t)).balances.filter(c=>c.quantity.decimals!=="0");return I.setTokenBalance(a,r),ae.lastRetry=void 0,ae.balanceLoading=!1,a}}catch(s){ae.lastRetry=Date.now(),e?.(s),Q.showError("Token Balance Unavailable")}finally{ae.balanceLoading=!1}return[]},resetAccount(e){i.resetAccount(e)}},I=H(fr);var Lt={onSwitchNetwork({network:e,ignoreSwitchConfirmation:t=!1}){let r=i.state.activeCaipNetwork,n=w.state.data;if(e.id===r?.id)return;let s=I.getCaipAddress(i.state.activeChain),a=e.chainNamespace!==i.state.activeChain,c=I.getCaipAddress(e.chainNamespace),l=C.getConnectorId(i.state.activeChain)===W.CONNECTOR_ID.AUTH,d=W.AUTH_CONNECTOR_SUPPORTED_CHAINS.find(b=>b===e.chainNamespace);t||l&&d?w.push("SwitchNetwork",{...n,network:e}):s&&a&&!c?w.push("SwitchActiveChain",{switchToChain:e.chainNamespace,navigateTo:"Connect",navigateWithReplace:!0,network:e}):w.push("SwitchNetwork",{...n,network:e})}};var Ne=v({message:"",variant:"info",open:!1}),gr={state:Ne,subscribeKey(e,t){return O(Ne,e,t)},open(e,t){let{debug:r}=S.state,{shortMessage:n,longMessage:o}=e;r&&(Ne.message=n,Ne.variant=t,Ne.open=!0),o&&console.error(typeof o=="function"?o():o)},close(){Ne.open=!1,Ne.message="",Ne.variant="info"}},ft=H(gr);var wr=E.getAnalyticsUrl(),Cr=new ue({baseUrl:wr,clientId:null}),br=["MODAL_CREATED"],ge=v({timestamp:Date.now(),reportedErrors:{},data:{type:"track",event:"MODAL_CREATED"}}),$={state:ge,subscribe(e){return B(ge,()=>e(ge))},getSdkProperties(){let{projectId:e,sdkType:t,sdkVersion:r}=S.state;return{projectId:e,st:t,sv:r||"html-wagmi-4.2.2"}},async _sendAnalyticsEvent(e){try{let t=I.state.address;if(br.includes(e.data.event)||typeof window>"u")return;await Cr.post({path:"/e",params:$.getSdkProperties(),body:{eventId:E.getUUID(),url:window.location.href,domain:window.location.hostname,timestamp:e.timestamp,props:{...e.data,address:t}}}),ge.reportedErrors.FORBIDDEN=!1}catch(t){t instanceof Error&&t.cause instanceof Response&&t.cause.status===W.HTTP_STATUS_CODES.FORBIDDEN&&!ge.reportedErrors.FORBIDDEN&&(ft.open({shortMessage:"Invalid App Configuration",longMessage:`Origin ${Ue()?window.origin:"uknown"} not found on Allowlist - update configuration on cloud.reown.com`},"error"),ge.reportedErrors.FORBIDDEN=!0)}},sendEvent(e){ge.timestamp=Date.now(),ge.data=e,S.state.features?.analytics&&$._sendAnalyticsEvent(ge)}};var Fe=v({loading:!1,open:!1,selectedNetworkId:void 0,activeChain:void 0,initialized:!1}),we={state:Fe,subscribe(e){return B(Fe,()=>e(Fe))},subscribeOpen(e){return O(Fe,"open",e)},set(e){Object.assign(Fe,{...Fe,...e})}};var re=v({loading:!1,loadingNamespaceMap:new Map,open:!1,shake:!1,namespace:void 0}),Er={state:re,subscribe(e){return B(re,()=>e(re))},subscribeKey(e,t){return O(re,e,t)},async open(e){let t=I.state.status==="connected",r=e?.namespace,n=i.state.activeChain,o=r&&r!==n,s=i.getAccountData(e?.namespace)?.caipAddress;if(N.state.wcBasic?g.prefetch({fetchNetworkImages:!1,fetchConnectorImages:!1}):await g.prefetch({fetchConnectorImages:!t,fetchFeaturedWallets:!t,fetchRecommendedWallets:!t}),C.setFilterByNamespace(e?.namespace),G.setLoading(!0,r),r&&o){let a=i.getNetworkData(r)?.caipNetwork||i.getRequestedCaipNetworks(r)[0];a&&Lt.onSwitchNetwork({network:a,ignoreSwitchConfirmation:!0})}else{let a=i.state.noAdapters;S.state.manualWCControl||a&&!s?E.isMobile()?w.reset("AllWallets"):w.reset("ConnectingWalletConnectBasic"):e?.view?w.reset(e.view,e.data):s?w.reset("Account"):w.reset("Connect")}re.open=!0,we.set({open:!0}),$.sendEvent({type:"track",event:"MODAL_OPEN",properties:{connected:!!s}})},close(){let e=S.state.enableEmbedded,t=!!i.state.activeCaipAddress;re.open&&$.sendEvent({type:"track",event:"MODAL_CLOSE",properties:{connected:t}}),re.open=!1,w.reset("Connect"),G.clearLoading(),e?t?w.replace("Account"):w.push("Connect"):we.set({open:!1}),N.resetUri()},setLoading(e,t){t&&re.loadingNamespaceMap.set(t,e),re.loading=e,we.set({loading:e})},clearLoading(){re.loadingNamespaceMap.clear(),re.loading=!1},shake(){re.shake||(re.shake=!0,setTimeout(()=>{re.shake=!1},500))}},G=H(Er);var F=v({view:"Connect",history:["Connect"],transactionStack:[]}),vr={state:F,subscribeKey(e,t){return O(F,e,t)},pushTransactionStack(e){F.transactionStack.push(e)},popTransactionStack(e){let t=F.transactionStack.pop();if(!t)return;let{onSuccess:r,onError:n,onCancel:o}=t;switch(e){case"success":r?.();break;case"error":n?.(),w.goBack();break;case"cancel":o?.(),w.goBack();break;default:}},push(e,t){e!==F.view&&(F.view=e,F.history.push(e),F.data=t)},reset(e,t){F.view=e,F.history=[e],F.data=t},replace(e,t){F.history.at(-1)===e||(F.view=e,F.history[F.history.length-1]=e,F.data=t)},goBack(){let e=i.state.activeCaipAddress,t=w.state.view==="ConnectingFarcaster",r=!e&&t;if(F.history.length>1){F.history.pop();let[n]=F.history.slice(-1);n&&(e&&n==="Connect"?F.view="Account":F.view=n)}else G.close();F.data?.wallet&&(F.data.wallet=void 0),setTimeout(()=>{if(r){I.setFarcasterUrl(void 0,i.state.activeChain);let n=C.getAuthConnector();n?.provider?.reload();let o=he(S.state);n?.provider?.syncDappData?.({metadata:o.metadata,sdkVersion:o.sdkVersion,projectId:o.projectId,sdkType:o.sdkType})}},100)},goBackToIndex(e){if(F.history.length>1){F.history=F.history.slice(0,e+1);let[t]=F.history.slice(-1);t&&(F.view=t)}},goBackOrCloseModal(){w.state.history.length>1?w.goBack():G.close()}},w=H(vr);var Ce=v({themeMode:"dark",themeVariables:{},w3mThemeVariables:void 0}),gt={state:Ce,subscribe(e){return B(Ce,()=>e(Ce))},setThemeMode(e){Ce.themeMode=e;try{let t=C.getAuthConnector();if(t){let r=gt.getSnapshot().themeVariables;t.provider.syncTheme({themeMode:e,themeVariables:r,w3mThemeVariables:ie(r,e)})}}catch{console.info("Unable to sync theme to auth connector")}},setThemeVariables(e){Ce.themeVariables={...Ce.themeVariables,...e};try{let t=C.getAuthConnector();if(t){let r=gt.getSnapshot().themeVariables;t.provider.syncTheme({themeVariables:r,w3mThemeVariables:ie(Ce.themeVariables,Ce.themeMode)})}}catch{console.info("Unable to sync theme to auth connector")}},getSnapshot(){return he(Ce)}},We=H(gt);var Bt={eip155:void 0,solana:void 0,polkadot:void 0,bip122:void 0,cosmos:void 0},k=v({allConnectors:[],connectors:[],activeConnector:void 0,filterByNamespace:void 0,activeConnectorIds:{...Bt},filterByNamespaceMap:{eip155:!0,solana:!0,polkadot:!0,bip122:!0,cosmos:!0}}),Ar={state:k,subscribe(e){return B(k,()=>{e(k)})},subscribeKey(e,t){return O(k,e,t)},initialize(e){e.forEach(t=>{let r=f.getConnectedConnectorId(t);r&&C.setConnectorId(r,t)})},setActiveConnector(e){e&&(k.activeConnector=le(e))},setConnectors(e){e.filter(o=>!k.allConnectors.some(s=>s.id===o.id&&C.getConnectorName(s.name)===C.getConnectorName(o.name)&&s.chain===o.chain)).forEach(o=>{o.type!=="MULTI_CHAIN"&&k.allConnectors.push(le(o))});let r=C.getEnabledNamespaces(),n=C.getEnabledConnectors(r);k.connectors=C.mergeMultiChainConnectors(n)},filterByNamespaces(e){Object.keys(k.filterByNamespaceMap).forEach(t=>{k.filterByNamespaceMap[t]=!1}),e.forEach(t=>{k.filterByNamespaceMap[t]=!0}),C.updateConnectorsForEnabledNamespaces()},filterByNamespace(e,t){k.filterByNamespaceMap[e]=t,C.updateConnectorsForEnabledNamespaces()},updateConnectorsForEnabledNamespaces(){let e=C.getEnabledNamespaces(),t=C.getEnabledConnectors(e),r=C.areAllNamespacesEnabled();k.connectors=C.mergeMultiChainConnectors(t),r?g.clearFilterByNamespaces():g.filterByNamespaces(e)},getEnabledNamespaces(){return Object.entries(k.filterByNamespaceMap).filter(([e,t])=>t).map(([e])=>e)},getEnabledConnectors(e){return k.allConnectors.filter(t=>e.includes(t.chain))},areAllNamespacesEnabled(){return Object.values(k.filterByNamespaceMap).every(e=>e)},mergeMultiChainConnectors(e){let t=C.generateConnectorMapByName(e),r=[];return t.forEach(n=>{let o=n[0],s=o?.id===W.CONNECTOR_ID.AUTH;n.length>1&&o?r.push({name:o.name,imageUrl:o.imageUrl,imageId:o.imageId,connectors:[...n],type:s?"AUTH":"MULTI_CHAIN",chain:"eip155",id:o?.id||""}):o&&r.push(o)}),r},generateConnectorMapByName(e){let t=new Map;return e.forEach(r=>{let{name:n}=r,o=C.getConnectorName(n);if(!o)return;let s=t.get(o)||[];s.find(c=>c.chain===r.chain)||s.push(r),t.set(o,s)}),t},getConnectorName(e){return e&&({"Trust Wallet":"Trust"}[e]||e)},getUniqueConnectorsByName(e){let t=[];return e.forEach(r=>{t.find(n=>n.chain===r.chain)||t.push(r)}),t},addConnector(e){if(e.id===W.CONNECTOR_ID.AUTH){let t=e,r=he(S.state),n=We.getSnapshot().themeMode,o=We.getSnapshot().themeVariables;t?.provider?.syncDappData?.({metadata:r.metadata,sdkVersion:r.sdkVersion,projectId:r.projectId,sdkType:r.sdkType}),t?.provider?.syncTheme({themeMode:n,themeVariables:o,w3mThemeVariables:ie(o,n)}),C.setConnectors([e])}else C.setConnectors([e])},getAuthConnector(e){let t=e||i.state.activeChain,r=k.connectors.find(n=>n.id===W.CONNECTOR_ID.AUTH);if(r)return r?.connectors?.length?r.connectors.find(o=>o.chain===t):r},getAnnouncedConnectorRdns(){return k.connectors.filter(e=>e.type==="ANNOUNCED").map(e=>e.info?.rdns)},getConnectorById(e){return k.allConnectors.find(t=>t.id===e)},getConnector(e,t){return k.allConnectors.filter(n=>n.chain===i.state.activeChain).find(n=>n.explorerId===e||n.info?.rdns===t)},syncIfAuthConnector(e){if(e.id!=="ID_AUTH")return;let t=e,r=he(S.state),n=We.getSnapshot().themeMode,o=We.getSnapshot().themeVariables;t?.provider?.syncDappData?.({metadata:r.metadata,sdkVersion:r.sdkVersion,sdkType:r.sdkType,projectId:r.projectId}),t.provider.syncTheme({themeMode:n,themeVariables:o,w3mThemeVariables:ie(o,n)})},getConnectorsByNamespace(e){let t=k.allConnectors.filter(r=>r.chain===e);return C.mergeMultiChainConnectors(t)},selectWalletConnector(e){let t=C.getConnector(e.id,e.rdns),r=i.state.activeChain;Dt.handleMobileDeeplinkRedirect(t?.explorerId||e.id,r),t?w.push("ConnectingExternal",{connector:t}):w.push("ConnectingWalletConnect",{wallet:e})},getConnectors(e){return e?C.getConnectorsByNamespace(e):C.mergeMultiChainConnectors(k.allConnectors)},setFilterByNamespace(e){k.filterByNamespace=e,k.connectors=C.getConnectors(e),g.setFilterByNamespace(e)},setConnectorId(e,t){e&&(k.activeConnectorIds={...k.activeConnectorIds,[t]:e},f.setConnectedConnectorId(t,e))},removeConnectorId(e){k.activeConnectorIds={...k.activeConnectorIds,[e]:void 0},f.deleteConnectedConnectorId(e)},getConnectorId(e){if(e)return k.activeConnectorIds[e]},isConnected(e){return e?!!k.activeConnectorIds[e]:Object.values(k.activeConnectorIds).some(t=>!!t)},resetConnectorIds(){k.activeConnectorIds={...Bt}}},C=H(Ar);var Sr="https://secure.walletconnect.org/sdk",Fs=(typeof process<"u"&&typeof process.env<"u"?process.env.NEXT_PUBLIC_SECURE_SITE_SDK_URL:void 0)||Sr,Ws=(typeof process<"u"&&typeof process.env<"u"?process.env.NEXT_PUBLIC_DEFAULT_LOG_LEVEL:void 0)||"error",$s=(typeof process<"u"&&typeof process.env<"u"?process.env.NEXT_PUBLIC_SECURE_SITE_SDK_VERSION:void 0)||"4";var be={SAFE_RPC_METHODS:["eth_accounts","eth_blockNumber","eth_call","eth_chainId","eth_estimateGas","eth_feeHistory","eth_gasPrice","eth_getAccount","eth_getBalance","eth_getBlockByHash","eth_getBlockByNumber","eth_getBlockReceipts","eth_getBlockTransactionCountByHash","eth_getBlockTransactionCountByNumber","eth_getCode","eth_getFilterChanges","eth_getFilterLogs","eth_getLogs","eth_getProof","eth_getStorageAt","eth_getTransactionByBlockHashAndIndex","eth_getTransactionByBlockNumberAndIndex","eth_getTransactionByHash","eth_getTransactionCount","eth_getTransactionReceipt","eth_getUncleCountByBlockHash","eth_getUncleCountByBlockNumber","eth_maxPriorityFeePerGas","eth_newBlockFilter","eth_newFilter","eth_newPendingTransactionFilter","eth_sendRawTransaction","eth_syncing","eth_uninstallFilter","wallet_getCapabilities","wallet_getCallsStatus","eth_getUserOperationReceipt","eth_estimateUserOperationGas","eth_getUserOperationByHash","eth_supportedEntryPoints","wallet_getAssets"],NOT_SAFE_RPC_METHODS:["personal_sign","eth_signTypedData_v4","eth_sendTransaction","solana_signMessage","solana_signTransaction","solana_signAllTransactions","solana_signAndSendTransaction","wallet_sendCalls","wallet_grantPermissions","wallet_revokePermissions","eth_sendUserOperation"],GET_CHAIN_ID:"eth_chainId",RPC_METHOD_NOT_ALLOWED_MESSAGE:"Requested RPC call is not allowed",RPC_METHOD_NOT_ALLOWED_UI_MESSAGE:"Action not allowed",ACCOUNT_TYPES:{EOA:"eoa",SMART_ACCOUNT:"smartAccount"}};var j=v({transactions:[],coinbaseTransactions:{},transactionsByYear:{},lastNetworkInView:void 0,loading:!1,empty:!1,next:void 0}),Nr={state:j,subscribe(e){return B(j,()=>e(j))},setLastNetworkInView(e){j.lastNetworkInView=e},async fetchTransactions(e,t){if(!e)throw new Error("Transactions can't be fetched without an accountAddress");j.loading=!0;try{let r=await m.fetchTransactions({account:e,cursor:j.next,onramp:t,cache:t==="coinbase"?"no-cache":void 0,chainId:i.state.activeCaipNetwork?.caipNetworkId}),n=$e.filterSpamTransactions(r.data),o=$e.filterByConnectedChain(n),s=[...j.transactions,...o];j.loading=!1,t==="coinbase"?j.coinbaseTransactions=$e.groupTransactionsByYearAndMonth(j.coinbaseTransactions,r.data):(j.transactions=s,j.transactionsByYear=$e.groupTransactionsByYearAndMonth(j.transactionsByYear,o)),j.empty=s.length===0,j.next=r.next?r.next:void 0}catch{let n=i.state.activeChain;$.sendEvent({type:"track",event:"ERROR_FETCH_TRANSACTIONS",properties:{address:e,projectId:S.state.projectId,cursor:j.next,isSmartAccount:I.state.preferredAccountTypes?.[n]===be.ACCOUNT_TYPES.SMART_ACCOUNT}}),Q.showError("Failed to fetch transactions"),j.loading=!1,j.empty=!0,j.next=void 0}},groupTransactionsByYearAndMonth(e={},t=[]){let r=e;return t.forEach(n=>{let o=new Date(n.metadata.minedAt).getFullYear(),s=new Date(n.metadata.minedAt).getMonth(),a=r[o]??{},u=(a[s]??[]).filter(l=>l.id!==n.id);r[o]={...a,[s]:[...u,n].sort((l,d)=>new Date(d.metadata.minedAt).getTime()-new Date(l.metadata.minedAt).getTime())}}),r},filterSpamTransactions(e){return e.filter(t=>!t.transfers.every(n=>n.nft_info?.flags.is_spam===!0))},filterByConnectedChain(e){let t=i.state.activeCaipNetwork?.caipNetworkId;return e.filter(n=>n.metadata.chain===t)},clearCursor(){j.next=void 0},resetTransactions(){j.transactions=[],j.transactionsByYear={},j.lastNetworkInView=void 0,j.loading=!1,j.empty=!1,j.next=void 0}},$e=H(Nr,"API_ERROR");var q=v({connections:new Map,wcError:!1,buffering:!1,status:"disconnected"}),Me,yr={state:q,subscribeKey(e,t){return O(q,e,t)},_getClient(){return q._client},setClient(e){q._client=le(e)},async connectWalletConnect(){if(E.isTelegram()||E.isSafari()&&E.isIos()){if(Me){await Me,Me=void 0;return}if(!E.isPairingExpired(q?.wcPairingExpiry)){let e=q.wcUri;q.wcUri=e;return}Me=N._getClient()?.connectWalletConnect?.().catch(()=>{}),N.state.status="connecting",await Me,Me=void 0,q.wcPairingExpiry=void 0,N.state.status="connected"}else await N._getClient()?.connectWalletConnect?.()},async connectExternal(e,t,r=!0){await N._getClient()?.connectExternal?.(e),r&&i.setActiveNamespace(t)},async reconnectExternal(e){await N._getClient()?.reconnectExternal?.(e);let t=e.chain||i.state.activeChain;t&&C.setConnectorId(e.id,t)},async setPreferredAccountType(e,t){G.setLoading(!0,i.state.activeChain);let r=C.getAuthConnector();r&&(I.setPreferredAccountType(e,t),await r.provider.setPreferredAccount(e),f.setPreferredAccountTypes(I.state.preferredAccountTypes??{[t]:e}),await N.reconnectExternal(r),G.setLoading(!1,i.state.activeChain),$.sendEvent({type:"track",event:"SET_PREFERRED_ACCOUNT_TYPE",properties:{accountType:e,network:i.state.activeCaipNetwork?.caipNetworkId||""}}))},async signMessage(e){return N._getClient()?.signMessage(e)},parseUnits(e,t){return N._getClient()?.parseUnits(e,t)},formatUnits(e,t){return N._getClient()?.formatUnits(e,t)},async sendTransaction(e){return N._getClient()?.sendTransaction(e)},async getCapabilities(e){return N._getClient()?.getCapabilities(e)},async grantPermissions(e){return N._getClient()?.grantPermissions(e)},async walletGetAssets(e){return N._getClient()?.walletGetAssets(e)??{}},async estimateGas(e){return N._getClient()?.estimateGas(e)},async writeContract(e){return N._getClient()?.writeContract(e)},async getEnsAddress(e){return N._getClient()?.getEnsAddress(e)},async getEnsAvatar(e){return N._getClient()?.getEnsAvatar(e)},checkInstalled(e){return N._getClient()?.checkInstalled?.(e)||!1},resetWcConnection(){q.wcUri=void 0,q.wcPairingExpiry=void 0,q.wcLinking=void 0,q.recentWallet=void 0,q.status="disconnected",$e.resetTransactions(),f.deleteWalletConnectDeepLink()},resetUri(){q.wcUri=void 0,q.wcPairingExpiry=void 0,Me=void 0},finalizeWcConnection(){let{wcLinking:e,recentWallet:t}=N.state;e&&f.setWalletConnectDeepLink(e),t&&f.setAppKitRecent(t),$.sendEvent({type:"track",event:"CONNECT_SUCCESS",properties:{method:e?"mobile":"qrcode",name:w.state.data?.wallet?.name||"Unknown"}})},setWcBasic(e){q.wcBasic=e},setUri(e){q.wcUri=e,q.wcPairingExpiry=E.getPairingExpiry()},setWcLinking(e){q.wcLinking=e},setWcError(e){q.wcError=e,q.buffering=!1},setRecentWallet(e){q.recentWallet=e},setBuffering(e){q.buffering=e},setStatus(e){q.status=e},async disconnect(e){try{await N._getClient()?.disconnect(e)}catch(t){throw new He("Failed to disconnect","INTERNAL_SDK_ERROR",t)}},setConnections(e,t){q.connections.set(t,e)},switchAccount({connection:e,address:t,namespace:r}){if(C.state.activeConnectorIds[r]===e.connectorId){let s=i.state.activeCaipNetwork;if(s){let a=`${r}:${s.id}:${t}`;I.setCaipAddress(a,r)}else console.warn(`No current network found for namespace "${r}"`)}else{let s=C.getConnector(e.connectorId);s?N.connectExternal(s,r):console.warn(`No connector found for namespace "${r}"`)}}},N=H(yr);var tt={createBalance(e,t){let r={name:e.metadata.name||"",symbol:e.metadata.symbol||"",decimals:e.metadata.decimals||0,value:e.metadata.value||0,price:e.metadata.price||0,iconUrl:e.metadata.iconUrl||""};return{name:r.name,symbol:r.symbol,chainId:t,address:e.address==="native"?void 0:this.convertAddressToCAIP10Address(e.address,t),value:r.value,price:r.price,quantity:{decimals:r.decimals.toString(),numeric:this.convertHexToBalance({hex:e.balance,decimals:r.decimals})},iconUrl:r.iconUrl}},convertHexToBalance({hex:e,decimals:t}){return vt(BigInt(e),t)},convertAddressToCAIP10Address(e,t){return`${t}:${e}`},createCAIP2ChainId(e,t){return`${t}:${parseInt(e,16)}`},getChainIdHexFromCAIP2ChainId(e){let t=e.split(":");if(t.length<2||!t[1])return"0x0";let r=t[1],n=parseInt(r,10);return isNaN(n)?"0x0":`0x${n.toString(16)}`},isWalletGetAssetsResponse(e){return typeof e!="object"||e===null?!1:Object.values(e).every(t=>Array.isArray(t)&&t.every(r=>this.isValidAsset(r)))},isValidAsset(e){return typeof e=="object"&&e!==null&&typeof e.address=="string"&&typeof e.balance=="string"&&(e.type==="ERC20"||e.type==="NATIVE")&&typeof e.metadata=="object"&&e.metadata!==null&&typeof e.metadata.name=="string"&&typeof e.metadata.symbol=="string"&&typeof e.metadata.decimals=="number"&&typeof e.metadata.price=="number"&&typeof e.metadata.iconUrl=="string"}};var wt={async getMyTokensWithBalance(e){let t=I.state.address,r=i.state.activeCaipNetwork;if(!t||!r)return[];if(r.chainNamespace==="eip155"){let o=await this.getEIP155Balances(t,r);if(o)return this.filterLowQualityTokens(o)}let n=await m.getBalance(t,r.caipNetworkId,e);return this.filterLowQualityTokens(n.balances)},async getEIP155Balances(e,t){try{let r=tt.getChainIdHexFromCAIP2ChainId(t.caipNetworkId);if(!(await N.getCapabilities(e))?.[r]?.assetDiscovery?.supported)return null;let o=await N.walletGetAssets({account:e,chainFilter:[r]});return tt.isWalletGetAssetsResponse(o)?(o[r]||[]).map(a=>tt.createBalance(a,t.caipNetworkId)):null}catch{return null}},filterLowQualityTokens(e){return e.filter(t=>t.quantity.decimals!=="0")},mapBalancesToSwapTokens(e){return e?.map(t=>({...t,address:t?.address?t.address:i.getActiveNetworkTokenAddress(),decimals:parseInt(t.quantity.decimals,10),logoUri:t.iconUrl,eip2612:!1}))||[]}};var M=v({tokenBalances:[],loading:!1}),_r={state:M,subscribe(e){return B(M,()=>e(M))},subscribeKey(e,t){return O(M,e,t)},setToken(e){e&&(M.token=le(e))},setTokenAmount(e){M.sendTokenAmount=e},setReceiverAddress(e){M.receiverAddress=e},setReceiverProfileImageUrl(e){M.receiverProfileImageUrl=e},setReceiverProfileName(e){M.receiverProfileName=e},setNetworkBalanceInUsd(e){M.networkBalanceInUSD=e},setLoading(e){M.loading=e},async sendToken(){try{switch(x.setLoading(!0),i.state.activeCaipNetwork?.chainNamespace){case"eip155":await x.sendEvmToken();return;case"solana":await x.sendSolanaToken();return;default:throw new Error("Unsupported chain")}}finally{x.setLoading(!1)}},async sendEvmToken(){let e=i.state.activeChain,t=I.state.preferredAccountTypes?.[e];if(!x.state.sendTokenAmount||!x.state.receiverAddress)throw new Error("An amount and receiver address are required");if(!x.state.token)throw new Error("A token is required");x.state.token?.address?($.sendEvent({type:"track",event:"SEND_INITIATED",properties:{isSmartAccount:t===be.ACCOUNT_TYPES.SMART_ACCOUNT,token:x.state.token.address,amount:x.state.sendTokenAmount,network:i.state.activeCaipNetwork?.caipNetworkId||""}}),await x.sendERC20Token({receiverAddress:x.state.receiverAddress,tokenAddress:x.state.token.address,sendTokenAmount:x.state.sendTokenAmount,decimals:x.state.token.quantity.decimals})):($.sendEvent({type:"track",event:"SEND_INITIATED",properties:{isSmartAccount:t===be.ACCOUNT_TYPES.SMART_ACCOUNT,token:x.state.token.symbol||"",amount:x.state.sendTokenAmount,network:i.state.activeCaipNetwork?.caipNetworkId||""}}),await x.sendNativeToken({receiverAddress:x.state.receiverAddress,sendTokenAmount:x.state.sendTokenAmount,decimals:x.state.token.quantity.decimals}))},async fetchTokenBalance(e){M.loading=!0;let t=i.state.activeCaipNetwork?.caipNetworkId,r=i.state.activeCaipNetwork?.chainNamespace,n=i.state.activeCaipAddress,o=n?E.getPlainAddress(n):void 0;if(M.lastRetry&&!E.isAllowedRetry(M.lastRetry,30*z.ONE_SEC_MS))return M.loading=!1,[];try{if(o&&t&&r){let s=await wt.getMyTokensWithBalance();return M.tokenBalances=s,M.lastRetry=void 0,s}}catch(s){M.lastRetry=Date.now(),e?.(s),Q.showError("Token Balance Unavailable")}finally{M.loading=!1}return[]},fetchNetworkBalance(){if(M.tokenBalances.length===0)return;let e=wt.mapBalancesToSwapTokens(M.tokenBalances);if(!e)return;let t=e.find(r=>r.address===i.getActiveNetworkTokenAddress());t&&(M.networkBalanceInUSD=t?it.multiply(t.quantity.numeric,t.price).toString():"0")},async sendNativeToken(e){w.pushTransactionStack({});let t=e.receiverAddress,r=I.state.address,n=N.parseUnits(e.sendTokenAmount.toString(),Number(e.decimals));await N.sendTransaction({chainNamespace:"eip155",to:t,address:r,data:"0x",value:n??BigInt(0)}),$.sendEvent({type:"track",event:"SEND_SUCCESS",properties:{isSmartAccount:I.state.preferredAccountTypes?.eip155===be.ACCOUNT_TYPES.SMART_ACCOUNT,token:x.state.token?.symbol||"",amount:e.sendTokenAmount,network:i.state.activeCaipNetwork?.caipNetworkId||""}}),N._getClient()?.updateBalance("eip155"),x.resetSend()},async sendERC20Token(e){w.pushTransactionStack({onSuccess(){w.replace("Account")}});let t=N.parseUnits(e.sendTokenAmount.toString(),Number(e.decimals));if(I.state.address&&e.sendTokenAmount&&e.receiverAddress&&e.tokenAddress){let r=E.getPlainAddress(e.tokenAddress);await N.writeContract({fromAddress:I.state.address,tokenAddress:r,args:[e.receiverAddress,t??BigInt(0)],method:"transfer",abi:at.getERC20Abi(r),chainNamespace:"eip155"}),x.resetSend()}},async sendSolanaToken(){if(!x.state.sendTokenAmount||!x.state.receiverAddress)throw new Error("An amount and receiver address are required");w.pushTransactionStack({onSuccess(){w.replace("Account")}}),await N.sendTransaction({chainNamespace:"solana",to:x.state.receiverAddress,value:x.state.sendTokenAmount}),N._getClient()?.updateBalance("solana"),x.resetSend()},resetSend(){M.token=void 0,M.sendTokenAmount=void 0,M.receiverAddress=void 0,M.receiverProfileImageUrl=void 0,M.receiverProfileName=void 0,M.loading=!1,M.tokenBalances=[]}},x=H(_r);var Ct={currentTab:0,tokenBalance:[],smartAccountDeployed:!1,addressLabels:new Map,allAccounts:[],user:void 0},rt={caipNetwork:void 0,supportsAllNetworks:!0,smartAccountEnabledNetworks:[]},p=v({chains:Ot(),activeCaipAddress:void 0,activeChain:void 0,activeCaipNetwork:void 0,noAdapters:!1,universalAdapter:{networkControllerClient:void 0,connectionControllerClient:void 0},isSwitchingNamespace:!1}),Ir={state:p,subscribe(e){return B(p,()=>{e(p)})},subscribeKey(e,t){return O(p,e,t)},subscribeChainProp(e,t,r){let n;return B(p.chains,()=>{let o=r||p.activeChain;if(o){let s=p.chains.get(o)?.[e];n!==s&&(n=s,t(s))}})},initialize(e,t,r){let{chainId:n,namespace:o}=f.getActiveNetworkProps(),s=t?.find(d=>d.id.toString()===n?.toString()),c=e.find(d=>d?.namespace===o)||e?.[0],u=e.map(d=>d.namespace).filter(d=>d!==void 0),l=S.state.enableEmbedded?new Set([...u]):new Set([...t?.map(d=>d.chainNamespace)??[]]);(e?.length===0||!c)&&(p.noAdapters=!0),p.noAdapters||(p.activeChain=c?.namespace,p.activeCaipNetwork=s,i.setChainNetworkData(c?.namespace,{caipNetwork:s}),p.activeChain&&we.set({activeChain:c?.namespace})),l.forEach(d=>{let b=t?.filter(K=>K.chainNamespace===d);i.state.chains.set(d,{namespace:d,networkState:v({...rt,caipNetwork:b?.[0]}),accountState:v(Ct),caipNetworks:b??[],...r}),i.setRequestedCaipNetworks(b??[],d)})},removeAdapter(e){if(p.activeChain===e){let t=Array.from(p.chains.entries()).find(([r])=>r!==e);if(t){let r=t[1]?.caipNetworks?.[0];r&&i.setActiveCaipNetwork(r)}}p.chains.delete(e)},addAdapter(e,{networkControllerClient:t,connectionControllerClient:r},n){p.chains.set(e.namespace,{namespace:e.namespace,networkState:{...rt,caipNetwork:n[0]},accountState:Ct,caipNetworks:n,connectionControllerClient:r,networkControllerClient:t}),i.setRequestedCaipNetworks(n?.filter(o=>o.chainNamespace===e.namespace)??[],e.namespace)},addNetwork(e){let t=p.chains.get(e.chainNamespace);if(t){let r=[...t.caipNetworks||[]];t.caipNetworks?.find(n=>n.id===e.id)||r.push(e),p.chains.set(e.chainNamespace,{...t,caipNetworks:r}),i.setRequestedCaipNetworks(r,e.chainNamespace),C.filterByNamespace(e.chainNamespace,!0)}},removeNetwork(e,t){let r=p.chains.get(e);if(r){let n=p.activeCaipNetwork?.id===t,o=[...r.caipNetworks?.filter(s=>s.id!==t)||[]];n&&r?.caipNetworks?.[0]&&i.setActiveCaipNetwork(r.caipNetworks[0]),p.chains.set(e,{...r,caipNetworks:o}),i.setRequestedCaipNetworks(o||[],e),o.length===0&&C.filterByNamespace(e,!1)}},setAdapterNetworkState(e,t){let r=p.chains.get(e);r&&(r.networkState={...r.networkState||rt,...t},p.chains.set(e,r))},setChainAccountData(e,t,r=!0){if(!e)throw new Error("Chain is required to update chain account data");let n=p.chains.get(e);if(n){let o={...n.accountState||Ct,...t};p.chains.set(e,{...n,accountState:o}),(p.chains.size===1||p.activeChain===e)&&(t.caipAddress&&(p.activeCaipAddress=t.caipAddress),I.replaceState(o))}},setChainNetworkData(e,t){if(!e)return;let r=p.chains.get(e);if(r){let n={...r.networkState||rt,...t};p.chains.set(e,{...r,networkState:n})}},setAccountProp(e,t,r,n=!0){i.setChainAccountData(r,{[e]:t},n),e==="status"&&t==="disconnected"&&r&&C.removeConnectorId(r)},setActiveNamespace(e){p.activeChain=e;let t=e?p.chains.get(e):void 0,r=t?.networkState?.caipNetwork;r?.id&&e&&(p.activeCaipAddress=t?.accountState?.caipAddress,p.activeCaipNetwork=r,i.setChainNetworkData(e,{caipNetwork:r}),f.setActiveCaipNetworkId(r?.caipNetworkId),we.set({activeChain:e,selectedNetworkId:r?.caipNetworkId}))},setActiveCaipNetwork(e){if(!e)return;p.activeChain!==e.chainNamespace&&i.setIsSwitchingNamespace(!0);let t=p.chains.get(e.chainNamespace);p.activeChain=e.chainNamespace,p.activeCaipNetwork=e,i.setChainNetworkData(e.chainNamespace,{caipNetwork:e}),t?.accountState?.address?p.activeCaipAddress=`${e.chainNamespace}:${e.id}:${t?.accountState?.address}`:p.activeCaipAddress=void 0,i.setAccountProp("caipAddress",p.activeCaipAddress,e.chainNamespace),t&&I.replaceState(t.accountState),x.resetSend(),we.set({activeChain:p.activeChain,selectedNetworkId:p.activeCaipNetwork?.caipNetworkId}),f.setActiveCaipNetworkId(e.caipNetworkId),!i.checkIfSupportedNetwork(e.chainNamespace)&&S.state.enableNetworkSwitch&&!S.state.allowUnsupportedChain&&!N.state.wcBasic&&i.showUnsupportedChainUI()},addCaipNetwork(e){if(!e)return;let t=p.chains.get(e.chainNamespace);t&&t?.caipNetworks?.push(e)},async switchActiveNamespace(e){if(!e)return;let t=e!==i.state.activeChain,r=i.getNetworkData(e)?.caipNetwork,n=i.getCaipNetworkByNamespace(e,r?.id);t&&n&&await i.switchActiveNetwork(n)},async switchActiveNetwork(e){let r=!i.state.chains.get(i.state.activeChain)?.caipNetworks?.some(o=>o.id===p.activeCaipNetwork?.id),n=i.getNetworkControllerClient(e.chainNamespace);if(n){try{await n.switchCaipNetwork(e),r&&G.close()}catch{w.goBack()}$.sendEvent({type:"track",event:"SWITCH_NETWORK",properties:{network:e.caipNetworkId}})}},getNetworkControllerClient(e){let t=e||p.activeChain,r=p.chains.get(t);if(!r)throw new Error("Chain adapter not found");if(!r.networkControllerClient)throw new Error("NetworkController client not set");return r.networkControllerClient},getConnectionControllerClient(e){let t=e||p.activeChain;if(!t)throw new Error("Chain is required to get connection controller client");let r=p.chains.get(t);if(!r?.connectionControllerClient)throw new Error("ConnectionController client not set");return r.connectionControllerClient},getAccountProp(e,t){let r=p.activeChain;if(t&&(r=t),!r)return;let n=p.chains.get(r)?.accountState;if(n)return n[e]},getNetworkProp(e,t){let r=p.chains.get(t)?.networkState;if(r)return r[e]},getRequestedCaipNetworks(e){let t=p.chains.get(e),{approvedCaipNetworkIds:r=[],requestedCaipNetworks:n=[]}=t?.networkState||{};return E.sortRequestedNetworks(r,n)},getAllRequestedCaipNetworks(){let e=[];return p.chains.forEach(t=>{let r=i.getRequestedCaipNetworks(t.namespace);e.push(...r)}),e},setRequestedCaipNetworks(e,t){i.setAdapterNetworkState(t,{requestedCaipNetworks:e});let n=i.getAllRequestedCaipNetworks().map(s=>s.chainNamespace),o=Array.from(new Set(n));C.filterByNamespaces(o)},getAllApprovedCaipNetworkIds(){let e=[];return p.chains.forEach(t=>{let r=i.getApprovedCaipNetworkIds(t.namespace);e.push(...r)}),e},getActiveCaipNetwork(){return p.activeCaipNetwork},getActiveCaipAddress(){return p.activeCaipAddress},getApprovedCaipNetworkIds(e){return p.chains.get(e)?.networkState?.approvedCaipNetworkIds||[]},async setApprovedCaipNetworksData(e){let r=await i.getNetworkControllerClient()?.getApprovedCaipNetworksData();i.setAdapterNetworkState(e,{approvedCaipNetworkIds:r?.approvedCaipNetworkIds,supportsAllNetworks:r?.supportsAllNetworks})},checkIfSupportedNetwork(e,t){let r=t||p.activeCaipNetwork,n=i.getRequestedCaipNetworks(e);return n.length?n?.some(o=>o.id===r?.id):!0},checkIfSupportedChainId(e){return p.activeChain?i.getRequestedCaipNetworks(p.activeChain)?.some(r=>r.id===e):!0},setSmartAccountEnabledNetworks(e,t){i.setAdapterNetworkState(t,{smartAccountEnabledNetworks:e})},checkIfSmartAccountEnabled(){let e=st.caipNetworkIdToNumber(p.activeCaipNetwork?.caipNetworkId),t=p.activeChain;return!t||!e?!1:!!i.getNetworkProp("smartAccountEnabledNetworks",t)?.includes(Number(e))},getActiveNetworkTokenAddress(){let e=p.activeCaipNetwork?.chainNamespace||"eip155",t=p.activeCaipNetwork?.id||1,r=z.NATIVE_TOKEN_ADDRESS[e];return`${e}:${t}:${r}`},showUnsupportedChainUI(){G.open({view:"UnsupportedChain"})},checkIfNamesSupported(){let e=p.activeCaipNetwork;return!!(e?.chainNamespace&&z.NAMES_SUPPORTED_CHAIN_NAMESPACES.includes(e.chainNamespace))},resetNetwork(e){i.setAdapterNetworkState(e,{approvedCaipNetworkIds:void 0,supportsAllNetworks:!0,smartAccountEnabledNetworks:[]})},resetAccount(e){let t=e;if(!t)throw new Error("Chain is required to set account prop");p.activeCaipAddress=void 0,i.setChainAccountData(t,{smartAccountDeployed:!1,currentTab:0,caipAddress:void 0,address:void 0,balance:void 0,balanceSymbol:void 0,profileName:void 0,profileImage:void 0,addressExplorerUrl:void 0,tokenBalance:[],connectedWalletInfo:void 0,preferredAccountTypes:void 0,socialProvider:void 0,socialWindow:void 0,farcasterUrl:void 0,allAccounts:[],user:void 0,status:"disconnected"}),C.removeConnectorId(t)},setIsSwitchingNamespace(e){p.isSwitchingNamespace=e},getFirstCaipNetworkSupportsAuthConnector(){let e=[],t;if(p.chains.forEach(r=>{W.AUTH_CONNECTOR_SUPPORTED_CHAINS.find(n=>n===r.namespace)&&r.namespace&&e.push(r.namespace)}),e.length>0){let r=e[0];return t=r?p.chains.get(r)?.caipNetworks?.[0]:void 0,t}},getAccountData(e){return e?i.state.chains.get(e)?.accountState:I.state},getNetworkData(e){let t=e||p.activeChain;if(t)return i.state.chains.get(t)?.networkState},getCaipNetworkByNamespace(e,t){if(!e)return;let r=i.state.chains.get(e),n=r?.caipNetworks?.find(o=>o.id===t);return n||r?.networkState?.caipNetwork||r?.caipNetworks?.[0]},getRequestedCaipNetworkIds(){let e=C.state.filterByNamespace;return(e?[p.chains.get(e)]:Array.from(p.chains.values())).flatMap(r=>r?.caipNetworks||[]).map(r=>r.caipNetworkId)},getCaipNetworks(e){return e?i.getRequestedCaipNetworks(e):i.getAllRequestedCaipNetworks()}},i=H(Ir);var Tr=E.getApiUrl(),ne=new ue({baseUrl:Tr,clientId:null}),Pr=40,Ht=4,Rr=20,_=v({promises:{},page:1,count:0,featured:[],allFeatured:[],recommended:[],allRecommended:[],wallets:[],filteredWallets:[],search:[],isAnalyticsEnabled:!1,excludedWallets:[],isFetchingRecommendedWallets:!1}),g={state:_,subscribeKey(e,t){return O(_,e,t)},_getSdkProperties(){let{projectId:e,sdkType:t,sdkVersion:r}=S.state;return{projectId:e,st:t||"appkit",sv:r||"html-wagmi-4.2.2"}},_filterOutExtensions(e){return S.state.isUniversalProvider?e.filter(t=>!!(t.mobile_link||t.desktop_link||t.webapp_link)):e},async _fetchWalletImage(e){let t=`${ne.baseUrl}/getWalletImage/${e}`,r=await ne.getBlob({path:t,params:g._getSdkProperties()});ee.setWalletImage(e,URL.createObjectURL(r))},async _fetchNetworkImage(e){let t=`${ne.baseUrl}/public/getAssetImage/${e}`,r=await ne.getBlob({path:t,params:g._getSdkProperties()});ee.setNetworkImage(e,URL.createObjectURL(r))},async _fetchConnectorImage(e){let t=`${ne.baseUrl}/public/getAssetImage/${e}`,r=await ne.getBlob({path:t,params:g._getSdkProperties()});ee.setConnectorImage(e,URL.createObjectURL(r))},async _fetchCurrencyImage(e){let t=`${ne.baseUrl}/public/getCurrencyImage/${e}`,r=await ne.getBlob({path:t,params:g._getSdkProperties()});ee.setCurrencyImage(e,URL.createObjectURL(r))},async _fetchTokenImage(e){let t=`${ne.baseUrl}/public/getTokenImage/${e}`,r=await ne.getBlob({path:t,params:g._getSdkProperties()});ee.setTokenImage(e,URL.createObjectURL(r))},_filterWalletsByPlatform(e){return E.isMobile()?e?.filter(r=>r.mobile_link||r.id===pe.COINBASE.id?!0:i.state.activeChain==="solana"&&(r.id===pe.SOLFLARE.id||r.id===pe.PHANTOM.id)):e},async fetchProjectConfig(){return(await ne.get({path:"/appkit/v1/config",params:g._getSdkProperties()})).features},async fetchAllowedOrigins(){try{let{allowedOrigins:e}=await ne.get({path:"/projects/v1/origins",params:g._getSdkProperties()});return e}catch{return[]}},async fetchNetworkImages(){let t=i.getAllRequestedCaipNetworks()?.map(({assets:r})=>r?.imageId).filter(Boolean).filter(r=>!ht.getNetworkImageById(r));t&&await Promise.allSettled(t.map(r=>g._fetchNetworkImage(r)))},async fetchConnectorImages(){let{connectors:e}=C.state,t=e.map(({imageId:r})=>r).filter(Boolean);await Promise.allSettled(t.map(r=>g._fetchConnectorImage(r)))},async fetchCurrencyImages(e=[]){await Promise.allSettled(e.map(t=>g._fetchCurrencyImage(t)))},async fetchTokenImages(e=[]){await Promise.allSettled(e.map(t=>g._fetchTokenImage(t)))},async fetchWallets(e){let t=e.exclude??[];g._getSdkProperties().sv.startsWith("html-core-")&&t.push(...Object.values(pe).map(s=>s.id));let n=await ne.get({path:"/getWallets",params:{...g._getSdkProperties(),...e,page:String(e.page),entries:String(e.entries),include:e.include?.join(","),exclude:t.join(",")}});return{data:g._filterWalletsByPlatform(n?.data)||[],count:n?.count}},async fetchFeaturedWallets(){let{featuredWalletIds:e}=S.state;if(e?.length){let t={...g._getSdkProperties(),page:1,entries:e?.length??Ht,include:e},{data:r}=await g.fetchWallets(t),n=[...r].sort((s,a)=>e.indexOf(s.id)-e.indexOf(a.id)),o=n.map(s=>s.image_id).filter(Boolean);await Promise.allSettled(o.map(s=>g._fetchWalletImage(s))),_.featured=n,_.allFeatured=n}},async fetchRecommendedWallets(){try{_.isFetchingRecommendedWallets=!0;let{includeWalletIds:e,excludeWalletIds:t,featuredWalletIds:r}=S.state,n=[...t??[],...r??[]].filter(Boolean),o=i.getRequestedCaipNetworkIds().join(","),s={page:1,entries:Ht,include:e,exclude:n,chains:o},{data:a,count:c}=await g.fetchWallets(s),u=f.getRecentWallets(),l=a.map(b=>b.image_id).filter(Boolean),d=u.map(b=>b.image_id).filter(Boolean);await Promise.allSettled([...l,...d].map(b=>g._fetchWalletImage(b))),_.recommended=a,_.allRecommended=a,_.count=c??0}catch{}finally{_.isFetchingRecommendedWallets=!1}},async fetchWalletsByPage({page:e}){let{includeWalletIds:t,excludeWalletIds:r,featuredWalletIds:n}=S.state,o=i.getRequestedCaipNetworkIds().join(","),s=[..._.recommended.map(({id:d})=>d),...r??[],...n??[]].filter(Boolean),a={page:e,entries:Pr,include:t,exclude:s,chains:o},{data:c,count:u}=await g.fetchWallets(a),l=c.slice(0,Rr).map(d=>d.image_id).filter(Boolean);await Promise.allSettled(l.map(d=>g._fetchWalletImage(d))),_.wallets=E.uniqueBy([..._.wallets,...g._filterOutExtensions(c)],"id").filter(d=>d.chains?.some(b=>o.includes(b))),_.count=u>_.count?u:_.count,_.page=e},async initializeExcludedWallets({ids:e}){let t={page:1,entries:e.length,include:e},{data:r}=await g.fetchWallets(t);r&&r.forEach(n=>{_.excludedWallets.push({rdns:n.rdns,name:n.name})})},async searchWallet({search:e,badge:t}){let{includeWalletIds:r,excludeWalletIds:n}=S.state,o=i.getRequestedCaipNetworkIds().join(",");_.search=[];let s={page:1,entries:100,search:e?.trim(),badge_type:t,include:r,exclude:n,chains:o},{data:a}=await g.fetchWallets(s);$.sendEvent({type:"track",event:"SEARCH_WALLET",properties:{badge:t??"",search:e??""}});let c=a.map(u=>u.image_id).filter(Boolean);await Promise.allSettled([...c.map(u=>g._fetchWalletImage(u)),E.wait(300)]),_.search=g._filterOutExtensions(a)},initPromise(e,t){let r=_.promises[e];return r||(_.promises[e]=t())},prefetch({fetchConnectorImages:e=!0,fetchFeaturedWallets:t=!0,fetchRecommendedWallets:r=!0,fetchNetworkImages:n=!0}={}){let o=[e&&g.initPromise("connectorImages",g.fetchConnectorImages),t&&g.initPromise("featuredWallets",g.fetchFeaturedWallets),r&&g.initPromise("recommendedWallets",g.fetchRecommendedWallets),n&&g.initPromise("networkImages",g.fetchNetworkImages)].filter(Boolean);return Promise.allSettled(o)},prefetchAnalyticsConfig(){S.state.features?.analytics&&g.fetchAnalyticsConfig()},async fetchAnalyticsConfig(){try{let{isAnalyticsEnabled:e}=await ne.get({path:"/getAnalyticsConfig",params:g._getSdkProperties()});S.setFeatures({analytics:e})}catch{S.setFeatures({analytics:!1})}},filterByNamespaces(e){if(!e?.length){_.featured=_.allFeatured,_.recommended=_.allRecommended;return}let t=i.getRequestedCaipNetworkIds().join(",");_.featured=_.allFeatured.filter(r=>r.chains?.some(n=>t.includes(n))),_.recommended=_.allRecommended.filter(r=>r.chains?.some(n=>t.includes(n))),_.filteredWallets=_.wallets.filter(r=>r.chains?.some(n=>t.includes(n)))},clearFilterByNamespaces(){_.filteredWallets=[]},setFilterByNamespace(e){if(!e){_.featured=_.allFeatured,_.recommended=_.allRecommended;return}let t=i.getRequestedCaipNetworkIds().join(",");_.featured=_.allFeatured.filter(r=>r.chains?.some(n=>t.includes(n))),_.recommended=_.allRecommended.filter(r=>r.chains?.some(n=>t.includes(n))),_.filteredWallets=_.wallets.filter(r=>r.chains?.some(n=>t.includes(n)))}};var kr=qt(Kt());var xr="wc",Ur="universal_provider",Na=`${xr}@2:${Ur}:`,Dr="https://rpc.walletconnect.org/v1/";var ya=`${Dr}bundler`;var je={getSIWX(){return S.state.siwx},async initializeIfEnabled(){let e=S.state.siwx,t=i.getActiveCaipAddress();if(!(e&&t))return;let[r,n,o]=t.split(":");if(i.checkIfSupportedNetwork(r))try{if((await e.getSessions(`${r}:${n}`,o)).length)return;await G.open({view:"SIWXSignMessage"})}catch(s){console.error("SIWXUtil:initializeIfEnabled",s),$.sendEvent({type:"track",event:"SIWX_AUTH_ERROR",properties:this.getSIWXEventProperties()}),await N._getClient()?.disconnect().catch(console.error),w.reset("Connect"),Q.showError("A problem occurred while trying initialize authentication")}},async requestSignMessage(){let e=S.state.siwx,t=E.getPlainAddress(i.getActiveCaipAddress()),r=i.getActiveCaipNetwork(),n=N._getClient();if(!e)throw new Error("SIWX is not enabled");if(!t)throw new Error("No ActiveCaipAddress found");if(!r)throw new Error("No ActiveCaipNetwork or client found");if(!n)throw new Error("No ConnectionController client found");try{let o=await e.createMessage({chainId:r.caipNetworkId,accountAddress:t}),s=o.toString();C.getConnectorId(r.chainNamespace)===W.CONNECTOR_ID.AUTH&&w.pushTransactionStack({});let c=await n.signMessage(s);await e.addSession({data:o,message:s,signature:c}),G.close(),$.sendEvent({type:"track",event:"SIWX_AUTH_SUCCESS",properties:this.getSIWXEventProperties()})}catch(o){let s=this.getSIWXEventProperties();(!G.state.open||w.state.view==="ApproveTransaction")&&await G.open({view:"SIWXSignMessage"}),s.isSmartAccount?Q.showError("This application might not support Smart Accounts"):Q.showError("Signature declined"),$.sendEvent({type:"track",event:"SIWX_AUTH_ERROR",properties:s}),console.error("SWIXUtil:requestSignMessage",o)}},async cancelSignMessage(){try{this.getSIWX()?.getRequired?.()?await N.disconnect():G.close(),w.reset("Connect"),$.sendEvent({event:"CLICK_CANCEL_SIWX",type:"track",properties:this.getSIWXEventProperties()})}catch(e){console.error("SIWXUtil:cancelSignMessage",e)}},async getSessions(){let e=S.state.siwx,t=E.getPlainAddress(i.getActiveCaipAddress()),r=i.getActiveCaipNetwork();return e&&t&&r?e.getSessions(r.caipNetworkId,t):[]},async isSIWXCloseDisabled(){let e=this.getSIWX();if(e){let t=w.state.view==="ApproveTransaction",r=w.state.view==="SIWXSignMessage";if(t||r)return e.getRequired?.()&&(await this.getSessions()).length===0}return!1},async universalProviderAuthenticate({universalProvider:e,chains:t,methods:r}){let n=je.getSIWX(),o=new Set(t.map(c=>c.split(":")[0]));if(!n||o.size!==1||!o.has("eip155"))return!1;let s=await n.createMessage({chainId:i.getActiveCaipNetwork()?.caipNetworkId||"",accountAddress:""}),a=await e.authenticate({nonce:s.nonce,domain:s.domain,uri:s.uri,exp:s.expirationTime,iat:s.issuedAt,nbf:s.notBefore,requestId:s.requestId,version:s.version,resources:s.resources,statement:s.statement,chainId:s.chainId,methods:r,chains:[s.chainId,...t.filter(c=>c!==s.chainId)]});if(Q.showLoading("Authenticating...",{autoClose:!1}),I.setConnectedWalletInfo({...a.session.peer.metadata,name:a.session.peer.metadata.name,icon:a.session.peer.metadata.icons?.[0],type:"WALLET_CONNECT"},Array.from(o)[0]),a?.auths?.length){let c=a.auths.map(u=>{let l=e.client.formatAuthMessage({request:u.p,iss:u.p.iss});return{data:{...u.p,accountAddress:u.p.iss.split(":").slice(-1).join(""),chainId:u.p.iss.split(":").slice(2,4).join(":"),uri:u.p.aud,version:u.p.version||s.version,expirationTime:u.p.exp,issuedAt:u.p.iat,notBefore:u.p.nbf},message:l,signature:u.s.s,cacao:u}});try{await n.setSessions(c),$.sendEvent({type:"track",event:"SIWX_AUTH_SUCCESS",properties:je.getSIWXEventProperties()})}catch(u){throw console.error("SIWX:universalProviderAuth - failed to set sessions",u),$.sendEvent({type:"track",event:"SIWX_AUTH_ERROR",properties:je.getSIWXEventProperties()}),await e.disconnect().catch(console.error),u}finally{Q.hide()}}return!0},getSIWXEventProperties(){let e=i.state.activeChain;return{network:i.state.activeCaipNetwork?.caipNetworkId||"",isSmartAccount:I.state.preferredAccountTypes?.[e]===be.ACCOUNT_TYPES.SMART_ACCOUNT}},async clearSessions(){let e=this.getSIWX();e&&await e.setSessions([])}};var Mr={isUnsupportedChainView(){return w.state.view==="UnsupportedChain"||w.state.view==="SwitchNetwork"&&w.state.history.includes("UnsupportedChain")},async safeClose(){if(this.isUnsupportedChainView()){G.shake();return}if(await je.isSIWXCloseDisabled()){G.shake();return}G.close()}};var Xe={id:"2b92315d-eab7-5bef-84fa-089a131333f5",name:"USD Coin",symbol:"USDC",networks:[{name:"ethereum-mainnet",display_name:"Ethereum",chain_id:"1",contract_address:"0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"},{name:"polygon-mainnet",display_name:"Polygon",chain_id:"137",contract_address:"0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"}]},bt={id:"USD",payment_method_limits:[{id:"card",min:"10.00",max:"7500.00"},{id:"ach_bank_account",min:"10.00",max:"25000.00"}]},Lr={providers:lt,selectedProvider:null,error:null,purchaseCurrency:Xe,paymentCurrency:bt,purchaseCurrencies:[Xe],paymentCurrencies:[],quotesLoading:!1},R=v(Lr),Br={state:R,subscribe(e){return B(R,()=>e(R))},subscribeKey(e,t){return O(R,e,t)},setSelectedProvider(e){if(e&&e.name==="meld"){let t=i.state.activeChain===W.CHAIN.SOLANA?"SOL":"USDC",r=I.state.address??"",n=new URL(e.url);n.searchParams.append("publicKey",Tt),n.searchParams.append("destinationCurrencyCode",t),n.searchParams.append("walletAddress",r),n.searchParams.append("externalCustomerId",S.state.projectId),R.selectedProvider={...e,url:n.toString()}}else R.selectedProvider=e},setOnrampProviders(e){if(Array.isArray(e)&&e.every(t=>typeof t=="string")){let t=e,r=lt.filter(n=>t.includes(n.name));R.providers=r}else R.providers=[]},setPurchaseCurrency(e){R.purchaseCurrency=e},setPaymentCurrency(e){R.paymentCurrency=e},setPurchaseAmount(e){Et.state.purchaseAmount=e},setPaymentAmount(e){Et.state.paymentAmount=e},async getAvailableCurrencies(){let e=await m.getOnrampOptions();R.purchaseCurrencies=e.purchaseCurrencies,R.paymentCurrencies=e.paymentCurrencies,R.paymentCurrency=e.paymentCurrencies[0]||bt,R.purchaseCurrency=e.purchaseCurrencies[0]||Xe,await g.fetchCurrencyImages(e.paymentCurrencies.map(t=>t.id)),await g.fetchTokenImages(e.purchaseCurrencies.map(t=>t.symbol))},async getQuote(){R.quotesLoading=!0;try{let e=await m.getOnrampQuote({purchaseCurrency:R.purchaseCurrency,paymentCurrency:R.paymentCurrency,amount:R.paymentAmount?.toString()||"0",network:R.purchaseCurrency?.symbol});return R.quotesLoading=!1,R.purchaseAmount=Number(e?.purchaseAmount.amount),e}catch(e){return R.error=e.message,R.quotesLoading=!1,null}finally{R.quotesLoading=!1}},resetState(){R.selectedProvider=null,R.error=null,R.purchaseCurrency=Xe,R.paymentCurrency=bt,R.purchaseCurrencies=[Xe],R.paymentCurrencies=[],R.paymentAmount=void 0,R.purchaseAmount=void 0,R.quotesLoading=!1}},Et=H(Br);var de=v({message:"",open:!1,triggerRect:{width:0,height:0,top:0,left:0},variant:"shade"}),Hr={state:de,subscribe(e){return B(de,()=>e(de))},subscribeKey(e,t){return O(de,e,t)},showTooltip({message:e,triggerRect:t,variant:r}){de.open=!0,de.message=e,de.triggerRect=t,de.variant=r},hide(){de.open=!1,de.message="",de.triggerRect={width:0,height:0,top:0,left:0}}},Fr=H(Hr);var Ft={convertEVMChainIdToCoinType(e){if(e>=2147483648)throw new Error("Invalid chainId");return(2147483648|e)>>>0}};var ce=v({suggestions:[],loading:!1}),Wr={state:ce,subscribe(e){return B(ce,()=>e(ce))},subscribeKey(e,t){return O(ce,e,t)},async resolveName(e){try{return await m.lookupEnsName(e)}catch(t){let r=t;throw new Error(r?.reasons?.[0]?.description||"Error resolving name")}},async isNameRegistered(e){try{return await m.lookupEnsName(e),!0}catch{return!1}},async getSuggestions(e){try{ce.loading=!0,ce.suggestions=[];let t=await m.getEnsNameSuggestions(e);return ce.suggestions=t.suggestions.map(r=>({...r,name:r.name}))||[],ce.suggestions}catch(t){let r=nt.parseEnsApiError(t,"Error fetching name suggestions");throw new Error(r)}finally{ce.loading=!1}},async getNamesForAddress(e){try{if(!i.state.activeCaipNetwork)return[];let r=f.getEnsFromCacheForAddress(e);if(r)return r;let n=await m.reverseLookupEnsName({address:e});return f.updateEnsCache({address:e,ens:n,timestamp:Date.now()}),n}catch(t){let r=nt.parseEnsApiError(t,"Error fetching names for address");throw new Error(r)}},async registerName(e){let t=i.state.activeCaipNetwork;if(!t)throw new Error("Network not found");let r=I.state.address,n=C.getAuthConnector();if(!r||!n)throw new Error("Address or auth connector not found");ce.loading=!0;try{let o=JSON.stringify({name:e,attributes:{},timestamp:Math.floor(Date.now()/1e3)});w.pushTransactionStack({onCancel(){w.replace("RegisterAccountName")}});let s=await N.signMessage(o);ce.loading=!1;let a=t.id;if(!a)throw new Error("Network not found");let c=Ft.convertEVMChainIdToCoinType(Number(a));await m.registerEnsName({coinType:c,address:r,signature:s,message:o}),I.setProfileName(e,t.chainNamespace),w.replace("RegisterAccountNameSuccess")}catch(o){let s=nt.parseEnsApiError(o,`Error registering name ${e}`);throw w.replace("RegisterAccountName"),new Error(s)}finally{ce.loading=!1}},validateName(e){return/^[a-zA-Z0-9-]{4,}$/u.test(e)},parseEnsApiError(e,t){return e?.reasons?.[0]?.description||t}},nt=H(Wr);var Je,ye,_e;function $r(e,t){Je=document.createElement("style"),ye=document.createElement("style"),_e=document.createElement("style"),Je.textContent=qe(e).core.cssText,ye.textContent=qe(e).dark.cssText,_e.textContent=qe(e).light.cssText,document.head.appendChild(Je),document.head.appendChild(ye),document.head.appendChild(_e),Wt(t)}function Wt(e){ye&&_e&&(e==="light"?(ye.removeAttribute("media"),_e.media="enabled"):(_e.removeAttribute("media"),ye.media="enabled"))}function jr(e){Je&&ye&&_e&&(Je.textContent=qe(e).core.cssText,ye.textContent=qe(e).dark.cssText,_e.textContent=qe(e).light.cssText)}function qe(e){return{core:Pe`
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
      @keyframes w3m-shake {
        0% {
          transform: scale(1) rotate(0deg);
        }
        20% {
          transform: scale(1) rotate(-1deg);
        }
        40% {
          transform: scale(1) rotate(1.5deg);
        }
        60% {
          transform: scale(1) rotate(-1.5deg);
        }
        80% {
          transform: scale(1) rotate(1deg);
        }
        100% {
          transform: scale(1) rotate(0deg);
        }
      }
      @keyframes w3m-iframe-fade-out {
        0% {
          opacity: 1;
        }
        100% {
          opacity: 0;
        }
      }
      @keyframes w3m-iframe-zoom-in {
        0% {
          transform: translateY(50px);
          opacity: 0;
        }
        100% {
          transform: translateY(0px);
          opacity: 1;
        }
      }
      @keyframes w3m-iframe-zoom-in-mobile {
        0% {
          transform: scale(0.95);
          opacity: 0;
        }
        100% {
          transform: scale(1);
          opacity: 1;
        }
      }
      :root {
        --w3m-modal-width: 360px;
        --w3m-color-mix-strength: ${se(e?.["--w3m-color-mix-strength"]?`${e["--w3m-color-mix-strength"]}%`:"0%")};
        --w3m-font-family: ${se(e?.["--w3m-font-family"]||"Inter, Segoe UI, Roboto, Oxygen, Ubuntu, Cantarell, Fira Sans, Droid Sans, Helvetica Neue, sans-serif;")};
        --w3m-font-size-master: ${se(e?.["--w3m-font-size-master"]||"10px")};
        --w3m-border-radius-master: ${se(e?.["--w3m-border-radius-master"]||"4px")};
        --w3m-z-index: ${se(e?.["--w3m-z-index"]||999)};

        --wui-font-family: var(--w3m-font-family);

        --wui-font-size-mini: calc(var(--w3m-font-size-master) * 0.8);
        --wui-font-size-micro: var(--w3m-font-size-master);
        --wui-font-size-tiny: calc(var(--w3m-font-size-master) * 1.2);
        --wui-font-size-small: calc(var(--w3m-font-size-master) * 1.4);
        --wui-font-size-paragraph: calc(var(--w3m-font-size-master) * 1.6);
        --wui-font-size-medium: calc(var(--w3m-font-size-master) * 1.8);
        --wui-font-size-large: calc(var(--w3m-font-size-master) * 2);
        --wui-font-size-title-6: calc(var(--w3m-font-size-master) * 2.2);
        --wui-font-size-medium-title: calc(var(--w3m-font-size-master) * 2.4);
        --wui-font-size-2xl: calc(var(--w3m-font-size-master) * 4);

        --wui-border-radius-5xs: var(--w3m-border-radius-master);
        --wui-border-radius-4xs: calc(var(--w3m-border-radius-master) * 1.5);
        --wui-border-radius-3xs: calc(var(--w3m-border-radius-master) * 2);
        --wui-border-radius-xxs: calc(var(--w3m-border-radius-master) * 3);
        --wui-border-radius-xs: calc(var(--w3m-border-radius-master) * 4);
        --wui-border-radius-s: calc(var(--w3m-border-radius-master) * 5);
        --wui-border-radius-m: calc(var(--w3m-border-radius-master) * 7);
        --wui-border-radius-l: calc(var(--w3m-border-radius-master) * 9);
        --wui-border-radius-3xl: calc(var(--w3m-border-radius-master) * 20);

        --wui-font-weight-light: 400;
        --wui-font-weight-regular: 500;
        --wui-font-weight-medium: 600;
        --wui-font-weight-bold: 700;

        --wui-letter-spacing-2xl: -1.6px;
        --wui-letter-spacing-medium-title: -0.96px;
        --wui-letter-spacing-title-6: -0.88px;
        --wui-letter-spacing-large: -0.8px;
        --wui-letter-spacing-medium: -0.72px;
        --wui-letter-spacing-paragraph: -0.64px;
        --wui-letter-spacing-small: -0.56px;
        --wui-letter-spacing-tiny: -0.48px;
        --wui-letter-spacing-micro: -0.2px;
        --wui-letter-spacing-mini: -0.16px;

        --wui-spacing-0: 0px;
        --wui-spacing-4xs: 2px;
        --wui-spacing-3xs: 4px;
        --wui-spacing-xxs: 6px;
        --wui-spacing-2xs: 7px;
        --wui-spacing-xs: 8px;
        --wui-spacing-1xs: 10px;
        --wui-spacing-s: 12px;
        --wui-spacing-m: 14px;
        --wui-spacing-l: 16px;
        --wui-spacing-2l: 18px;
        --wui-spacing-xl: 20px;
        --wui-spacing-xxl: 24px;
        --wui-spacing-2xl: 32px;
        --wui-spacing-3xl: 40px;
        --wui-spacing-4xl: 90px;
        --wui-spacing-5xl: 95px;

        --wui-icon-box-size-xxs: 14px;
        --wui-icon-box-size-xs: 20px;
        --wui-icon-box-size-sm: 24px;
        --wui-icon-box-size-md: 32px;
        --wui-icon-box-size-mdl: 36px;
        --wui-icon-box-size-lg: 40px;
        --wui-icon-box-size-2lg: 48px;
        --wui-icon-box-size-xl: 64px;

        --wui-icon-size-inherit: inherit;
        --wui-icon-size-xxs: 10px;
        --wui-icon-size-xs: 12px;
        --wui-icon-size-sm: 14px;
        --wui-icon-size-md: 16px;
        --wui-icon-size-mdl: 18px;
        --wui-icon-size-lg: 20px;
        --wui-icon-size-xl: 24px;
        --wui-icon-size-xxl: 28px;

        --wui-wallet-image-size-inherit: inherit;
        --wui-wallet-image-size-sm: 40px;
        --wui-wallet-image-size-md: 56px;
        --wui-wallet-image-size-lg: 80px;

        --wui-visual-size-size-inherit: inherit;
        --wui-visual-size-sm: 40px;
        --wui-visual-size-md: 55px;
        --wui-visual-size-lg: 80px;

        --wui-box-size-md: 100px;
        --wui-box-size-lg: 120px;

        --wui-ease-out-power-2: cubic-bezier(0, 0, 0.22, 1);
        --wui-ease-out-power-1: cubic-bezier(0, 0, 0.55, 1);

        --wui-ease-in-power-3: cubic-bezier(0.66, 0, 1, 1);
        --wui-ease-in-power-2: cubic-bezier(0.45, 0, 1, 1);
        --wui-ease-in-power-1: cubic-bezier(0.3, 0, 1, 1);

        --wui-ease-inout-power-1: cubic-bezier(0.45, 0, 0.55, 1);

        --wui-duration-lg: 200ms;
        --wui-duration-md: 125ms;
        --wui-duration-sm: 75ms;

        --wui-path-network-sm: path(
          'M15.4 2.1a5.21 5.21 0 0 1 5.2 0l11.61 6.7a5.21 5.21 0 0 1 2.61 4.52v13.4c0 1.87-1 3.59-2.6 4.52l-11.61 6.7c-1.62.93-3.6.93-5.22 0l-11.6-6.7a5.21 5.21 0 0 1-2.61-4.51v-13.4c0-1.87 1-3.6 2.6-4.52L15.4 2.1Z'
        );

        --wui-path-network-md: path(
          'M43.4605 10.7248L28.0485 1.61089C25.5438 0.129705 22.4562 0.129705 19.9515 1.61088L4.53951 10.7248C2.03626 12.2051 0.5 14.9365 0.5 17.886V36.1139C0.5 39.0635 2.03626 41.7949 4.53951 43.2752L19.9515 52.3891C22.4562 53.8703 25.5438 53.8703 28.0485 52.3891L43.4605 43.2752C45.9637 41.7949 47.5 39.0635 47.5 36.114V17.8861C47.5 14.9365 45.9637 12.2051 43.4605 10.7248Z'
        );

        --wui-path-network-lg: path(
          'M78.3244 18.926L50.1808 2.45078C45.7376 -0.150261 40.2624 -0.150262 35.8192 2.45078L7.6756 18.926C3.23322 21.5266 0.5 26.3301 0.5 31.5248V64.4752C0.5 69.6699 3.23322 74.4734 7.6756 77.074L35.8192 93.5492C40.2624 96.1503 45.7376 96.1503 50.1808 93.5492L78.3244 77.074C82.7668 74.4734 85.5 69.6699 85.5 64.4752V31.5248C85.5 26.3301 82.7668 21.5266 78.3244 18.926Z'
        );

        --wui-width-network-sm: 36px;
        --wui-width-network-md: 48px;
        --wui-width-network-lg: 86px;

        --wui-height-network-sm: 40px;
        --wui-height-network-md: 54px;
        --wui-height-network-lg: 96px;

        --wui-icon-size-network-xs: 12px;
        --wui-icon-size-network-sm: 16px;
        --wui-icon-size-network-md: 24px;
        --wui-icon-size-network-lg: 42px;

        --wui-color-inherit: inherit;

        --wui-color-inverse-100: #fff;
        --wui-color-inverse-000: #000;

        --wui-cover: rgba(20, 20, 20, 0.8);

        --wui-color-modal-bg: var(--wui-color-modal-bg-base);

        --wui-color-accent-100: var(--wui-color-accent-base-100);
        --wui-color-accent-090: var(--wui-color-accent-base-090);
        --wui-color-accent-080: var(--wui-color-accent-base-080);

        --wui-color-success-100: var(--wui-color-success-base-100);
        --wui-color-success-125: var(--wui-color-success-base-125);

        --wui-color-warning-100: var(--wui-color-warning-base-100);

        --wui-color-error-100: var(--wui-color-error-base-100);
        --wui-color-error-125: var(--wui-color-error-base-125);

        --wui-color-blue-100: var(--wui-color-blue-base-100);
        --wui-color-blue-90: var(--wui-color-blue-base-90);

        --wui-icon-box-bg-error-100: var(--wui-icon-box-bg-error-base-100);
        --wui-icon-box-bg-blue-100: var(--wui-icon-box-bg-blue-base-100);
        --wui-icon-box-bg-success-100: var(--wui-icon-box-bg-success-base-100);
        --wui-icon-box-bg-inverse-100: var(--wui-icon-box-bg-inverse-base-100);

        --wui-all-wallets-bg-100: var(--wui-all-wallets-bg-100);

        --wui-avatar-border: var(--wui-avatar-border-base);

        --wui-thumbnail-border: var(--wui-thumbnail-border-base);

        --wui-wallet-button-bg: var(--wui-wallet-button-bg-base);

        --wui-box-shadow-blue: var(--wui-color-accent-glass-020);
      }

      @supports (background: color-mix(in srgb, white 50%, black)) {
        :root {
          --wui-color-modal-bg: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-modal-bg-base)
          );

          --wui-box-shadow-blue: color-mix(in srgb, var(--wui-color-accent-100) 20%, transparent);

          --wui-color-accent-100: color-mix(
            in srgb,
            var(--wui-color-accent-base-100) 100%,
            transparent
          );
          --wui-color-accent-090: color-mix(
            in srgb,
            var(--wui-color-accent-base-100) 90%,
            transparent
          );
          --wui-color-accent-080: color-mix(
            in srgb,
            var(--wui-color-accent-base-100) 80%,
            transparent
          );
          --wui-color-accent-glass-090: color-mix(
            in srgb,
            var(--wui-color-accent-base-100) 90%,
            transparent
          );
          --wui-color-accent-glass-080: color-mix(
            in srgb,
            var(--wui-color-accent-base-100) 80%,
            transparent
          );
          --wui-color-accent-glass-020: color-mix(
            in srgb,
            var(--wui-color-accent-base-100) 20%,
            transparent
          );
          --wui-color-accent-glass-015: color-mix(
            in srgb,
            var(--wui-color-accent-base-100) 15%,
            transparent
          );
          --wui-color-accent-glass-010: color-mix(
            in srgb,
            var(--wui-color-accent-base-100) 10%,
            transparent
          );
          --wui-color-accent-glass-005: color-mix(
            in srgb,
            var(--wui-color-accent-base-100) 5%,
            transparent
          );
          --wui-color-accent-002: color-mix(
            in srgb,
            var(--wui-color-accent-base-100) 2%,
            transparent
          );

          --wui-color-fg-100: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-fg-100)
          );
          --wui-color-fg-125: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-fg-125)
          );
          --wui-color-fg-150: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-fg-150)
          );
          --wui-color-fg-175: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-fg-175)
          );
          --wui-color-fg-200: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-fg-200)
          );
          --wui-color-fg-225: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-fg-225)
          );
          --wui-color-fg-250: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-fg-250)
          );
          --wui-color-fg-275: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-fg-275)
          );
          --wui-color-fg-300: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-fg-300)
          );
          --wui-color-fg-325: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-fg-325)
          );
          --wui-color-fg-350: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-fg-350)
          );

          --wui-color-bg-100: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-bg-100)
          );
          --wui-color-bg-125: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-bg-125)
          );
          --wui-color-bg-150: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-bg-150)
          );
          --wui-color-bg-175: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-bg-175)
          );
          --wui-color-bg-200: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-bg-200)
          );
          --wui-color-bg-225: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-bg-225)
          );
          --wui-color-bg-250: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-bg-250)
          );
          --wui-color-bg-275: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-bg-275)
          );
          --wui-color-bg-300: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-bg-300)
          );
          --wui-color-bg-325: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-bg-325)
          );
          --wui-color-bg-350: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-bg-350)
          );

          --wui-color-success-100: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-success-base-100)
          );
          --wui-color-success-125: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-success-base-125)
          );

          --wui-color-warning-100: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-warning-base-100)
          );

          --wui-color-error-100: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-error-base-100)
          );
          --wui-color-blue-100: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-blue-base-100)
          );
          --wui-color-blue-90: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-blue-base-90)
          );
          --wui-color-error-125: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-color-error-base-125)
          );

          --wui-icon-box-bg-error-100: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-icon-box-bg-error-base-100)
          );
          --wui-icon-box-bg-accent-100: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-icon-box-bg-blue-base-100)
          );
          --wui-icon-box-bg-success-100: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-icon-box-bg-success-base-100)
          );
          --wui-icon-box-bg-inverse-100: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-icon-box-bg-inverse-base-100)
          );

          --wui-all-wallets-bg-100: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-all-wallets-bg-100)
          );

          --wui-avatar-border: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-avatar-border-base)
          );

          --wui-thumbnail-border: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-thumbnail-border-base)
          );

          --wui-wallet-button-bg: color-mix(
            in srgb,
            var(--w3m-color-mix) var(--w3m-color-mix-strength),
            var(--wui-wallet-button-bg-base)
          );
        }
      }
    `,light:Pe`
      :root {
        --w3m-color-mix: ${se(e?.["--w3m-color-mix"]||"#fff")};
        --w3m-accent: ${se(ie(e,"dark")["--w3m-accent"])};
        --w3m-default: #fff;

        --wui-color-modal-bg-base: ${se(ie(e,"dark")["--w3m-background"])};
        --wui-color-accent-base-100: var(--w3m-accent);

        --wui-color-blueberry-100: hsla(230, 100%, 67%, 1);
        --wui-color-blueberry-090: hsla(231, 76%, 61%, 1);
        --wui-color-blueberry-080: hsla(230, 59%, 55%, 1);
        --wui-color-blueberry-050: hsla(231, 100%, 70%, 0.1);

        --wui-color-fg-100: #e4e7e7;
        --wui-color-fg-125: #d0d5d5;
        --wui-color-fg-150: #a8b1b1;
        --wui-color-fg-175: #a8b0b0;
        --wui-color-fg-200: #949e9e;
        --wui-color-fg-225: #868f8f;
        --wui-color-fg-250: #788080;
        --wui-color-fg-275: #788181;
        --wui-color-fg-300: #6e7777;
        --wui-color-fg-325: #9a9a9a;
        --wui-color-fg-350: #363636;

        --wui-color-bg-100: #141414;
        --wui-color-bg-125: #191a1a;
        --wui-color-bg-150: #1e1f1f;
        --wui-color-bg-175: #222525;
        --wui-color-bg-200: #272a2a;
        --wui-color-bg-225: #2c3030;
        --wui-color-bg-250: #313535;
        --wui-color-bg-275: #363b3b;
        --wui-color-bg-300: #3b4040;
        --wui-color-bg-325: #252525;
        --wui-color-bg-350: #ffffff;

        --wui-color-success-base-100: #26d962;
        --wui-color-success-base-125: #30a46b;

        --wui-color-warning-base-100: #f3a13f;

        --wui-color-error-base-100: #f25a67;
        --wui-color-error-base-125: #df4a34;

        --wui-color-blue-base-100: rgba(102, 125, 255, 1);
        --wui-color-blue-base-90: rgba(102, 125, 255, 0.9);

        --wui-color-success-glass-001: rgba(38, 217, 98, 0.01);
        --wui-color-success-glass-002: rgba(38, 217, 98, 0.02);
        --wui-color-success-glass-005: rgba(38, 217, 98, 0.05);
        --wui-color-success-glass-010: rgba(38, 217, 98, 0.1);
        --wui-color-success-glass-015: rgba(38, 217, 98, 0.15);
        --wui-color-success-glass-020: rgba(38, 217, 98, 0.2);
        --wui-color-success-glass-025: rgba(38, 217, 98, 0.25);
        --wui-color-success-glass-030: rgba(38, 217, 98, 0.3);
        --wui-color-success-glass-060: rgba(38, 217, 98, 0.6);
        --wui-color-success-glass-080: rgba(38, 217, 98, 0.8);

        --wui-color-success-glass-reown-020: rgba(48, 164, 107, 0.2);

        --wui-color-warning-glass-reown-020: rgba(243, 161, 63, 0.2);

        --wui-color-error-glass-001: rgba(242, 90, 103, 0.01);
        --wui-color-error-glass-002: rgba(242, 90, 103, 0.02);
        --wui-color-error-glass-005: rgba(242, 90, 103, 0.05);
        --wui-color-error-glass-010: rgba(242, 90, 103, 0.1);
        --wui-color-error-glass-015: rgba(242, 90, 103, 0.15);
        --wui-color-error-glass-020: rgba(242, 90, 103, 0.2);
        --wui-color-error-glass-025: rgba(242, 90, 103, 0.25);
        --wui-color-error-glass-030: rgba(242, 90, 103, 0.3);
        --wui-color-error-glass-060: rgba(242, 90, 103, 0.6);
        --wui-color-error-glass-080: rgba(242, 90, 103, 0.8);

        --wui-color-error-glass-reown-020: rgba(223, 74, 52, 0.2);

        --wui-color-gray-glass-001: rgba(255, 255, 255, 0.01);
        --wui-color-gray-glass-002: rgba(255, 255, 255, 0.02);
        --wui-color-gray-glass-005: rgba(255, 255, 255, 0.05);
        --wui-color-gray-glass-010: rgba(255, 255, 255, 0.1);
        --wui-color-gray-glass-015: rgba(255, 255, 255, 0.15);
        --wui-color-gray-glass-020: rgba(255, 255, 255, 0.2);
        --wui-color-gray-glass-025: rgba(255, 255, 255, 0.25);
        --wui-color-gray-glass-030: rgba(255, 255, 255, 0.3);
        --wui-color-gray-glass-060: rgba(255, 255, 255, 0.6);
        --wui-color-gray-glass-080: rgba(255, 255, 255, 0.8);
        --wui-color-gray-glass-090: rgba(255, 255, 255, 0.9);

        --wui-color-dark-glass-100: rgba(42, 42, 42, 1);

        --wui-icon-box-bg-error-base-100: #3c2426;
        --wui-icon-box-bg-blue-base-100: #20303f;
        --wui-icon-box-bg-success-base-100: #1f3a28;
        --wui-icon-box-bg-inverse-base-100: #243240;

        --wui-all-wallets-bg-100: #222b35;

        --wui-avatar-border-base: #252525;

        --wui-thumbnail-border-base: #252525;

        --wui-wallet-button-bg-base: var(--wui-color-bg-125);

        --w3m-card-embedded-shadow-color: rgb(17 17 18 / 25%);
      }
    `,dark:Pe`
      :root {
        --w3m-color-mix: ${se(e?.["--w3m-color-mix"]||"#000")};
        --w3m-accent: ${se(ie(e,"light")["--w3m-accent"])};
        --w3m-default: #000;

        --wui-color-modal-bg-base: ${se(ie(e,"light")["--w3m-background"])};
        --wui-color-accent-base-100: var(--w3m-accent);

        --wui-color-blueberry-100: hsla(231, 100%, 70%, 1);
        --wui-color-blueberry-090: hsla(231, 97%, 72%, 1);
        --wui-color-blueberry-080: hsla(231, 92%, 74%, 1);

        --wui-color-fg-100: #141414;
        --wui-color-fg-125: #2d3131;
        --wui-color-fg-150: #474d4d;
        --wui-color-fg-175: #636d6d;
        --wui-color-fg-200: #798686;
        --wui-color-fg-225: #828f8f;
        --wui-color-fg-250: #8b9797;
        --wui-color-fg-275: #95a0a0;
        --wui-color-fg-300: #9ea9a9;
        --wui-color-fg-325: #9a9a9a;
        --wui-color-fg-350: #d0d0d0;

        --wui-color-bg-100: #ffffff;
        --wui-color-bg-125: #f5fafa;
        --wui-color-bg-150: #f3f8f8;
        --wui-color-bg-175: #eef4f4;
        --wui-color-bg-200: #eaf1f1;
        --wui-color-bg-225: #e5eded;
        --wui-color-bg-250: #e1e9e9;
        --wui-color-bg-275: #dce7e7;
        --wui-color-bg-300: #d8e3e3;
        --wui-color-bg-325: #f3f3f3;
        --wui-color-bg-350: #202020;

        --wui-color-success-base-100: #26b562;
        --wui-color-success-base-125: #30a46b;

        --wui-color-warning-base-100: #f3a13f;

        --wui-color-error-base-100: #f05142;
        --wui-color-error-base-125: #df4a34;

        --wui-color-blue-base-100: rgba(102, 125, 255, 1);
        --wui-color-blue-base-90: rgba(102, 125, 255, 0.9);

        --wui-color-success-glass-001: rgba(38, 181, 98, 0.01);
        --wui-color-success-glass-002: rgba(38, 181, 98, 0.02);
        --wui-color-success-glass-005: rgba(38, 181, 98, 0.05);
        --wui-color-success-glass-010: rgba(38, 181, 98, 0.1);
        --wui-color-success-glass-015: rgba(38, 181, 98, 0.15);
        --wui-color-success-glass-020: rgba(38, 181, 98, 0.2);
        --wui-color-success-glass-025: rgba(38, 181, 98, 0.25);
        --wui-color-success-glass-030: rgba(38, 181, 98, 0.3);
        --wui-color-success-glass-060: rgba(38, 181, 98, 0.6);
        --wui-color-success-glass-080: rgba(38, 181, 98, 0.8);

        --wui-color-success-glass-reown-020: rgba(48, 164, 107, 0.2);

        --wui-color-warning-glass-reown-020: rgba(243, 161, 63, 0.2);

        --wui-color-error-glass-001: rgba(240, 81, 66, 0.01);
        --wui-color-error-glass-002: rgba(240, 81, 66, 0.02);
        --wui-color-error-glass-005: rgba(240, 81, 66, 0.05);
        --wui-color-error-glass-010: rgba(240, 81, 66, 0.1);
        --wui-color-error-glass-015: rgba(240, 81, 66, 0.15);
        --wui-color-error-glass-020: rgba(240, 81, 66, 0.2);
        --wui-color-error-glass-025: rgba(240, 81, 66, 0.25);
        --wui-color-error-glass-030: rgba(240, 81, 66, 0.3);
        --wui-color-error-glass-060: rgba(240, 81, 66, 0.6);
        --wui-color-error-glass-080: rgba(240, 81, 66, 0.8);

        --wui-color-error-glass-reown-020: rgba(223, 74, 52, 0.2);

        --wui-icon-box-bg-error-base-100: #f4dfdd;
        --wui-icon-box-bg-blue-base-100: #d9ecfb;
        --wui-icon-box-bg-success-base-100: #daf0e4;
        --wui-icon-box-bg-inverse-base-100: #dcecfc;

        --wui-all-wallets-bg-100: #e8f1fa;

        --wui-avatar-border-base: #f3f4f4;

        --wui-thumbnail-border-base: #eaefef;

        --wui-wallet-button-bg-base: var(--wui-color-bg-125);

        --wui-color-gray-glass-001: rgba(0, 0, 0, 0.01);
        --wui-color-gray-glass-002: rgba(0, 0, 0, 0.02);
        --wui-color-gray-glass-005: rgba(0, 0, 0, 0.05);
        --wui-color-gray-glass-010: rgba(0, 0, 0, 0.1);
        --wui-color-gray-glass-015: rgba(0, 0, 0, 0.15);
        --wui-color-gray-glass-020: rgba(0, 0, 0, 0.2);
        --wui-color-gray-glass-025: rgba(0, 0, 0, 0.25);
        --wui-color-gray-glass-030: rgba(0, 0, 0, 0.3);
        --wui-color-gray-glass-060: rgba(0, 0, 0, 0.6);
        --wui-color-gray-glass-080: rgba(0, 0, 0, 0.8);
        --wui-color-gray-glass-090: rgba(0, 0, 0, 0.9);

        --wui-color-dark-glass-100: rgba(233, 233, 233, 1);

        --w3m-card-embedded-shadow-color: rgb(224 225 233 / 25%);
      }
    `}}var zc=Pe`
  *,
  *::after,
  *::before,
  :host {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
    font-style: normal;
    text-rendering: optimizeSpeed;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    -webkit-tap-highlight-color: transparent;
    font-family: var(--wui-font-family);
    backface-visibility: hidden;
  }
`,Yc=Pe`
  button,
  a {
    cursor: pointer;
    display: flex;
    justify-content: center;
    align-items: center;
    position: relative;
    transition:
      color var(--wui-duration-lg) var(--wui-ease-out-power-1),
      background-color var(--wui-duration-lg) var(--wui-ease-out-power-1),
      border var(--wui-duration-lg) var(--wui-ease-out-power-1),
      border-radius var(--wui-duration-lg) var(--wui-ease-out-power-1),
      box-shadow var(--wui-duration-lg) var(--wui-ease-out-power-1);
    will-change: background-color, color, border, box-shadow, border-radius;
    outline: none;
    border: none;
    column-gap: var(--wui-spacing-3xs);
    background-color: transparent;
    text-decoration: none;
  }

  wui-flex {
    transition: border-radius var(--wui-duration-lg) var(--wui-ease-out-power-1);
    will-change: border-radius;
  }

  button:disabled > wui-wallet-image,
  button:disabled > wui-all-wallets-image,
  button:disabled > wui-network-image,
  button:disabled > wui-image,
  button:disabled > wui-transaction-visual,
  button:disabled > wui-logo {
    filter: grayscale(1);
  }

  @media (hover: hover) and (pointer: fine) {
    button:hover:enabled {
      background-color: var(--wui-color-gray-glass-005);
    }

    button:active:enabled {
      background-color: var(--wui-color-gray-glass-010);
    }
  }

  button:disabled > wui-icon-box {
    opacity: 0.5;
  }

  input {
    border: none;
    outline: none;
    appearance: none;
  }
`,Xc=Pe`
  .wui-color-inherit {
    color: var(--wui-color-inherit);
  }

  .wui-color-accent-100 {
    color: var(--wui-color-accent-100);
  }

  .wui-color-error-100 {
    color: var(--wui-color-error-100);
  }

  .wui-color-blue-100 {
    color: var(--wui-color-blue-100);
  }

  .wui-color-blue-90 {
    color: var(--wui-color-blue-90);
  }

  .wui-color-error-125 {
    color: var(--wui-color-error-125);
  }

  .wui-color-success-100 {
    color: var(--wui-color-success-100);
  }

  .wui-color-success-125 {
    color: var(--wui-color-success-125);
  }

  .wui-color-inverse-100 {
    color: var(--wui-color-inverse-100);
  }

  .wui-color-inverse-000 {
    color: var(--wui-color-inverse-000);
  }

  .wui-color-fg-100 {
    color: var(--wui-color-fg-100);
  }

  .wui-color-fg-200 {
    color: var(--wui-color-fg-200);
  }

  .wui-color-fg-300 {
    color: var(--wui-color-fg-300);
  }

  .wui-color-fg-325 {
    color: var(--wui-color-fg-325);
  }

  .wui-color-fg-350 {
    color: var(--wui-color-fg-350);
  }

  .wui-bg-color-inherit {
    background-color: var(--wui-color-inherit);
  }

  .wui-bg-color-blue-100 {
    background-color: var(--wui-color-accent-100);
  }

  .wui-bg-color-error-100 {
    background-color: var(--wui-color-error-100);
  }

  .wui-bg-color-error-125 {
    background-color: var(--wui-color-error-125);
  }

  .wui-bg-color-success-100 {
    background-color: var(--wui-color-success-100);
  }

  .wui-bg-color-success-125 {
    background-color: var(--wui-color-success-100);
  }

  .wui-bg-color-inverse-100 {
    background-color: var(--wui-color-inverse-100);
  }

  .wui-bg-color-inverse-000 {
    background-color: var(--wui-color-inverse-000);
  }

  .wui-bg-color-fg-100 {
    background-color: var(--wui-color-fg-100);
  }

  .wui-bg-color-fg-200 {
    background-color: var(--wui-color-fg-200);
  }

  .wui-bg-color-fg-300 {
    background-color: var(--wui-color-fg-300);
  }

  .wui-color-fg-325 {
    background-color: var(--wui-color-fg-325);
  }

  .wui-color-fg-350 {
    background-color: var(--wui-color-fg-350);
  }
`;var $t={getSpacingStyles(e,t){if(Array.isArray(e))return e[t]?`var(--wui-spacing-${e[t]})`:void 0;if(typeof e=="string")return`var(--wui-spacing-${e})`},getFormattedDate(e){return new Intl.DateTimeFormat("en-US",{month:"short",day:"numeric"}).format(e)},getHostName(e){try{return new URL(e).hostname}catch{return""}},getTruncateString({string:e,charsStart:t,charsEnd:r,truncate:n}){return e.length<=t+r?e:n==="end"?`${e.substring(0,t)}...`:n==="start"?`...${e.substring(e.length-r)}`:`${e.substring(0,Math.floor(t))}...${e.substring(e.length-Math.floor(r))}`},generateAvatarColors(e){let r=e.toLowerCase().replace(/^0x/iu,"").replace(/[^a-f0-9]/gu,"").substring(0,6).padEnd(6,"0"),n=this.hexToRgb(r),o=getComputedStyle(document.documentElement).getPropertyValue("--w3m-border-radius-master"),a=100-3*Number(o?.replace("px","")),c=`${a}% ${a}% at 65% 40%`,u=[];for(let l=0;l<5;l+=1){let d=this.tintColor(n,.15*l);u.push(`rgb(${d[0]}, ${d[1]}, ${d[2]})`)}return`
    --local-color-1: ${u[0]};
    --local-color-2: ${u[1]};
    --local-color-3: ${u[2]};
    --local-color-4: ${u[3]};
    --local-color-5: ${u[4]};
    --local-radial-circle: ${c}
   `},hexToRgb(e){let t=parseInt(e,16),r=t>>16&255,n=t>>8&255,o=t&255;return[r,n,o]},tintColor(e,t){let[r,n,o]=e,s=Math.round(r+(255-r)*t),a=Math.round(n+(255-n)*t),c=Math.round(o+(255-o)*t);return[s,a,c]},isNumber(e){return{number:/^[0-9]+$/u}.number.test(e)},getColorTheme(e){return e||(typeof window<"u"&&window.matchMedia?window.matchMedia("(prefers-color-scheme: dark)")?.matches?"dark":"light":"dark")},splitBalance(e){let t=e.split(".");return t.length===2?[t[0],t[1]]:["0","00"]},roundNumber(e,t,r){return e.toString().length>=t?Number(e).toFixed(r):e},formatNumberToLocalString(e,t=2){return e===void 0?"0.00":typeof e=="number"?e.toLocaleString("en-US",{maximumFractionDigits:t,minimumFractionDigits:t}):parseFloat(e).toLocaleString("en-US",{maximumFractionDigits:t,minimumFractionDigits:t})}};function qr(e,t){let{kind:r,elements:n}=t;return{kind:r,elements:n,finisher(o){customElements.get(e)||customElements.define(e,o)}}}function Kr(e,t){return customElements.get(e)||customElements.define(e,t),t}function Vr(e){return function(r){return typeof r=="function"?Kr(e,r):qr(e,r)}}var pl={ACCOUNT_TABS:[{label:"Tokens"},{label:"NFTs"},{label:"Activity"}],SECURE_SITE_ORIGIN:(typeof process<"u"&&typeof process.env<"u"?process.env.NEXT_PUBLIC_SECURE_SITE_ORIGIN:void 0)||"https://secure.walletconnect.org",VIEW_DIRECTION:{Next:"next",Prev:"prev"},DEFAULT_CONNECT_METHOD_ORDER:["email","social","wallet"],ANIMATION_DURATIONS:{HeaderText:120,ModalHeight:150,ViewTransition:150}};export{W as a,st as b,rr as c,v as d,B as e,le as f,O as g,z as h,f as i,E as j,S as k,ee as l,ht as m,ft as n,$ as o,g as p,w as q,We as r,C as s,Q as t,N as u,we as v,x as w,i as x,m as y,I as z,G as A,Et as B,Fr as C,nt as D,je as E,Mr as F,pl as G,$r as H,Wt as I,jr as J,zc as K,Yc as L,Xc as M,$t as N,Vr as O};

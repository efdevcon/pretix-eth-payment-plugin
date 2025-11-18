import{K as u,L as Z,M as E,N as v,O as d}from"./pretix-eth-5-chunk-V7RLZCVE.js";import{b as m,c as F,d as Y,e as l,g as z,h as X,i as K,j as h}from"./pretix-eth-5-chunk-TH6XAEVV.js";var ut={attribute:!0,type:String,converter:F,reflect:!1,hasChanged:Y},dt=(e=ut,t,i)=>{let{kind:o,metadata:s}=i,r=globalThis.litPropertyMetadata.get(s);if(r===void 0&&globalThis.litPropertyMetadata.set(s,r=new Map),o==="setter"&&((e=Object.create(e)).wrapped=!0),r.set(i.name,e),o==="accessor"){let{name:a}=i;return{set(n){let g=t.get.call(this);t.set.call(this,n),this.requestUpdate(a,g,e)},init(n){return n!==void 0&&this.C(a,void 0,e,n),n}}}if(o==="setter"){let{name:a}=i;return function(n){let g=this[a];t.call(this,n),this.requestUpdate(a,g,e)}}throw Error("Unsupported decorator location: "+o)};function c(e){return(t,i)=>typeof i=="object"?dt(e,t,i):((o,s,r)=>{let a=s.hasOwnProperty(r);return s.constructor.createProperty(r,o),a?Object.getOwnPropertyDescriptor(s,r):void 0})(e,t,i)}function $t(e){return c({...e,state:!0,attribute:!1})}var Q=m`
  :host {
    display: flex;
    width: inherit;
    height: inherit;
  }
`;var f=function(e,t,i,o){var s=arguments.length,r=s<3?t:o===null?o=Object.getOwnPropertyDescriptor(t,i):o,a;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")r=Reflect.decorate(e,t,i,o);else for(var n=e.length-1;n>=0;n--)(a=e[n])&&(r=(s<3?a(r):s>3?a(t,i,r):a(t,i))||r);return s>3&&r&&Object.defineProperty(t,i,r),r},p=class extends h{render(){return this.style.cssText=`
      flex-direction: ${this.flexDirection};
      flex-wrap: ${this.flexWrap};
      flex-basis: ${this.flexBasis};
      flex-grow: ${this.flexGrow};
      flex-shrink: ${this.flexShrink};
      align-items: ${this.alignItems};
      justify-content: ${this.justifyContent};
      column-gap: ${this.columnGap&&`var(--wui-spacing-${this.columnGap})`};
      row-gap: ${this.rowGap&&`var(--wui-spacing-${this.rowGap})`};
      gap: ${this.gap&&`var(--wui-spacing-${this.gap})`};
      padding-top: ${this.padding&&v.getSpacingStyles(this.padding,0)};
      padding-right: ${this.padding&&v.getSpacingStyles(this.padding,1)};
      padding-bottom: ${this.padding&&v.getSpacingStyles(this.padding,2)};
      padding-left: ${this.padding&&v.getSpacingStyles(this.padding,3)};
      margin-top: ${this.margin&&v.getSpacingStyles(this.margin,0)};
      margin-right: ${this.margin&&v.getSpacingStyles(this.margin,1)};
      margin-bottom: ${this.margin&&v.getSpacingStyles(this.margin,2)};
      margin-left: ${this.margin&&v.getSpacingStyles(this.margin,3)};
    `,l`<slot></slot>`}};p.styles=[u,Q];f([c()],p.prototype,"flexDirection",void 0);f([c()],p.prototype,"flexWrap",void 0);f([c()],p.prototype,"flexBasis",void 0);f([c()],p.prototype,"flexGrow",void 0);f([c()],p.prototype,"flexShrink",void 0);f([c()],p.prototype,"alignItems",void 0);f([c()],p.prototype,"justifyContent",void 0);f([c()],p.prototype,"columnGap",void 0);f([c()],p.prototype,"rowGap",void 0);f([c()],p.prototype,"gap",void 0);f([c()],p.prototype,"padding",void 0);f([c()],p.prototype,"margin",void 0);p=f([d("wui-flex")],p);var ae=e=>e??X;var B={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},A=e=>(...t)=>({_$litDirective$:e,values:t}),$=class{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,i,o){this._$Ct=t,this._$AM=i,this._$Ci=o}_$AS(t,i){return this.update(t,i)}update(t,i){return this.render(...i)}};var J=A(class extends ${constructor(e){if(super(e),e.type!==B.ATTRIBUTE||e.name!=="class"||e.strings?.length>2)throw Error("`classMap()` can only be used in the `class` attribute and must be the only part in the attribute.")}render(e){return" "+Object.keys(e).filter(t=>e[t]).join(" ")+" "}update(e,[t]){if(this.st===void 0){this.st=new Set,e.strings!==void 0&&(this.nt=new Set(e.strings.join(" ").split(/\s/).filter(o=>o!=="")));for(let o in t)t[o]&&!this.nt?.has(o)&&this.st.add(o);return this.render(t)}let i=e.element.classList;for(let o of this.st)o in t||(i.remove(o),this.st.delete(o));for(let o in t){let s=!!t[o];s===this.st.has(o)||this.nt?.has(o)||(s?(i.add(o),this.st.add(o)):(i.remove(o),this.st.delete(o)))}return z}});var tt=m`
  :host {
    display: inline-flex !important;
  }

  slot {
    width: 100%;
    display: inline-block;
    font-style: normal;
    font-family: var(--wui-font-family);
    font-feature-settings:
      'tnum' on,
      'lnum' on,
      'case' on;
    line-height: 130%;
    font-weight: var(--wui-font-weight-regular);
    overflow: inherit;
    text-overflow: inherit;
    text-align: var(--local-align);
    color: var(--local-color);
  }

  .wui-line-clamp-1 {
    overflow: hidden;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 1;
  }

  .wui-line-clamp-2 {
    overflow: hidden;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }

  .wui-font-medium-400 {
    font-size: var(--wui-font-size-medium);
    font-weight: var(--wui-font-weight-light);
    letter-spacing: var(--wui-letter-spacing-medium);
  }

  .wui-font-medium-600 {
    font-size: var(--wui-font-size-medium);
    letter-spacing: var(--wui-letter-spacing-medium);
  }

  .wui-font-title-600 {
    font-size: var(--wui-font-size-title);
    letter-spacing: var(--wui-letter-spacing-title);
  }

  .wui-font-title-6-600 {
    font-size: var(--wui-font-size-title-6);
    letter-spacing: var(--wui-letter-spacing-title-6);
  }

  .wui-font-mini-700 {
    font-size: var(--wui-font-size-mini);
    letter-spacing: var(--wui-letter-spacing-mini);
    text-transform: uppercase;
  }

  .wui-font-large-500,
  .wui-font-large-600,
  .wui-font-large-700 {
    font-size: var(--wui-font-size-large);
    letter-spacing: var(--wui-letter-spacing-large);
  }

  .wui-font-2xl-500,
  .wui-font-2xl-600,
  .wui-font-2xl-700 {
    font-size: var(--wui-font-size-2xl);
    letter-spacing: var(--wui-letter-spacing-2xl);
  }

  .wui-font-paragraph-400,
  .wui-font-paragraph-500,
  .wui-font-paragraph-600,
  .wui-font-paragraph-700 {
    font-size: var(--wui-font-size-paragraph);
    letter-spacing: var(--wui-letter-spacing-paragraph);
  }

  .wui-font-small-400,
  .wui-font-small-500,
  .wui-font-small-600 {
    font-size: var(--wui-font-size-small);
    letter-spacing: var(--wui-letter-spacing-small);
  }

  .wui-font-tiny-400,
  .wui-font-tiny-500,
  .wui-font-tiny-600 {
    font-size: var(--wui-font-size-tiny);
    letter-spacing: var(--wui-letter-spacing-tiny);
  }

  .wui-font-micro-700,
  .wui-font-micro-600 {
    font-size: var(--wui-font-size-micro);
    letter-spacing: var(--wui-letter-spacing-micro);
    text-transform: uppercase;
  }

  .wui-font-tiny-400,
  .wui-font-small-400,
  .wui-font-medium-400,
  .wui-font-paragraph-400 {
    font-weight: var(--wui-font-weight-light);
  }

  .wui-font-large-700,
  .wui-font-paragraph-700,
  .wui-font-micro-700,
  .wui-font-mini-700 {
    font-weight: var(--wui-font-weight-bold);
  }

  .wui-font-medium-600,
  .wui-font-medium-title-600,
  .wui-font-title-6-600,
  .wui-font-large-600,
  .wui-font-paragraph-600,
  .wui-font-small-600,
  .wui-font-tiny-600,
  .wui-font-micro-600 {
    font-weight: var(--wui-font-weight-medium);
  }

  :host([disabled]) {
    opacity: 0.4;
  }
`;var P=function(e,t,i,o){var s=arguments.length,r=s<3?t:o===null?o=Object.getOwnPropertyDescriptor(t,i):o,a;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")r=Reflect.decorate(e,t,i,o);else for(var n=e.length-1;n>=0;n--)(a=e[n])&&(r=(s<3?a(r):s>3?a(t,i,r):a(t,i))||r);return s>3&&r&&Object.defineProperty(t,i,r),r},x=class extends h{constructor(){super(...arguments),this.variant="paragraph-500",this.color="fg-300",this.align="left",this.lineClamp=void 0}render(){let t={[`wui-font-${this.variant}`]:!0,[`wui-color-${this.color}`]:!0,[`wui-line-clamp-${this.lineClamp}`]:!!this.lineClamp};return this.style.cssText=`
      --local-align: ${this.align};
      --local-color: var(--wui-color-${this.color});
    `,l`<slot class=${J(t)}></slot>`}};x.styles=[u,tt];P([c()],x.prototype,"variant",void 0);P([c()],x.prototype,"color",void 0);P([c()],x.prototype,"align",void 0);P([c()],x.prototype,"lineClamp",void 0);x=P([d("wui-text")],x);var{I:ke}=K,et=e=>e===null||typeof e!="object"&&typeof e!="function";var it=e=>e.strings===void 0;var R=(e,t)=>{let i=e._$AN;if(i===void 0)return!1;for(let o of i)o._$AO?.(t,!1),R(o,t);return!0},D=e=>{let t,i;do{if((t=e._$AM)===void 0)break;i=t._$AN,i.delete(e),e=t}while(i?.size===0)},ot=e=>{for(let t;t=e._$AM;e=t){let i=t._$AN;if(i===void 0)t._$AN=i=new Set;else if(i.has(e))break;i.add(e),wt(t)}};function ft(e){this._$AN!==void 0?(D(this),this._$AM=e,ot(this)):this._$AM=e}function gt(e,t=!1,i=0){let o=this._$AH,s=this._$AN;if(s!==void 0&&s.size!==0)if(t)if(Array.isArray(o))for(let r=i;r<o.length;r++)R(o[r],!1),D(o[r]);else o!=null&&(R(o,!1),D(o));else R(this,e)}var wt=e=>{e.type==B.CHILD&&(e._$AP??=gt,e._$AQ??=ft)},L=class extends ${constructor(){super(...arguments),this._$AN=void 0}_$AT(t,i,o){super._$AT(t,i,o),ot(this),this.isConnected=t._$AU}_$AO(t,i=!0){t!==this.isConnected&&(this.isConnected=t,t?this.reconnected?.():this.disconnected?.()),i&&(R(this,t),D(this))}setValue(t){if(it(this._$Ct))this._$Ct._$AI(t,this);else{let i=[...this._$Ct._$AH];i[this._$Ci]=t,this._$Ct._$AI(i,this,0)}}disconnected(){}reconnected(){}};var I=class{constructor(t){this.G=t}disconnect(){this.G=void 0}reconnect(t){this.G=t}deref(){return this.G}},M=class{constructor(){this.Y=void 0,this.Z=void 0}get(){return this.Y}pause(){this.Y??=new Promise(t=>this.Z=t)}resume(){this.Z?.(),this.Y=this.Z=void 0}};var rt=e=>!et(e)&&typeof e.then=="function",st=1073741823,G=class extends L{constructor(){super(...arguments),this._$Cwt=st,this._$Cbt=[],this._$CK=new I(this),this._$CX=new M}render(...t){return t.find(i=>!rt(i))??z}update(t,i){let o=this._$Cbt,s=o.length;this._$Cbt=i;let r=this._$CK,a=this._$CX;this.isConnected||this.disconnected();for(let n=0;n<i.length&&!(n>this._$Cwt);n++){let g=i[n];if(!rt(g))return this._$Cwt=n,g;n<s&&g===o[n]||(this._$Cwt=st,s=0,Promise.resolve(g).then(async _=>{for(;a.get();)await a.get();let C=r.deref();if(C!==void 0){let q=C._$Cbt.indexOf(g);q>-1&&q<C._$Cwt&&(C._$Cwt=q,C.setValue(_))}}))}return z}disconnected(){this._$CK.disconnect(),this._$CX.pause()}reconnected(){this._$CK.reconnect(this),this._$CX.resume()}},at=A(G);var N=class{constructor(){this.cache=new Map}set(t,i){this.cache.set(t,i)}get(t){return this.cache.get(t)}has(t){return this.cache.has(t)}delete(t){this.cache.delete(t)}clear(){this.cache.clear()}},H=new N;var nt=m`
  :host {
    display: flex;
    aspect-ratio: var(--local-aspect-ratio);
    color: var(--local-color);
    width: var(--local-width);
  }

  svg {
    width: inherit;
    height: inherit;
    object-fit: contain;
    object-position: center;
  }

  .fallback {
    width: var(--local-width);
    height: var(--local-height);
  }
`;var k=function(e,t,i,o){var s=arguments.length,r=s<3?t:o===null?o=Object.getOwnPropertyDescriptor(t,i):o,a;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")r=Reflect.decorate(e,t,i,o);else for(var n=e.length-1;n>=0;n--)(a=e[n])&&(r=(s<3?a(r):s>3?a(t,i,r):a(t,i))||r);return s>3&&r&&Object.defineProperty(t,i,r),r},ct={add:async()=>(await import("./pretix-eth-5-add-RE33J2A6.js")).addSvg,allWallets:async()=>(await import("./pretix-eth-5-all-wallets-4AX7CEY2.js")).allWalletsSvg,arrowBottomCircle:async()=>(await import("./pretix-eth-5-arrow-bottom-circle-DGFIB3KO.js")).arrowBottomCircleSvg,appStore:async()=>(await import("./pretix-eth-5-app-store-L5JARIFN.js")).appStoreSvg,apple:async()=>(await import("./pretix-eth-5-apple-MOFDI6EG.js")).appleSvg,arrowBottom:async()=>(await import("./pretix-eth-5-arrow-bottom-BT3GKP23.js")).arrowBottomSvg,arrowLeft:async()=>(await import("./pretix-eth-5-arrow-left-3D24VFEC.js")).arrowLeftSvg,arrowRight:async()=>(await import("./pretix-eth-5-arrow-right-NZKSNAYS.js")).arrowRightSvg,arrowTop:async()=>(await import("./pretix-eth-5-arrow-top-JKX6GFB7.js")).arrowTopSvg,bank:async()=>(await import("./pretix-eth-5-bank-AQA2OYP6.js")).bankSvg,browser:async()=>(await import("./pretix-eth-5-browser-5Q6OG5OV.js")).browserSvg,card:async()=>(await import("./pretix-eth-5-card-GVFV4FKY.js")).cardSvg,checkmark:async()=>(await import("./pretix-eth-5-checkmark-XCQGHW7Y.js")).checkmarkSvg,checkmarkBold:async()=>(await import("./pretix-eth-5-checkmark-bold-IBNEKUHL.js")).checkmarkBoldSvg,chevronBottom:async()=>(await import("./pretix-eth-5-chevron-bottom-F3U32FKW.js")).chevronBottomSvg,chevronLeft:async()=>(await import("./pretix-eth-5-chevron-left-LZNNGFTX.js")).chevronLeftSvg,chevronRight:async()=>(await import("./pretix-eth-5-chevron-right-Q42DCHFD.js")).chevronRightSvg,chevronTop:async()=>(await import("./pretix-eth-5-chevron-top-H4E5BPKY.js")).chevronTopSvg,chromeStore:async()=>(await import("./pretix-eth-5-chrome-store-4HIVBO64.js")).chromeStoreSvg,clock:async()=>(await import("./pretix-eth-5-clock-APOGHBLD.js")).clockSvg,close:async()=>(await import("./pretix-eth-5-close-HV3DK57C.js")).closeSvg,compass:async()=>(await import("./pretix-eth-5-compass-7PZ43UNH.js")).compassSvg,coinPlaceholder:async()=>(await import("./pretix-eth-5-coinPlaceholder-TBGBMORW.js")).coinPlaceholderSvg,copy:async()=>(await import("./pretix-eth-5-copy-2H2SPBNR.js")).copySvg,cursor:async()=>(await import("./pretix-eth-5-cursor-KCZVLLAT.js")).cursorSvg,cursorTransparent:async()=>(await import("./pretix-eth-5-cursor-transparent-GGBZQG2W.js")).cursorTransparentSvg,desktop:async()=>(await import("./pretix-eth-5-desktop-H6BZAQKZ.js")).desktopSvg,disconnect:async()=>(await import("./pretix-eth-5-disconnect-R7RNY6IZ.js")).disconnectSvg,discord:async()=>(await import("./pretix-eth-5-discord-2NK4XRW4.js")).discordSvg,etherscan:async()=>(await import("./pretix-eth-5-etherscan-QQJ2THD6.js")).etherscanSvg,extension:async()=>(await import("./pretix-eth-5-extension-OXBMAIG7.js")).extensionSvg,externalLink:async()=>(await import("./pretix-eth-5-external-link-Q2THBY3X.js")).externalLinkSvg,facebook:async()=>(await import("./pretix-eth-5-facebook-3FCCUH6C.js")).facebookSvg,farcaster:async()=>(await import("./pretix-eth-5-farcaster-DXM27GNY.js")).farcasterSvg,filters:async()=>(await import("./pretix-eth-5-filters-ZJATEX7P.js")).filtersSvg,github:async()=>(await import("./pretix-eth-5-github-2KMNJ55L.js")).githubSvg,google:async()=>(await import("./pretix-eth-5-google-Y2Y4IIMK.js")).googleSvg,helpCircle:async()=>(await import("./pretix-eth-5-help-circle-SII2DREK.js")).helpCircleSvg,image:async()=>(await import("./pretix-eth-5-image-MO2NFFNR.js")).imageSvg,id:async()=>(await import("./pretix-eth-5-id-UDTUG4QG.js")).idSvg,infoCircle:async()=>(await import("./pretix-eth-5-info-circle-YBTMNY42.js")).infoCircleSvg,lightbulb:async()=>(await import("./pretix-eth-5-lightbulb-5MUPYPCK.js")).lightbulbSvg,mail:async()=>(await import("./pretix-eth-5-mail-BNSJA4YK.js")).mailSvg,mobile:async()=>(await import("./pretix-eth-5-mobile-4ZZJUFJP.js")).mobileSvg,more:async()=>(await import("./pretix-eth-5-more-Z2AID2CF.js")).moreSvg,networkPlaceholder:async()=>(await import("./pretix-eth-5-network-placeholder-T47NSNQ3.js")).networkPlaceholderSvg,nftPlaceholder:async()=>(await import("./pretix-eth-5-nftPlaceholder-HSC35GON.js")).nftPlaceholderSvg,off:async()=>(await import("./pretix-eth-5-off-ZRTJWTWQ.js")).offSvg,playStore:async()=>(await import("./pretix-eth-5-play-store-UA42BXU5.js")).playStoreSvg,plus:async()=>(await import("./pretix-eth-5-plus-TSJ6PERR.js")).plusSvg,qrCode:async()=>(await import("./pretix-eth-5-qr-code-4ONRE45H.js")).qrCodeIcon,recycleHorizontal:async()=>(await import("./pretix-eth-5-recycle-horizontal-U4DH7SDX.js")).recycleHorizontalSvg,refresh:async()=>(await import("./pretix-eth-5-refresh-H3FTT7WK.js")).refreshSvg,search:async()=>(await import("./pretix-eth-5-search-UROANNMT.js")).searchSvg,send:async()=>(await import("./pretix-eth-5-send-CCQJOHCV.js")).sendSvg,swapHorizontal:async()=>(await import("./pretix-eth-5-swapHorizontal-C6CRVF6Y.js")).swapHorizontalSvg,swapHorizontalMedium:async()=>(await import("./pretix-eth-5-swapHorizontalMedium-F6N4HIPV.js")).swapHorizontalMediumSvg,swapHorizontalBold:async()=>(await import("./pretix-eth-5-swapHorizontalBold-N3ZHTUHC.js")).swapHorizontalBoldSvg,swapHorizontalRoundedBold:async()=>(await import("./pretix-eth-5-swapHorizontalRoundedBold-VMWAPNBO.js")).swapHorizontalRoundedBoldSvg,swapVertical:async()=>(await import("./pretix-eth-5-swapVertical-CUQ4EPHQ.js")).swapVerticalSvg,telegram:async()=>(await import("./pretix-eth-5-telegram-6USXJ37H.js")).telegramSvg,threeDots:async()=>(await import("./pretix-eth-5-three-dots-BIXZGR2N.js")).threeDotsSvg,twitch:async()=>(await import("./pretix-eth-5-twitch-RNVO5SQE.js")).twitchSvg,twitter:async()=>(await import("./pretix-eth-5-x-UXGGEUNA.js")).xSvg,twitterIcon:async()=>(await import("./pretix-eth-5-twitterIcon-NV2ZW5NW.js")).twitterIconSvg,verify:async()=>(await import("./pretix-eth-5-verify-7DMHUN35.js")).verifySvg,verifyFilled:async()=>(await import("./pretix-eth-5-verify-filled-7QR52FNX.js")).verifyFilledSvg,wallet:async()=>(await import("./pretix-eth-5-wallet-VR2QV73B.js")).walletSvg,walletConnect:async()=>(await import("./pretix-eth-5-walletconnect-NHLX7UON.js")).walletConnectSvg,walletConnectLightBrown:async()=>(await import("./pretix-eth-5-walletconnect-NHLX7UON.js")).walletConnectLightBrownSvg,walletConnectBrown:async()=>(await import("./pretix-eth-5-walletconnect-NHLX7UON.js")).walletConnectBrownSvg,walletPlaceholder:async()=>(await import("./pretix-eth-5-wallet-placeholder-MOQMI6E4.js")).walletPlaceholderSvg,warningCircle:async()=>(await import("./pretix-eth-5-warning-circle-UBCK64TT.js")).warningCircleSvg,x:async()=>(await import("./pretix-eth-5-x-UXGGEUNA.js")).xSvg,info:async()=>(await import("./pretix-eth-5-info-XP2IGXAP.js")).infoSvg,exclamationTriangle:async()=>(await import("./pretix-eth-5-exclamation-triangle-JUSJKJNH.js")).exclamationTriangleSvg,reown:async()=>(await import("./pretix-eth-5-reown-logo-LAR6FZ5E.js")).reownSvg};async function vt(e){if(H.has(e))return H.get(e);let i=(ct[e]??ct.copy)();return H.set(e,i),i}var b=class extends h{constructor(){super(...arguments),this.size="md",this.name="copy",this.color="fg-300",this.aspectRatio="1 / 1"}render(){return this.style.cssText=`
      --local-color: ${`var(--wui-color-${this.color});`}
      --local-width: ${`var(--wui-icon-size-${this.size});`}
      --local-aspect-ratio: ${this.aspectRatio}
    `,l`${at(vt(this.name),l`<div class="fallback"></div>`)}`}};b.styles=[u,E,nt];k([c()],b.prototype,"size",void 0);k([c()],b.prototype,"name",void 0);k([c()],b.prototype,"color",void 0);k([c()],b.prototype,"aspectRatio",void 0);b=k([d("wui-icon")],b);var lt=m`
  :host {
    display: inline-flex;
    justify-content: center;
    align-items: center;
    position: relative;
    overflow: hidden;
    background-color: var(--wui-color-gray-glass-020);
    border-radius: var(--local-border-radius);
    border: var(--local-border);
    box-sizing: content-box;
    width: var(--local-size);
    height: var(--local-size);
    min-height: var(--local-size);
    min-width: var(--local-size);
  }

  @supports (background: color-mix(in srgb, white 50%, black)) {
    :host {
      background-color: color-mix(in srgb, var(--local-bg-value) var(--local-bg-mix), transparent);
    }
  }
`;var y=function(e,t,i,o){var s=arguments.length,r=s<3?t:o===null?o=Object.getOwnPropertyDescriptor(t,i):o,a;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")r=Reflect.decorate(e,t,i,o);else for(var n=e.length-1;n>=0;n--)(a=e[n])&&(r=(s<3?a(r):s>3?a(t,i,r):a(t,i))||r);return s>3&&r&&Object.defineProperty(t,i,r),r},w=class extends h{constructor(){super(...arguments),this.size="md",this.backgroundColor="accent-100",this.iconColor="accent-100",this.background="transparent",this.border=!1,this.borderColor="wui-color-bg-125",this.icon="copy"}render(){let t=this.iconSize||this.size,i=this.size==="lg",o=this.size==="xl",s=i?"12%":"16%",r=i?"xxs":o?"s":"3xl",a=this.background==="gray",n=this.background==="opaque",g=this.backgroundColor==="accent-100"&&n||this.backgroundColor==="success-100"&&n||this.backgroundColor==="error-100"&&n||this.backgroundColor==="inverse-100"&&n,_=`var(--wui-color-${this.backgroundColor})`;return g?_=`var(--wui-icon-box-bg-${this.backgroundColor})`:a&&(_=`var(--wui-color-gray-${this.backgroundColor})`),this.style.cssText=`
       --local-bg-value: ${_};
       --local-bg-mix: ${g||a?"100%":s};
       --local-border-radius: var(--wui-border-radius-${r});
       --local-size: var(--wui-icon-box-size-${this.size});
       --local-border: ${this.borderColor==="wui-color-bg-125"?"2px":"1px"} solid ${this.border?`var(--${this.borderColor})`:"transparent"}
   `,l` <wui-icon color=${this.iconColor} size=${t} name=${this.icon}></wui-icon> `}};w.styles=[u,Z,lt];y([c()],w.prototype,"size",void 0);y([c()],w.prototype,"backgroundColor",void 0);y([c()],w.prototype,"iconColor",void 0);y([c()],w.prototype,"iconSize",void 0);y([c()],w.prototype,"background",void 0);y([c({type:Boolean})],w.prototype,"border",void 0);y([c()],w.prototype,"borderColor",void 0);y([c()],w.prototype,"icon",void 0);w=y([d("wui-icon-box")],w);var pt=m`
  :host {
    display: block;
    width: var(--local-width);
    height: var(--local-height);
  }

  img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center center;
    border-radius: inherit;
  }
`;var W=function(e,t,i,o){var s=arguments.length,r=s<3?t:o===null?o=Object.getOwnPropertyDescriptor(t,i):o,a;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")r=Reflect.decorate(e,t,i,o);else for(var n=e.length-1;n>=0;n--)(a=e[n])&&(r=(s<3?a(r):s>3?a(t,i,r):a(t,i))||r);return s>3&&r&&Object.defineProperty(t,i,r),r},S=class extends h{constructor(){super(...arguments),this.src="./path/to/image.jpg",this.alt="Image",this.size=void 0}render(){return this.style.cssText=`
      --local-width: ${this.size?`var(--wui-icon-size-${this.size});`:"100%"};
      --local-height: ${this.size?`var(--wui-icon-size-${this.size});`:"100%"};
      `,l`<img src=${this.src} alt=${this.alt} @error=${this.handleImageError} />`}handleImageError(){this.dispatchEvent(new CustomEvent("onLoadError",{bubbles:!0,composed:!0}))}};S.styles=[u,E,pt];W([c()],S.prototype,"src",void 0);W([c()],S.prototype,"alt",void 0);W([c()],S.prototype,"size",void 0);S=W([d("wui-image")],S);var mt=m`
  :host {
    display: flex;
    justify-content: center;
    align-items: center;
    height: var(--wui-spacing-m);
    padding: 0 var(--wui-spacing-3xs) !important;
    border-radius: var(--wui-border-radius-5xs);
    transition:
      border-radius var(--wui-duration-lg) var(--wui-ease-out-power-1),
      background-color var(--wui-duration-lg) var(--wui-ease-out-power-1);
    will-change: border-radius, background-color;
  }

  :host > wui-text {
    transform: translateY(5%);
  }

  :host([data-variant='main']) {
    background-color: var(--wui-color-accent-glass-015);
    color: var(--wui-color-accent-100);
  }

  :host([data-variant='shade']) {
    background-color: var(--wui-color-gray-glass-010);
    color: var(--wui-color-fg-200);
  }

  :host([data-variant='success']) {
    background-color: var(--wui-icon-box-bg-success-100);
    color: var(--wui-color-success-100);
  }

  :host([data-variant='error']) {
    background-color: var(--wui-icon-box-bg-error-100);
    color: var(--wui-color-error-100);
  }

  :host([data-size='lg']) {
    padding: 11px 5px !important;
  }

  :host([data-size='lg']) > wui-text {
    transform: translateY(2%);
  }
`;var U=function(e,t,i,o){var s=arguments.length,r=s<3?t:o===null?o=Object.getOwnPropertyDescriptor(t,i):o,a;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")r=Reflect.decorate(e,t,i,o);else for(var n=e.length-1;n>=0;n--)(a=e[n])&&(r=(s<3?a(r):s>3?a(t,i,r):a(t,i))||r);return s>3&&r&&Object.defineProperty(t,i,r),r},T=class extends h{constructor(){super(...arguments),this.variant="main",this.size="lg"}render(){this.dataset.variant=this.variant,this.dataset.size=this.size;let t=this.size==="md"?"mini-700":"micro-700";return l`
      <wui-text data-variant=${this.variant} variant=${t} color="inherit">
        <slot></slot>
      </wui-text>
    `}};T.styles=[u,mt];U([c()],T.prototype,"variant",void 0);U([c()],T.prototype,"size",void 0);T=U([d("wui-tag")],T);var ht=m`
  :host {
    display: flex;
  }

  :host([data-size='sm']) > svg {
    width: 12px;
    height: 12px;
  }

  :host([data-size='md']) > svg {
    width: 16px;
    height: 16px;
  }

  :host([data-size='lg']) > svg {
    width: 24px;
    height: 24px;
  }

  :host([data-size='xl']) > svg {
    width: 32px;
    height: 32px;
  }

  svg {
    animation: rotate 2s linear infinite;
  }

  circle {
    fill: none;
    stroke: var(--local-color);
    stroke-width: 4px;
    stroke-dasharray: 1, 124;
    stroke-dashoffset: 0;
    stroke-linecap: round;
    animation: dash 1.5s ease-in-out infinite;
  }

  :host([data-size='md']) > svg > circle {
    stroke-width: 6px;
  }

  :host([data-size='sm']) > svg > circle {
    stroke-width: 8px;
  }

  @keyframes rotate {
    100% {
      transform: rotate(360deg);
    }
  }

  @keyframes dash {
    0% {
      stroke-dasharray: 1, 124;
      stroke-dashoffset: 0;
    }

    50% {
      stroke-dasharray: 90, 124;
      stroke-dashoffset: -35;
    }

    100% {
      stroke-dashoffset: -125;
    }
  }
`;var V=function(e,t,i,o){var s=arguments.length,r=s<3?t:o===null?o=Object.getOwnPropertyDescriptor(t,i):o,a;if(typeof Reflect=="object"&&typeof Reflect.decorate=="function")r=Reflect.decorate(e,t,i,o);else for(var n=e.length-1;n>=0;n--)(a=e[n])&&(r=(s<3?a(r):s>3?a(t,i,r):a(t,i))||r);return s>3&&r&&Object.defineProperty(t,i,r),r},j=class extends h{constructor(){super(...arguments),this.color="accent-100",this.size="lg"}render(){return this.style.cssText=`--local-color: ${this.color==="inherit"?"inherit":`var(--wui-color-${this.color})`}`,this.dataset.size=this.size,l`<svg viewBox="25 25 50 50">
      <circle r="20" cy="50" cx="50"></circle>
    </svg>`}};j.styles=[u,ht];V([c()],j.prototype,"color",void 0);V([c()],j.prototype,"size",void 0);j=V([d("wui-loading-spinner")],j);export{c as a,$t as b,ae as c,A as d,L as e,J as f};
/*! Bundled license information:

@lit/reactive-element/decorators/property.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/decorators/state.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/decorators/custom-element.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/decorators/event-options.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/decorators/base.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/decorators/query.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/decorators/query-all.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/decorators/query-async.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/decorators/query-assigned-elements.js:
  (**
   * @license
   * Copyright 2021 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/decorators/query-assigned-nodes.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/directives/if-defined.js:
  (**
   * @license
   * Copyright 2018 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/directive.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/directives/class-map.js:
  (**
   * @license
   * Copyright 2018 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/directive-helpers.js:
  (**
   * @license
   * Copyright 2020 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/async-directive.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/directives/private-async-helpers.js:
  (**
   * @license
   * Copyright 2021 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/directives/until.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)
*/

import { IAbstractConnectorOptions } from "../../helpers";
export interface ICoinbaseWalletSdkConnectorOptions extends IAbstractConnectorOptions {
    infuraId?: string;
    rpc?: {
        [chainId: number]: string;
    };
    chainId?: number;
    appName?: string;
    appLogoUrl?: string;
    darkMode?: boolean;
}
declare const ConnectToCoinbaseWalletSdk: (CoinbaseWalletSdk: any, opts: ICoinbaseWalletSdkConnectorOptions) => Promise<unknown>;
/**
 * @deprecated WalletLink is deprecated in favor of CoinbaseWalletSdk
 */
export declare const walletlink: (CoinbaseWalletSdk: any, opts: ICoinbaseWalletSdkConnectorOptions) => Promise<unknown>;
export default ConnectToCoinbaseWalletSdk;
//# sourceMappingURL=coinbasewallet.d.ts.map
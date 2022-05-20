import { IAbstractConnectorOptions } from "../../helpers";
export interface IVenlyConnectorOptions extends IAbstractConnectorOptions {
    clientId: string;
    secretType?: string;
    environment?: string;
}
declare const ConnectToVenly: (Venly: any, opts: IVenlyConnectorOptions) => Promise<unknown>;
export default ConnectToVenly;
//# sourceMappingURL=venly.d.ts.map
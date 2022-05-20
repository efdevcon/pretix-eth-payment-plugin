import { IAbstractConnectorOptions } from "../../helpers";
export interface ISequenceConnectorOptions extends IAbstractConnectorOptions {
    appName: string;
    defaultNetwork?: string;
}
declare const ConnectToSequence: (sequence: any, opts?: ISequenceConnectorOptions | undefined) => Promise<any>;
export default ConnectToSequence;
//# sourceMappingURL=sequence.d.ts.map
import { IBuilderStateProps } from '@app/store/form-builder/types';

import ICommandListener from '../interfaces/ICommandListener';

export default class EnterCommandListener extends ICommandListener {
    private readonly state: IBuilderStateProps | null = null;

    constructor(state: IBuilderStateProps) {
        super();
        this.state = state;
    }

    execute(callback?: Function | undefined): void {
        if (this.state) {
            console.log(this.state);
            // TODO: add a new block here
        }

        if (typeof callback !== 'undefined') callback();
    }
}

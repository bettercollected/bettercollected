import { IBuilderStateProps } from '@app/store/form-builder/types';

import ICommandListener from '../interfaces/ICommandListener';

export default class EnterCommandListener extends ICommandListener {
    private readonly state: IBuilderStateProps | null = null;

    constructor(state: IBuilderStateProps) {
        super();
        this.state = state;
    }

    execute(event: React.KeyboardEvent, callback?: Function | undefined): void {
        event.preventDefault();
        if (this.state) {
            // TODO: add a new block here
        }

        if (typeof callback !== 'undefined') callback();
    }
}
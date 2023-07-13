import { IBuilderStateProps } from '@app/store/form-builder/types';

import ICommandListener from '../interfaces/ICommandListener';

export default class ArrowCommandListener extends ICommandListener {
    private readonly state: IBuilderStateProps | null = null;
    private readonly key: string;

    constructor(state: IBuilderStateProps, key: string) {
        super();
        this.state = state;
        this.key = key;
    }

    execute(callback?: Function | undefined): void {
        if (this.state && this.key === 'ArrowDown') {
            console.log(this.state, 'Arrow down invoked');
            // TODO: focus to another block
        }
        if (this.state && this.key === 'ArrowUp') {
            console.log(this.state, 'Arrow up invoked');
            // TODO: focus to another block
        }

        if (typeof callback !== 'undefined') callback();
    }
}

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

    execute(event: React.KeyboardEvent, callback?: Function | undefined): void {
        if (this.state && this.key === 'ArrowDown') {
            // TODO: focus to another block
        }
        if (this.state && this.key === 'ArrowUp') {
            // TODO: focus to another block
        }

        if (typeof callback !== 'undefined') callback();
    }
}

import ICommandListener from '../interfaces/ICommandListener';

export default class SpotlightCommandListener extends ICommandListener {
    execute(event: React.KeyboardEvent, callback?: Function | undefined): void {
        if (typeof callback !== 'undefined') callback();
    }
}

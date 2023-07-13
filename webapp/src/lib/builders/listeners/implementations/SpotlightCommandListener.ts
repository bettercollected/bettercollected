import ICommandListener from '../interfaces/ICommandListener';

export default class SpotlightCommandListener extends ICommandListener {
    execute(callback?: Function | undefined): void {
        if (typeof callback !== 'undefined') callback();
    }
}

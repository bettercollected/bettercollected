export default abstract class ICommandListener {
    abstract execute(event: React.KeyboardEvent, callback?: Function): void;

    undo?(callback?: Function): void;

    redo?(callback?: Function): void;
}

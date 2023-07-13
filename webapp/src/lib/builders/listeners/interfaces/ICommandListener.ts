export default abstract class ICommandListener {
    abstract execute(callback?: Function): void;
    undo?(callback?: Function): void;
    redo?(callback?: Function): void;
}

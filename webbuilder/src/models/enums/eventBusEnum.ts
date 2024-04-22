enum FormBuilderEventBusEventType {
    StopPropagation = 'stop_propagation',
    Save = 'form_save',
    Preview = 'preview',
    OpenTagSelector = 'open_tag_selector',
    OpenFieldSelector = 'open_field_selector'
}

enum MarkdownEventBusEventType {
    FirstLine = 'first_line',
    LastLine = 'last_line'
}

enum HistoryEventBusEventType {
    Undo = 'undo',
    Redo = 'redo',
    UndoRedoStart = 'undo_redo_start',
    UndoRedoCompleted = 'undo_redo_completed'
}

const EventBusEventType = {
    FormBuilder: FormBuilderEventBusEventType,
    MarkdownEditor: MarkdownEventBusEventType,
    History: HistoryEventBusEventType
};

export default EventBusEventType;

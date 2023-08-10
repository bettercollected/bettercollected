enum FormBuilderEventBusEventType {
    StopPropagation = 'stop_propagation',
    Save = 'form_save',
    Publish = 'publish',
    OpenTagSelector = 'open_tag_selector'
}

enum MarkdownEventBusEventType {
    FirstLine = 'first_line',
    LastLine = 'last_line'
}

const EventBusEventType = {
    FormBuilder: FormBuilderEventBusEventType,
    MarkdownEditor: MarkdownEventBusEventType
};

export default EventBusEventType;

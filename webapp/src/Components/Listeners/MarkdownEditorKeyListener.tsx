import React from 'react';

export default function MarkdownEditorKeyListener({ children }: React.PropsWithChildren) {
    // const builderState = useAppSelector(selectBuilderState);
    // const { activeFieldId, activeFieldIndex } = builderState;
    // const [editorDetails, setEditorDetails] = useState({ isFirstLine: false, isLastLine: false });

    // const onKeyDownCallback = useCallback(
    //     (event: KeyboardEvent) => {
    //         const formField: IFormFieldState | undefined = builderState.fields[activeFieldId];
    //         if (!formField || formField.type !== FormBuilderTagNames.LAYOUT_MARKDOWN) return;
    //         // if (editorDetails.isFirstLine || editorDetails.isLastLine) return;

    //     },
    //     [activeFieldId, builderState.fields]
    // );

    // const handleFirstLine = (val: boolean) => {
    //     setEditorDetails({ ...editorDetails, isFirstLine: val });
    // };
    // const handleLastLine = (val: boolean) => {
    //     setEditorDetails({ ...editorDetails, isLastLine: val });
    // };

    // useEffect(() => {
    //     const throttledKeyDownCallback = onKeyDownCallback;

    //     document.addEventListener('keydown', throttledKeyDownCallback);

    //     return () => {
    //         document.removeEventListener('keydown', throttledKeyDownCallback);

    //     };
    // }, [builderState, onKeyDownCallback]);

    return <div>{children}</div>;
}

import React, { ChangeEvent, useEffect, useRef, useState } from 'react';

import TextArea from '@Components/Common/Input/TextArea';
import MarkdownText from '@Components/Common/Markdown';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import cn from 'classnames';
import { useDispatch } from 'react-redux';

import useFormBuilderState from '@app/containers/form-builder/context';
import useUserTypingDetection from '@app/lib/hooks/use-user-typing-detection';
import useUndoRedo from '@app/lib/use-undo-redo';
import { KeyType } from '@app/models/enums/formBuilder';
import { setActiveField, setUpdateField } from '@app/store/form-builder/actions';
import { selectActiveFieldId } from '@app/store/form-builder/selectors';
import { useAppSelector } from '@app/store/hooks';

interface MarkdownEditorProps {
    field: any;
    id: string;
}

const MarkdownEditor = ({ id, field }: MarkdownEditorProps) => {
    const [preview, setPreview] = useState(false);
    const inputRef = useRef<HTMLTextAreaElement | null>(null);
    const { setBackspaceCount } = useFormBuilderState();
    const { handleUserTypingEnd } = useUserTypingDetection();
    const { isUndoRedoInProgress } = useUndoRedo();

    const dispatch = useDispatch();

    const activeFieldIndex = useAppSelector(selectActiveFieldId);

    const getEditingLinePosition = () => {
        const textArea = inputRef.current;
        let lineIndex = 0;
        let currentCharCount = 0;

        if (!textArea) return lineIndex;

        const lines = textArea.value.split('\n');
        const cursorPosition = textArea.selectionStart || 0;

        for (let i = 0; i < lines.length; i++) {
            if (cursorPosition <= currentCharCount + lines[i].length) {
                lineIndex = i;
                break;
            }
            currentCharCount += lines[i].length + 1; // Adding 1 for newline character
        }

        return lineIndex;
    };

    const onKeyDownCallback = (event: KeyboardEvent) => {
        if (field?.position !== activeFieldIndex) return;
        const currentEditingLine = getEditingLinePosition();
        const lines = inputRef.current?.value.split('\n');
        const lastLineIndex = (lines?.length ?? 1) - 1;
        if (event.key === KeyType.ArrowUp && currentEditingLine !== 0) {
            event.stopPropagation();
            event.stopImmediatePropagation();
        } else if (event.key === KeyType.ArrowDown && currentEditingLine !== lastLineIndex) {
            event.stopPropagation();
            event.stopImmediatePropagation();
        }
    };
    const onChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
        if (isUndoRedoInProgress) return;
        setBackspaceCount(0);
        dispatch(
            setUpdateField({
                ...field,
                value: event.target.value
            })
        );
        handleUserTypingEnd();
    };
    const handlePreview = () => {
        setPreview(!preview);
    };
    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            onKeyDownCallback(event);
        };

        document.addEventListener('keydown', handleKeyDown);

        return () => {
            document.removeEventListener('keydown', handleKeyDown);
        };
    });

    useEffect(() => {
        if (field?.position !== activeFieldIndex) return;
        inputRef.current?.focus();
    }, [activeFieldIndex, field?.position]);

    return (
        <div className={cn('w-full relative ', preview && 'border rounded-sm p-3 min-h-14')}>
            <div className="cursor-pointer  absolute right-3 top-1 text-gray-500" onClick={handlePreview}>
                {preview ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
            </div>

            {preview ? (
                <MarkdownText text={field.value ?? ''} />
            ) : (
                <TextArea
                    id={id}
                    ref={inputRef}
                    value={field?.value}
                    onChange={onChange}
                    onFocus={() => {
                        dispatch(setActiveField({ id: field?.id, position: field?.position }));
                    }}
                />
            )}
        </div>
    );
};

export default MarkdownEditor;

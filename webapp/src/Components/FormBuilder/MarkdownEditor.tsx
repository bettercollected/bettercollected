import React, { ChangeEvent, useEffect, useRef, useState } from 'react';

import TextArea from '@Components/Common/Input/TextArea';
import { Key, Visibility, VisibilityOff } from '@mui/icons-material';
import cn from 'classnames';
import { useDispatch } from 'react-redux';

import useFormBuilderState from '@app/containers/form-builder/context';
import eventBus from '@app/lib/event-bus';
import EventBusEventType from '@app/models/enums/eventBusEnum';
import { KeyType } from '@app/models/enums/formBuilder';
import { setActiveField, setUpdateField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { useAppSelector } from '@app/store/hooks';

import MarkdownText from '../UI/MarkdownText';

interface MarkdownEditorProps {
    field: any;
    id: string;
}

const MarkdownEditor = ({ id, field }: MarkdownEditorProps) => {
    const [preview, setPreview] = useState(false);
    const inputRef = useRef<HTMLTextAreaElement | null>(null);

    const dispatch = useDispatch();
    const builderState = useAppSelector(selectBuilderState);
    const { setBackspaceCount } = useFormBuilderState();
    // const { t } = useBuilderTranslation();

    const activeFieldIndex = builderState.activeFieldIndex;

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
        console.log(lines);
        console.log('lastLineIndex', lastLineIndex);
        console.log('currentEditingLine', currentEditingLine);
        if (event.key === KeyType.ArrowUp && currentEditingLine !== 0) {
            event.stopPropagation();
            event.stopImmediatePropagation();
        } else if (event.key === KeyType.ArrowDown && currentEditingLine !== lastLineIndex) {
            event.stopPropagation();
            event.stopImmediatePropagation();
        }
    };
    const onChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
        setBackspaceCount(0);
        dispatch(
            setUpdateField({
                ...field,
                value: event.target.value
            })
        );
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
        <div id={id} className={cn('w-full relative ', preview && 'border rounded-md p-4')}>
            <div className="cursor-pointer  absolute right-3 top-1 text-gray-500" onClick={handlePreview}>
                {preview ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
            </div>

            {preview ? (
                <MarkdownText text={field.value} />
            ) : (
                <TextArea
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

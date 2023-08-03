import React, { ChangeEvent, useEffect, useRef, useState } from 'react';

import TextArea from '@Components/Common/Input/TextArea';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import cn from 'classnames';
import { useDispatch } from 'react-redux';

import useFormBuilderState from '@app/containers/form-builder/context';
import { setActiveField, setUpdateField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { useAppSelector } from '@app/store/hooks';

import MarkdownText from '../UI/MarkdownText';

interface MarkdownEditorProps {
    field: any;
    id: string;
}

export default function MarkdownEditor({ id, field }: MarkdownEditorProps) {
    const [preview, setPreview] = useState(false);
    const inputRef = useRef<HTMLTextAreaElement | null>(null);

    const dispatch = useDispatch();
    const builderState = useAppSelector(selectBuilderState);
    const { setBackspaceCount } = useFormBuilderState();
    // const { t } = useBuilderTranslation();

    const activeFieldIndex = builderState.activeFieldIndex;

    const onChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
        event.preventDefault();
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
        if (field?.position !== activeFieldIndex) return;
        // contentRef.current?.focus();
        inputRef.current?.focus();
    }, [activeFieldIndex, field?.position]);

    return (
        <div className={cn('w-full relative ', preview && 'border rounded-md p-8')}>
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
}
2;

import React from 'react';

import FormBuilderFieldSelector from '@Components/FormBuilder/BuilderBlock/FormBuilderFieldSelector';
import MentionedFieldSettings from '@Components/FormBuilder/BuilderBlock/MentionedFieldSettings';
import CustomContentEditable from '@Components/FormBuilder/ContentEditable/CustomContentEditable';
import { batch, useDispatch } from 'react-redux';

import useFormBuilderState from '@app/containers/form-builder/context';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import useUserTypingDetection from '@app/lib/hooks/use-user-typing-detection';
import useUndoRedo from '@app/lib/use-undo-redo';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setBuilderMenuState, setBuilderState, setUpdateField } from '@app/store/form-builder/actions';
import { selectFields, selectMenuState } from '@app/store/form-builder/selectors';
import { useAppSelector } from '@app/store/hooks';
import { contentEditableClassNames, convertPlaceholderToDisplayValue, getDisplayNameForField } from '@app/utils/formBuilderBlockUtils';
import { toEndDottedStr } from '@app/utils/stringUtils';

interface IHeaderInputBlockProps {
    field: any;
    id: any;
    position: number;
}

const getPlaceholder = (type: FormBuilderTagNames) => {
    switch (type) {
        case FormBuilderTagNames.LAYOUT_HEADER4:
            return '4';
        case FormBuilderTagNames.LAYOUT_HEADER3:
            return '3';
        case FormBuilderTagNames.LAYOUT_HEADER2:
            return '2';
        case FormBuilderTagNames.LAYOUT_HEADER1:
            return '1';
        case FormBuilderTagNames.LAYOUT_LABEL:
            return 'LABEL';
        default:
            return '';
    }
};
export default function HeaderInputBlock({ field, id, position }: IHeaderInputBlockProps) {
    const dispatch = useDispatch();
    const { setBackspaceCount } = useFormBuilderState();
    const { t } = useBuilderTranslation();
    const { handleUserTypingEnd } = useUserTypingDetection();
    const { isUndoRedoInProgress } = useUndoRedo();
    const pipingFieldMenuState: any = useAppSelector(selectMenuState('pipingFields'));
    const pipingSettingsState = useAppSelector(selectMenuState('pipingFieldSettings'));

    const fieldsRecord = useAppSelector(selectFields);
    const fields = Object.values(fieldsRecord);

    function convertEntitiesToNormal(inputString: string): string {
        const entityRegex = /&(#\d+|[\w]+);/g;

        return inputString.replace(entityRegex, (match, entity) => {
            if (entity.startsWith('#')) {
                // Numeric ASCII code
                const asciiCode = parseInt(entity.substring(1), 10);
                return String.fromCharCode(asciiCode);
            } else {
                // Named HTML entity
                const div = document.createElement('div');
                div.innerHTML = `&${entity};`;
                const textContent = div.textContent || div.innerText;

                // Remove the temporary div element
                div.remove();

                return textContent;
            }
        });
    }

    function convertSpanToPlaceholder(contentEditableContent: string) {
        // Create a regular expression to match the span element with a data-field-id attribute
        const spanRegex = /<span[^>]*data-field-id="([0-9a-fA-F-]+)"[^>]*>(.*?)<\/span>/g;

        // Use replace with a callback function to replace the span element with the placeholder
        const spanReplacedString = contentEditableContent.replace(spanRegex, (match, fieldId) => {
            return `{{ ${fieldId} }}`;
        });

        return convertEntitiesToNormal(spanReplacedString);
    }

    function isAtSymbolRemoved(original: string, modified: string) {
        const regex = /@/;
        const originalCount = (original.match(regex) || []).length;
        const modifiedCount = (modified.match(regex) || []).length;

        return originalCount - modifiedCount === 1;
    }

    const onChange = (event: any) => {
        const value = convertSpanToPlaceholder(event?.target?.value || '');

        batch(() => {
            // @ts-ignore
            if (event.nativeEvent.inputType === 'deleteContentBackward' && isAtSymbolRemoved(field?.value, value)) {
                dispatch(
                    setBuilderMenuState({
                        pipingFields: {
                            ...pipingFieldMenuState,
                            isOpen: false,
                            atFieldUuid: '',
                            position: 'down'
                        }
                    })
                );
            }
            if (isUndoRedoInProgress) return;
            setBackspaceCount(0);
            dispatch(
                setUpdateField({
                    ...field,
                    value: value
                })
            );
            handleUserTypingEnd();
        });
    };

    function convertPlaceholderToSpan(inputString?: string) {
        const placeholderRegex = /{{\s*([0-9a-fA-F-]+)\s*}}/g;

        // Use replace with a callback function to replace the placeholder
        return inputString?.replace(placeholderRegex, (match, fieldId) => {
            const displayName = getDisplayNameForField(fields, fieldId);
            // Replace the placeholder with a <span> element containing the field value
            return `<span contenteditable="false" class="bg-black-300 max-w-[200px] truncate rounded p-1 cursor-pointer" data-current-field="${field.id}" data-field-id="${fieldId}">@${toEndDottedStr(
                convertPlaceholderToDisplayValue(fields, displayName),
                24
            )}</span>`;
        });
    }

    const searchQuery = field.value?.match(/@([^@\s]*)/)?.[1] ?? '';

    return (
        <div>
            {pipingFieldMenuState?.isOpen && pipingFieldMenuState?.atFieldUuid === field?.id && <FormBuilderFieldSelector field={field} searchQuery={searchQuery} />}
            {pipingSettingsState?.isOpen && pipingSettingsState?.atFieldId === field?.id && <MentionedFieldSettings field={field} />}
            <CustomContentEditable
                type={field?.type}
                tagName="p"
                position={position}
                id={id}
                value={convertPlaceholderToSpan(field?.value) || ''}
                className={'w-full  ' + contentEditableClassNames(false, field?.type, true)}
                onChangeCallback={onChange}
                placeholder={t('COMPONENTS.HEADER.' + getPlaceholder(field?.type))}
                onFocusCallback={(event: React.FocusEvent<HTMLElement>) => {
                    dispatch(setBuilderState({ activeFieldIndex: position }));
                }}
            />
        </div>
    );
}

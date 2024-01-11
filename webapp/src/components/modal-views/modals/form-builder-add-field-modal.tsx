import {
    allowedAdvancedTags,
    allowedLayoutTags,
    allowedQuestionAndAnswerTags
} from '@Components/FormBuilder/BuilderBlock/FormBuilderTagSelector';
import {batch} from 'react-redux';
import {v4} from 'uuid';

import {Close} from '@app/components/icons/close';
import {useModal} from '@app/components/modal-views/context';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import {FormBuilderTagNames} from '@app/models/enums/formBuilder';
import {resetBuilderMenuState, setAddNewField, setBuilderState, setDeleteField} from '@app/store/form-builder/actions';
import {selectBuilderState} from '@app/store/form-builder/selectors';
import {IBuilderState} from '@app/store/form-builder/types';
import {useAppAsyncDispatch, useAppDispatch, useAppSelector} from '@app/store/hooks';
import useFormBuilderButtonState from "@Components/FormBuilder/bottomAtom";

const Fields = [
    {
        title: 'INSERT_MENU.WITH_LABEL',
        items: allowedQuestionAndAnswerTags
    },
    {
        title: 'INSERT_MENU.LAYOUTS',
        items: allowedLayoutTags
    },
    {
        title: 'Advanced Fields',
        items: allowedAdvancedTags
    }
];

export default function FormBuilderAddFieldModal({index}: { index?: number }) {
    const {closeModal} = useModal();
    const builderState: IBuilderState = useAppSelector(selectBuilderState);
    const {setShowButton} = useFormBuilderButtonState();

    const dispatch = useAppDispatch();
    const asyncDispatch = useAppAsyncDispatch();

    const {t} = useBuilderTranslation();
    const handleFieldSelected = (type: FormBuilderTagNames) => {
        if (type === FormBuilderTagNames.BUTTON) {
            asyncDispatch(
                setBuilderState({
                    buttonText: 'Submit'
                })
        ).
            then(() => {
                setShowButton();
                document.getElementById(`form-builder-button`)?.focus();
            })
            dispatch(resetBuilderMenuState());

        } else {
            const getActiveIndex = () => {
                if (index !== undefined && index > -1) return index;
                if (builderState.activeFieldIndex > -1) return builderState.activeFieldIndex;
                return Object.keys(builderState.fields).length - 1;
            };
            const activeIndex = getActiveIndex();
            const activeField = Object.values(builderState.fields)[activeIndex];
            const nextField = Object.values(builderState.fields)[activeIndex + 1];
            const isActiveFieldLayoutShortText = activeField?.type === FormBuilderTagNames.LAYOUT_SHORT_TEXT;
            const isNextFieldInputField = nextField?.type.includes('input_');
            const shouldInsertInCurrentField = isActiveFieldLayoutShortText && !activeField.value;

            batch(() => {
                if (shouldInsertInCurrentField) dispatch(setDeleteField(activeField.id));
                const fieldId = v4();
                asyncDispatch(
                    setAddNewField({
                        id: fieldId,
                        type,
                        position: isNextFieldInputField ? activeIndex + 1 : activeIndex
                    })
                ).then(() => document.getElementById(`item-${fieldId}`)?.focus())
                dispatch(resetBuilderMenuState());
            });
        }
        closeModal();
    };

    return (
        <div className="bg-white rounded relative flex flex-col gap-10 last:!mt-0 p-10">
            <Close
                className="absolute top-5 right-5 cursor-pointer"
                onClick={() => {
                    closeModal();
                }}
            />
            {Fields.map((fieldType, index) => (
                <div key={t(fieldType.title)} className="flex flex-col">
                    <div className="h5 !text-black-800 mb-6">{t(fieldType.title)}</div>
                    <div className="grid gap-x-12 gap-y-2 grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
                        {fieldType.items.map((tag: any, index: number) => (
                            <div
                                key={tag.id}
                                className="flex cursor-pointer hover:bg-gray-100 h-12 p-2 items-center rounded gap-2"
                                onClick={() => {
                                    handleFieldSelected(tag.type);
                                }}
                            >
                                <div className="w-7 text-pink">{tag.icon}</div>
                                <span className={'text-black-700 text-sm font-medium'}>{tag.label}</span>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

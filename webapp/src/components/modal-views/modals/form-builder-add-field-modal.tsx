import { allowedLayoutTags, allowedQuestionAndAnswerTags } from '@Components/FormBuilder/BuilderBlock/FormBuilderTagSelector';
import { batch } from 'react-redux';
import { v4 } from 'uuid';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { resetBuilderMenuState, setAddNewField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

const Fields = [
    {
        title: 'INSERT_MENU.WITH_LABEL',
        items: allowedQuestionAndAnswerTags
    },
    {
        title: 'INSERT_MENU.LAYOUTS',
        items: allowedLayoutTags
    }
    // {
    //     title: 'Elements without Label',
    //     items: allowedInputTags
    // }
];

export default function FormBuilderAddFieldModal({ index }: { index?: number }) {
    const { closeModal, modalProps } = useModal();
    const builderState = useAppSelector(selectBuilderState);

    const dispatch = useAppDispatch();

    const { t } = useBuilderTranslation();
    const handleFieldSelected = (type: FormBuilderTagNames) => {
        batch(() => {
            dispatch(
                setAddNewField({
                    id: v4(),
                    type,
                    position: builderState.activeFieldIndex >= 0 ? builderState.activeFieldIndex : Object.keys(builderState.fields).length - 1
                })
            );
            dispatch(resetBuilderMenuState());
        });
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
                    <div className="body1 mb-6">{t(fieldType.title)}</div>
                    <div className="grid gap-x-12 gap-y-2 grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
                        {fieldType.items.map((tag, index) => (
                            <div
                                key={tag.id}
                                className="flex cursor-pointer hover:bg-gray-100 h-12 p-2 items-center rounded gap-2"
                                onClick={() => {
                                    handleFieldSelected(tag.type);
                                }}
                            >
                                <div className="w-7">{tag.icon}</div>
                                <span>{tag.label}</span>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

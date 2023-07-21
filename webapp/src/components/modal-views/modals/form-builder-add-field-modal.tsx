import { allowedInputTags, allowedLayoutTags, allowedQuestionAndAnswerTags } from '@Components/FormBuilder/BuilderBlock/FormBuilderTagSelector';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setAddNewField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { addFieldNewImplementation } from '@app/store/form-builder/slice';
import { IBuilderStateProps } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

const Fields = [
    {
        title: 'Elements with Label',
        items: allowedQuestionAndAnswerTags
    },
    {
        title: 'Layouts',
        items: allowedLayoutTags
    },
    {
        title: 'Elements without Label',
        items: allowedInputTags
    }
];

export default function FormBuilderAddFieldModal({ index }: { index?: number }) {
    const { closeModal, modalProps } = useModal();
    const builderState = useAppSelector(selectBuilderState);

    const dispatch = useAppDispatch();
    const handleFieldSelected = (type: FormBuilderTagNames) => {
        dispatch(setAddNewField({ id: uuidv4(), type, position: index || Object.keys(builderState.fields).length - 1 }));
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
                <div key={fieldType.title} className="flex flex-col">
                    <div className="body1 mb-6">{fieldType.title}</div>
                    <div className="grid gap-x-12 gap-y-2 grid-cols-1 md:grid-cols-2 lg:grid-cols-4">
                        {fieldType.items.map((tag, index) => (
                            <div
                                key={tag.id}
                                className="flex cursor-pointer hover:bg-gray-100 p-2 items-center rounded gap-2"
                                onClick={() => {
                                    handleFieldSelected(tag.type);
                                }}
                            >
                                {tag.icon}
                                {tag.label}
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

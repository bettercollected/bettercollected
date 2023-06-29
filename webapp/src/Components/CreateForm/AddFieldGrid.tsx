import Image from 'next/image';

import { FormIcon } from '@Components/Common/Icons/FormIcon';
import { useDispatch } from 'react-redux';

import { QUESTION_TYPE } from '@app/components/form/renderer/form-renderer';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { addField } from '@app/store/form-builder/slice';

export const FieldsMap: {
    [key: string]: any;
} = {
    [QUESTION_TYPE.SHORT_TEXT]: {
        value: 'Short Text',
        icon: <FormIcon />
    },
    [QUESTION_TYPE.LONG_TEXT]: {
        value: 'Long Text',
        icon: <FormIcon />
    },
    [QUESTION_TYPE.STATEMENT]: {
        value: 'Statement',
        icon: <FormIcon />
    },
    [QUESTION_TYPE.EMAIL]: {
        value: 'Email',
        icon: <FormIcon />
    }
};

interface IAddFieldFridProps {
    closeModal: () => void;
}

AddFieldGrid.defaultProps = {
    closeModal: () => {}
};

export default function AddFieldGrid({ closeModal }: IAddFieldFridProps) {
    const dispatch = useDispatch();
    const addFormField = (type: string) => {
        dispatch(addField(type));
        closeModal();
    };

    return (
        <div className="mt-4 grid w-full grid-cols-2  items-center gap-5 md:grid-cols-3 lg:grid-cols-4">
            {Object.keys(FieldsMap).map((key: string) => (
                <div key={key}>
                    <div
                        className="text-md box-shadow flex cursor-pointer items-center space-x-4 rounded bg-white px-5 py-4"
                        onClick={() => {
                            addFormField(key);
                        }}
                    >
                        <span className={'mr-4 flex items-center md:flex'}>{FieldsMap[key].icon}</span>
                        {FieldsMap[key].value}
                    </div>
                </div>
            ))}
        </div>
    );
}

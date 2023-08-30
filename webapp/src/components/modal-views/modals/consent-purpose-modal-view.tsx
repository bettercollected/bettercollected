import React, { useState } from 'react';

import AppButton from '@Components/Common/Input/Button/AppButton';
import MuiSwitch from '@Components/Common/Input/Switch';
import TextArea from '@Components/Common/Input/TextArea';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import ContentEditable from 'react-contenteditable';

import { DropdownCloseIcon } from '@app/components/icons/dropdown-close';
import { ConsentCategoryType, ConsentType } from '@app/models/enums/consentEnum';
import { setAddConsent, setUpdateConsent } from '@app/store/consent/actions';
import { IConsentField } from '@app/store/consent/types';
import { useAppDispatch } from '@app/store/hooks';

import { useModal } from '../context';

export type ConsentPurposeModalMode = 'add' | 'update' | 'create';

export interface ConsentPurposeModalProps {
    selection?: string;
    category: ConsentCategoryType;
    type: ConsentType;
    description?: string;
    required?: boolean;
    consentId?: string;
    mode?: ConsentPurposeModalMode;
}

export default function ConsentPurposeModalView() {
    const { closeModal, modalProps } = useModal();
    const consentPurposeModalProps = modalProps as ConsentPurposeModalProps | null;
    const [purposeTitle, setPurposeTitle] = useState(consentPurposeModalProps?.selection ?? '');
    const [purposeDescription, setPurposeDescription] = useState(consentPurposeModalProps?.description ?? '');
    const [isRequired, setIsRequired] = useState(consentPurposeModalProps?.required ?? false);

    const dispatch = useAppDispatch();

    const handlePurposeTitleChange = (event: any) => {
        setPurposeTitle(event.target.value);
    };

    const handleDescriptionChange = (event: any) => {
        setPurposeDescription(event.target.value);
    };

    const handleToggle = (event: any) => {
        setIsRequired(event.target.checked);
    };

    const onAddUpdate = () => {
        const consentField: IConsentField = {
            id: consentPurposeModalProps?.mode === 'update' ? consentPurposeModalProps.consentId! : uuidv4(),
            category: consentPurposeModalProps?.category,
            description: purposeDescription,
            required: isRequired,
            type: consentPurposeModalProps?.type,
            title: purposeTitle
        };
        if (consentPurposeModalProps?.mode === 'update') {
            dispatch(setUpdateConsent(consentField));
        } else {
            dispatch(setAddConsent(consentField));
        }
        closeModal();
    };

    const getButtonText = () => {
        if (consentPurposeModalProps?.mode === 'update') {
            return 'Update';
        } else if (consentPurposeModalProps?.mode === 'create') {
            return 'Create';
        }
        return 'Add';
    };
    return (
        <div className="bg-white rounded-2xl w-fit md:w-[621px] h-content">
            <div className="flex justify-between py-4 px-6 border-b border-black-200">
                <div className="p2 !text-black-800">Purpose Of The Form</div>
                <DropdownCloseIcon className="cursor-pointer" onClick={closeModal} />
            </div>
            <div className="pt-4 md:pt-6 pb-7 md:pb-10 space-y-7 md:space-y-10">
                <ContentEditable className="h3-new m-0 p-0 w-full cursor-text focus-visible:border-0 focus-visible:outline-none px-7 md:px-10" html={purposeTitle} data-placeholder="Add Purpose" onChange={handlePurposeTitleChange} />

                <div className="space-y-2 px-7 md:px-10">
                    <div className="h5-new xs:!text-sm">Brief description of your purpose</div>
                    <TextArea placeholder="Enter text here" minRows={4} value={purposeDescription} onChange={handleDescriptionChange} />
                </div>

                <div className="flex justify-between bg-blue-100  px-7 md:px-10 py-4 md:py-6">
                    <div className="space-y-3">
                        <div className="h5-new xs:!text-sm">Make this purpose required (*)</div>
                        <p className="p2 !text-black-800 xs:!text-sm">Enabling this option will make the purpose section mandatory (*). Users filling out the form must accept this purpose and acknowledge it.</p>
                    </div>
                    <MuiSwitch thumbSize={24} trackColorUnchecked="#AAAAAA" checked={isRequired} onChange={handleToggle} />
                </div>
                <div className="px-7 md:px-10">
                    <AppButton className="w-[100px] md:w-[192px] py-3 px-8 bg-new-blue-500" onClick={onAddUpdate}>
                        {getButtonText()}
                    </AppButton>
                </div>
            </div>
        </div>
    );
}

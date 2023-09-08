import React, { useEffect, useRef, useState } from 'react';

import AppButton from '@Components/Common/Input/Button/AppButton';
import MuiSwitch from '@Components/Common/Input/Switch';
import TextArea from '@Components/Common/Input/TextArea';
import ConsentModalTopBar from '@Components/Consent/ConsentModalTopBar';
import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import ContentEditable from 'react-contenteditable';
import { toast } from 'react-toastify';

import { DropdownCloseIcon } from '@app/components/icons/dropdown-close';
import { IConsentOption } from '@app/models/types/consentTypes';
import { setAddConsent, setUpdateConsent } from '@app/store/consent/actions';
import { useCreateWorkspaceConsentMutation } from '@app/store/consent/api';
import { IConsentField } from '@app/store/consent/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

import { useModal } from '../context';

export type ConsentPurposeModalMode = 'add' | 'update' | 'create';

export interface ConsentPurposeModalProps {
    consent: IConsentOption;
    mode?: ConsentPurposeModalMode;
}

export default function ConsentPurposeModalView() {
    const { closeModal, modalProps } = useModal();
    const workspace = useAppSelector(selectWorkspace);
    const [createWorkspaceConsent] = useCreateWorkspaceConsentMutation();
    const consentPurposeModalProps = modalProps as ConsentPurposeModalProps | null;
    const [purposeTitle, setPurposeTitle] = useState(consentPurposeModalProps?.consent.title ?? '');
    const [purposeDescription, setPurposeDescription] = useState(consentPurposeModalProps?.consent.description ?? '');
    const [isRequired, setIsRequired] = useState(consentPurposeModalProps?.consent.required ?? false);
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

    const onDone = () => {
        const consentField: IConsentField = {
            consentId: consentPurposeModalProps?.mode === 'update' ? consentPurposeModalProps?.consent.consentId! : uuidv4(),
            category: consentPurposeModalProps?.consent.category,
            description: purposeDescription,
            required: isRequired,
            type: consentPurposeModalProps?.consent.type,
            title: purposeTitle
        };
        if (consentPurposeModalProps?.mode === 'create') {
            createWorkspaceConsent({ workspaceId: workspace.id, consent: consentField }).catch(() => {
                toast.error('Failed to create workspace');
            });
            dispatch(setAddConsent(consentField));
        } else if (consentPurposeModalProps?.mode === 'update') {
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
            <ConsentModalTopBar />
            <div className="pt-4 md:pt-6 pb-7 md:pb-10 space-y-7 md:space-y-10">
                <ContentEditable className="h3-new m-0 p-0 w-full cursor-text focus-visible:border-0 focus-visible:outline-none px-7 md:px-10" html={purposeTitle} data-placeholder="Add Purpose" onChange={handlePurposeTitleChange} />

                <div className="space-y-2 px-7 md:px-10">
                    <div className="h5-new">Brief description of your purpose</div>
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
                    <AppButton className="w-[100px] md:w-[192px] py-3 px-8 bg-new-blue-500" onClick={onDone}>
                        {getButtonText()}
                    </AppButton>
                </div>
            </div>
        </div>
    );
}

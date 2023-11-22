import React, { useCallback, useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import _ from 'lodash';

import AppTextField from '@Components/Common/Input/AppTextField';

import environments from '@app/configs/environments';
import { onBoarding } from '@app/constants/locales/onboarding-screen';
import { FormDataDto } from '@app/containers/Onboarding';
import { useAppSelector } from '@app/store/hooks';
import { useLazyGetWorkspaceNameAvailabilityQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

import { InfoIcon } from '../icons/info-icon';

interface ITextFieldHandler {
    formData: FormDataDto;
    workspaceNameSuggestion: string;
    setFormData: any;
    errorWorkspaceName: boolean;
}

const TextFieldHandler = ({ formData, workspaceNameSuggestion, setFormData, errorWorkspaceName }: ITextFieldHandler) => {
    const [getWorkspaceAvailability, { isLoading: isCheckingHandleName }] = useLazyGetWorkspaceNameAvailabilityQuery();
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);

    useEffect(() => {
        if (errorWorkspaceName) {
            setIsErrorWorkspaceName(true);
            setErrorMessage('Please fill the handle name');
        } else {
            setIsErrorWorkspaceName(false);
        }
    }, [errorWorkspaceName]);

    const [isErrorWorkspaceName, setIsErrorWorkspaceName] = useState(false);
    const [errorMessage, setErrorMessage] = useState('');

    async function getAvailability(value: string) {
        const availability = await getAvailabilityStatusOfWorkspaceName(value);
        if (!availability) {
            setIsErrorWorkspaceName(true);
            setErrorMessage('Handle name already taken. Try another.');
        }
    }

    const checkWorkspacename = useCallback(
        _.debounce((value: string) => getAvailability(value), 200),
        []
    );

    const getAvailabilityStatusOfWorkspaceName = async (workspace_name: string | null) => {
        const request = {
            workspaceId: workspace.id,
            title: workspace_name
        };
        const { isSuccess, data } = await getWorkspaceAvailability(request);
        if (isSuccess) {
            return data === 'True';
        }
        return false;
    };

    const setWorkspaceSuggestionToWorkspaceNameField = (suggestion: string) => {
        setFormData({ ...formData, workspaceName: suggestion });
    };

    const [handleName, setHandleName] = useState(formData.title);

    useEffect(() => {
        setHandleName(formData.title.toLowerCase());
        setFormData({
            ...formData,
            workspaceName: formData.title.toLowerCase()
        });
    }, [formData.title]);

    const handleOnchange = (e: any) => {
        const inputText = e.target.value;
        if (e.target.id === 'workspaceName') {
            if (!inputText) {
                setIsErrorWorkspaceName(true);
                setErrorMessage(t(onBoarding.fillHandleName));
            } else if (inputText.includes(' ')) {
                setIsErrorWorkspaceName(true);
                setErrorMessage(t(onBoarding.spaceNotAllowed));
            } else if (!inputText.match(/^[a-zA-Z0-9_]+$/)) {
                setIsErrorWorkspaceName(true);
                setErrorMessage(t(onBoarding.allowedCharacters));
            } else {
                setIsErrorWorkspaceName(false);
                checkWorkspacename(inputText.toLowerCase());
            }
        }
        setHandleName(inputText.toLowerCase());
        setFormData({
            ...formData,
            workspaceName: inputText.toLowerCase()
        });
    };

    return (
        <div>
            <AppTextField title="Handle Name" id="workspaceName" placeholder="Enter workspace handle name" value={handleName} onChange={handleOnchange} isError={isErrorWorkspaceName}>
                <AppTextField.Description>
                    {t(onBoarding.useSmallCase)} (eg: abc) <br />
                    https://{environments.CLIENT_DOMAIN}/<span className="text-pink-500">{formData.workspaceName}</span>
                </AppTextField.Description>
            </AppTextField>

            {!isErrorWorkspaceName ? (
                <></>
            ) : (
                <>
                    <div className={'text-red-600 text-xs md:text-sm !mt-2 flex items-center gap-2'}>
                        <InfoIcon className="w-4 h-4" />
                        {errorMessage}
                    </div>
                    {workspaceNameSuggestion && (
                        <div className={'flex items-center flex-wrap !mt-2'}>
                            <p className={'text-sm'}>{t(onBoarding.workspaceNameAvailable)}: &nbsp; </p>
                            <p
                                className={'text-sm font-semibold text-blue-500 cursor-pointer'}
                                onClick={() => {
                                    setWorkspaceSuggestionToWorkspaceNameField(workspaceNameSuggestion);
                                    setIsErrorWorkspaceName(false);
                                }}
                            >
                                {` ${workspaceNameSuggestion}`}
                            </p>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default TextFieldHandler;

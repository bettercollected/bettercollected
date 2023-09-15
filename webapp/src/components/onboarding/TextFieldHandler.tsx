import React, { useCallback, useEffect, useState } from 'react';

import _ from 'lodash';

import AppTextField from '@Components/Common/Input/AppTextField';

import environments from '@app/configs/environments';
import { FormDataDto } from '@app/containers/Onboarding';
import { useLazyGetWorkspaceNameAvailabilityQuery } from '@app/store/workspaces/api';

import { InfoIcon } from '../icons/info-icon';
import { useTranslation } from 'next-i18next';
import { onBoarding } from '@app/constants/locales/onboarding-screen';

interface ITextFieldHandler {
    formData: FormDataDto;
    workspaceNameSuggestion: string;
    setFormData: any;
    errorWorkspaceName: boolean;
}

const TextFieldHandler = ({ formData, workspaceNameSuggestion, setFormData, errorWorkspaceName }: ITextFieldHandler) => {
    const [getWorkspaceAvailability, { isLoading: isCheckingHandleName }] = useLazyGetWorkspaceNameAvailabilityQuery();
    const { t } = useTranslation();

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
        const { isSuccess, data } = await getWorkspaceAvailability(workspace_name);
        if (isSuccess) {
            return data === 'True';
        }
        return false;
    };

    const setWorkspaceSuggestionToWorkspaceNameField = (suggestion: string) => {
        setFormData({ ...formData, workspaceName: suggestion });
    };

    const handleOnchange = (e: any) => {
        if (e.target.id === 'workspaceName') {
            if (!e.target.value) {
                setIsErrorWorkspaceName(true);
                setErrorMessage(t(onBoarding.fillHandleName));
            } else if (e.target.value.includes(' ')) {
                setIsErrorWorkspaceName(true);
                setErrorMessage(t(onBoarding.spaceNotAllowed));
            } else if (!e.target.value.match(/^[a-z0-9_]+$/)) {
                setIsErrorWorkspaceName(true);
                setErrorMessage(t(onBoarding.allowedCharacters));
            } else {
                setIsErrorWorkspaceName(false);
                checkWorkspacename(e.target.value);
            }
        }
        setFormData({
            ...formData,
            workspaceName: e.target.value
        });
    };

    return (
        <div>
            <AppTextField title="Handle Name" id="workspaceName" placeholder="Enter workspace handle name" value={formData.workspaceName} onChange={handleOnchange} isError={isErrorWorkspaceName}>
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

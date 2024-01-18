import React, { useCallback, useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import _ from 'lodash';

import AppTextField from '@Components/Common/Input/AppTextField';

import environments from '@app/configs/environments';
import { onBoarding } from '@app/constants/locales/onboarding-screen';
import { FormDataDto } from '@app/containers/Onboarding';
import { useAppSelector } from '@app/store/hooks';
import { useLazyGetWorkspaceNameAvailabilityQuery, useLazyGetWorkspaceNameSuggestionsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { checkIfPredefinedWorkspaceName } from '@app/utils/workspaceNameUtils';

import { InfoIcon } from '../icons/info-icon';

interface ITextFieldHandler {
    formData: FormDataDto;
    setFormData: any;
    handleOnChange: any;
}

const TextFieldHandler = ({ formData, setFormData, handleOnChange }: ITextFieldHandler) => {
    const [getWorkspaceAvailability] = useLazyGetWorkspaceNameAvailabilityQuery();
    const [trigger] = useLazyGetWorkspaceNameSuggestionsQuery();
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);

    const [errorMessage, setErrorMessage] = useState('');
    const [workspaceNameSuggestion, setWorkspaceNameSuggestion] = useState<string>('');

    async function getAvailability(value: string) {
        const availability = await getAvailabilityStatusOfWorkspaceName(value);
        if (!availability) {
            if (checkIfPredefinedWorkspaceName(value)) {
                setErrorMessage('It is predefined name. Please take another name.');
            } else {
                setErrorMessage('Handle name already taken. Try another.');
            }
        } else {
            setErrorMessage('');
        }
    }

    const checkWorkspaceName = useCallback(
        _.debounce((value: string) => getAvailability(value), 200),
        []
    );

    const getAvailabilityStatusOfWorkspaceName = async (workspace_name: string | null) => {
        if (checkIfPredefinedWorkspaceName(workspace_name)) return;
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

    useEffect(() => {
        let workspaceName = formData.workspaceName;
        getAvailabilityStatusOfWorkspaceName(workspaceName).then((availability) => {
            if (!availability) {
                fetchSuggestionsForWorkspaceHandle(formData.title).then((suggestion) => {
                    workspaceName = suggestion;
                });
            } else {
            }
        });
        setFormData({
            ...formData,
            workspaceName: workspaceName
        });
    }, []);

    useEffect(() => {
        const inputText = formData.workspaceName;
        if (!inputText) {
            setErrorMessage(t(onBoarding.fillHandleName));
        } else if (inputText.includes(' ')) {
            setErrorMessage(t(onBoarding.spaceNotAllowed));
        } else if (!inputText.match(/^[a-zA-Z0-9_]+$/)) {
            setErrorMessage(t(onBoarding.allowedCharacters));
        } else {
            checkWorkspaceName(inputText.toLowerCase());
        }
        getAvailability(formData.workspaceName);
    }, [formData.workspaceName]);

    const fetchSuggestionsForWorkspaceHandle = async (text: string) => {
        if (!!text) {
            const request = {
                workspaceId: workspace?.id,
                title: text.toLowerCase()
            };
            const { isSuccess, data } = await trigger(request);
            if (isSuccess) {
                const suggestion = data[Math.floor(Math.random() * 4) + 1];
                setWorkspaceNameSuggestion(suggestion);
                return suggestion;
            }
        }
    };

    return (
        <div>
            <AppTextField required title="Handle Name" id="workspaceName" placeholder="Enter workspace handle name" value={formData.workspaceName} onChange={handleOnChange} isError={!!errorMessage && !!errorMessage && !!formData.workspaceName}>
                <AppTextField.Description>
                    {t(onBoarding.useSmallCase)} (eg: abc) <br />
                    https://{environments.CLIENT_DOMAIN}/<span className="text-pink-500">{formData.workspaceName}</span>
                </AppTextField.Description>
            </AppTextField>
            {errorMessage && formData.workspaceName && (
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

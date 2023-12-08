import React, {useCallback, useEffect, useState} from 'react';

import {useTranslation} from 'next-i18next';

import _ from 'lodash';

import AppTextField from '@Components/Common/Input/AppTextField';

import environments from '@app/configs/environments';
import {onBoarding} from '@app/constants/locales/onboarding-screen';
import {FormDataDto} from '@app/containers/Onboarding';
import {useAppSelector} from '@app/store/hooks';
import {useLazyGetWorkspaceNameAvailabilityQuery} from '@app/store/workspaces/api';
import {selectWorkspace} from '@app/store/workspaces/slice';

import {InfoIcon} from '../icons/info-icon';
import {checkIfPredefinedWorkspaceName} from "@app/utils/workspaceNameUtils";

interface ITextFieldHandler {
    formData: FormDataDto;
    workspaceNameSuggestion: string;
    setFormData: any;
    errorWorkspaceName: boolean;
    setIsErrorOnTextField: any;
}

const TextFieldHandler = ({
                              formData,
                              workspaceNameSuggestion,
                              setFormData,
                              errorWorkspaceName,
                              setIsErrorOnTextField
                          }: ITextFieldHandler) => {
    const [getWorkspaceAvailability, {isLoading: isCheckingHandleName}] = useLazyGetWorkspaceNameAvailabilityQuery();
    const {t} = useTranslation();
    const workspace = useAppSelector(selectWorkspace);

    useEffect(() => {
        if (errorWorkspaceName) {
            setIsErrorWorkspaceName(true);
            setErrorMessage(t(onBoarding.fillHandleName));
        } else {
            setIsErrorWorkspaceName(false);
        }
    }, [errorWorkspaceName]);

    const [isErrorWorkspaceName, setIsErrorWorkspaceName] = useState(false);
    const [errorMessage, setErrorMessage] = useState('');

    useEffect(() => {
        setIsErrorOnTextField(isErrorWorkspaceName)
    }, [isErrorWorkspaceName]);

    async function getAvailability(value: string) {
        const availability = await getAvailabilityStatusOfWorkspaceName(value);
        if (!availability) {
            setIsErrorWorkspaceName(true);
            if (checkIfPredefinedWorkspaceName(value)) {
                setErrorMessage('It is predefined name. Please take another name.');
            } else {
                setErrorMessage('Handle name already taken. Try another.');

            }
        }
    }

    const checkWorkspacename = useCallback(
        _.debounce((value: string) => getAvailability(value), 200),
        []
    );

    const getAvailabilityStatusOfWorkspaceName = async (workspace_name: string | null) => {
        if (checkIfPredefinedWorkspaceName(workspace_name)) return;
        const request = {
            workspaceId: workspace.id,
            title: workspace_name
        };
        const {isSuccess, data} = await getWorkspaceAvailability(request);
        if (isSuccess) {
            return data === 'True';
        }
        return false;
    };

    const setWorkspaceSuggestionToWorkspaceNameField = (suggestion: string) => {
        setFormData({...formData, workspaceName: suggestion});
    };

    const [handleName, setHandleName] = useState(formData.title);

    useEffect(() => {
        const title = formData.title
            .replace(/\s/g, '')
            .replace(/[^a-zA-Z0-9]/g, '')
            .toLowerCase();
        setHandleName(title);
        setFormData({
            ...formData,
            workspaceName: title
        });
    }, []);

    useEffect(() => {
        formData.workspaceName && setHandleName(formData.workspaceName);
    }, [formData.workspaceName]);

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
        setFormData({
            ...formData,
            workspaceName: inputText.toLowerCase()
        });
        setHandleName(inputText.toLowerCase());
    };

    return (
        <div>
            <AppTextField title="Handle Name" id="workspaceName" placeholder="Enter workspace handle name"
                          value={handleName} onChange={handleOnchange} isError={isErrorWorkspaceName}>
                <AppTextField.Description>
                    {t(onBoarding.useSmallCase)} (eg: abc) <br/>
                    https://{environments.CLIENT_DOMAIN}/<span className="text-pink-500">{handleName}</span>
                </AppTextField.Description>
            </AppTextField>

            {!isErrorWorkspaceName ? (
                <></>
            ) : (
                <>
                    <div className={'text-red-600 text-xs md:text-sm !mt-2 flex items-center gap-2'}>
                        <InfoIcon className="w-4 h-4"/>
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

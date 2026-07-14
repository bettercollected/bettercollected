"use client";
import { useCallback, useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import _ from 'lodash';


import { onBoarding } from '@app/constants/locales/onboarding-screen';
import { FormDataDto } from '@app/containers/onboarding';
import { useAppSelector } from '@app/store/hooks';
import { useLazyGetWorkspaceNameAvailabilityQuery, useLazyGetWorkspaceNameSuggestionsQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { checkIfPredefinedWorkspaceName } from '@app/utils/workspace-utils';

import { AppInput } from '@app/shadcn/components/ui/input';
import { Label } from '@app/shadcn/components/ui/label';
import { InfoIcon } from '../icons/info-icon';

interface IWorkspaceNameInputHandler {
    formData: FormDataDto;
    setFormData: any;
    handleOnChange: any;
    createWorkspace?: boolean;
}

const WorkspaceNameInputHandler = ({ formData, setFormData, handleOnChange, createWorkspace }: IWorkspaceNameInputHandler) => {
    const [getWorkspaceAvailability] = useLazyGetWorkspaceNameAvailabilityQuery();
    const [trigger, { data }] = useLazyGetWorkspaceNameSuggestionsQuery();
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
            fetchSuggestionsForWorkspaceHandle(formData.title);
        } else {
            setErrorMessage('');
        }
    }

    const checkWorkspaceNameAvailability = useCallback((value: string) =>
        _.debounce((value: string) => getAvailability(value), 200),
        [getAvailability]
    );

    const getAvailabilityStatusOfWorkspaceName = async (workspace_name: string | null) => {
        if (checkIfPredefinedWorkspaceName(workspace_name)) return false;
        const request = {
            workspaceId: createWorkspace ? '' : workspace.id,
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
        if (workspaceName) {
            getAvailabilityStatusOfWorkspaceName(workspaceName).then((availability) => {
                if (!availability) {
                    fetchSuggestionsForWorkspaceHandle(formData.title).then((suggestion) => {
                        // No suggestion (empty title / failed fetch) must not
                        // write undefined — that flips the input to
                        // uncontrolled and React logs an error.
                        if (suggestion) setFormData({ ...formData, workspaceName: suggestion });
                    });
                }
            });
        } else {
            fetchSuggestionsForWorkspaceHandle(formData.title.toLowerCase()).then((suggestion) => {
                if (suggestion) setFormData({ ...formData, workspaceName: suggestion });
            });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (formData.workspaceName) {
            if (formData.workspaceName.includes(' ')) {
                setErrorMessage(t(onBoarding.spaceNotAllowed));
                fetchSuggestionsForWorkspaceHandle(formData.title);
            } else if (!formData.workspaceName.match(/^[a-zA-Z0-9_]+$/)) {
                setErrorMessage(t(onBoarding.allowedCharacters));
                fetchSuggestionsForWorkspaceHandle(formData.title);
            } else {
                checkWorkspaceNameAvailability(formData.workspaceName.toLowerCase());
            }
        }
    }, [formData.workspaceName]);

    const fetchSuggestionsForWorkspaceHandle = async (text: string) => {
        if (!!text) {
            const request = {
                workspaceId: createWorkspace ? '' : workspace?.id,
                title: text.toLowerCase()
            };
            const { isSuccess, data } = await trigger(request);
            if (isSuccess) {
                if (data.includes(text)) {
                    return text;
                } else {
                    // Fewer than 5 suggestions made this index out of range.
                    const suggestion = data[Math.floor(Math.random() * 4) + 1] ?? data[0];
                    if (suggestion) setWorkspaceNameSuggestion(suggestion);
                    return suggestion;
                }
            }
        }
    };

    return (
        <div className="flex flex-col gap-1.5 w-full relative">
            <Label htmlFor="workspaceName" className="text-sm font-medium ml-1 mb-1 text-gray-700">
                Handle Name
            </Label>
            <AppInput
                required
                id="workspaceName"
                placeholder="Enter workspace handle name"
                value={formData.workspaceName?.toLowerCase() ?? ''}
                onChange={handleOnChange}
                className={errorMessage && formData.workspaceName ? 'border-red-500 focus-visible:ring-red-500 w-full' : 'w-full'}
            />
            <p className="text-xs text-gray-500 ml-1 mt-1">
                {t(onBoarding.useSmallCase)} (eg: abc) <br />
                https://{window.PUBLIC_CONFIG?.FORM_DOMAIN}/<span className="text-pink-500 font-medium">{formData.workspaceName?.toLowerCase()}</span>
            </p>
            {errorMessage && formData.workspaceName && (
                <>
                    <div className={'text-red-600 text-xs md:text-sm mt-2 flex items-center gap-2'}>
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

export default WorkspaceNameInputHandler;

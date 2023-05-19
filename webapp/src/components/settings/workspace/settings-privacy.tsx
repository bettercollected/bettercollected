import React, { MutableRefObject, useEffect, useRef, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import styled from '@emotion/styled';
import HelpIcon from '@mui/icons-material/Help';
import ModeEditIcon from '@mui/icons-material/ModeEdit';
import SaveIcon from '@mui/icons-material/Save';
import TextField from '@mui/material/TextField';
import { toast } from 'react-toastify';

import environments from '@app/configs/environments';
import { localesGlobal } from '@app/constants/locales/global';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { privacyPolicyTooltip, termsOfServiceTooltip } from '@app/constants/tooltipContent';
import { useAppSelector } from '@app/store/hooks';
import { usePatchWorkspacePoliciesMutation } from '@app/store/workspaces/api';

const StyledTextField = styled.div`
    width: 100%;

    .MuiFormControl-root {
        width: 100%;
        background: white;
        border-radius: 4px;
        outline: none;
        background-color: #f0f8ff;
    }

    .MuiOutlinedInput-notchedOutline {
        border-width: 0px;
        width: 100%;
    }

    .MuiOutlinedInput-input {
        width: 100%;
    }

    .Mui-disabled {
        -webkit-text-fill-color: #757575;
    }

    @media screen and (max-width: 640px) {
        .MuiFormControl-root {
            width: 100%;
        }
    }
`;

const CardContainer = (props: any) => {
    const className = props?.className ?? '';
    return <div className={`w-full p-4 h-32 mb-4 border-solid border-[1px] rounded-md border-[#efefef] lg:w-2/3 ${className}`}>{props.children}</div>;
};

const IconContainer = (props: any) => {
    return <div className="p-1 ml-2 my-19 bg-blue-600 hover:bg-blue-700 cursor-pointer rounded-md">{props.children}</div>;
};

const CardTitle = ({ title, tooltipDesc }: any) => {
    return (
        <div className="flex pl-[15px] h-4 items-center">
            <h1 className="text-gray-500 text-sm">{title}</h1>
            <Tooltip title={tooltipDesc}>
                <HelpIcon className="text-gray-500 cursor-pointer !w-5 !h-5 ml-2" />
            </Tooltip>
        </div>
    );
};

export default function Settingsprivacy({ className = '', childClassName = '' }: { className?: string; childClassName?: string }) {
    const [policies, setPolicies] = useState({ privacy_policy_url: '', terms_of_service_url: '' });
    const { t } = useTranslation();
    const workspace = useAppSelector((state) => state.workspace);
    const [patchWorkspacePolicies, { isLoading }] = usePatchWorkspacePoliciesMutation();

    const privacyPolicyInputRef = useRef() as MutableRefObject<HTMLInputElement>;
    const termsOfServiceInputRef = useRef() as MutableRefObject<HTMLInputElement>;

    const [editMode, setEditMode] = useState({ privacy_policy_editMode: false, terms_of_service_editMode: false });
    const router = useRouter();

    useEffect(() => {
        const domain = 'https://bettercollected.com';
        // TODO: Update privacy policy URL and TOC URL
        // const privacyPolicyUrl = workspace.privacy_policy_url ? workspace.privacy_policy_url : `${domain}${environments.PRIVACY_POLICY}`;
        // const termsAndConditionsUrl = workspace.terms_of_service_url ? workspace.terms_of_service_url : `${domain}${environments.TERMS_AND_CONDITIONS}`;
        // setPolicies({ privacy_policy_url: privacyPolicyUrl, terms_of_service_url: termsAndConditionsUrl });
    }, []);

    useEffect(() => {
        if (editMode.privacy_policy_editMode) {
            privacyPolicyInputRef.current.focus();
        }
    }, [editMode.privacy_policy_editMode]);

    useEffect(() => {
        if (editMode.terms_of_service_editMode) {
            termsOfServiceInputRef.current.focus();
        }
    }, [editMode.terms_of_service_editMode]);

    const handleEmailValidation = (str: string) => {
        if (!str) return;
        const testRegex = /(^(https:\/\/www\.|https:\/\/)?[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?$)/;
        const result = testRegex.test(str);
        return result;
    };

    const handleChange = (e: any) => {
        setPolicies({ ...policies, [e.target.name]: e.target.value });
    };

    const handleSavePrivacyPolicy = async () => {
        if (isLoading) return;
        if (!policies.privacy_policy_url) return;

        if (!handleEmailValidation(policies.privacy_policy_url)) {
            toast.error(t(toastMessage.invalidUrl).toString(), { type: 'error', toastId: ToastId.ERROR_TOAST });
            return;
        }
        if (workspace.privacy_policy_url === policies.privacy_policy_url) {
            setEditMode({ ...editMode, privacy_policy_editMode: false });
            return;
        }
        const formData = new FormData();
        if (workspace.privacy_policy_url !== policies.privacy_policy_url) formData.append('privacy_policy_url', policies.privacy_policy_url);
        try {
            await patchWorkspacePolicies({ workspace_id: workspace.id, body: formData });
            setEditMode({ ...editMode, privacy_policy_editMode: false });
            router.push(router.asPath, undefined);
            toast(t(toastMessage.updated).toString(), { type: 'success', toastId: ToastId.SUCCESS_TOAST });
        } catch (e) {
            toast(t(toastMessage.somethingWentWrong).toString(), { type: 'error', toastId: ToastId.ERROR_TOAST });
        }
    };

    const handleSaveTermsOfService = async () => {
        if (isLoading) return;
        if (!policies.terms_of_service_url) return;

        if (!handleEmailValidation(policies.terms_of_service_url)) {
            toast.error(t(toastMessage.invalidUrl).toString(), { type: 'error', toastId: ToastId.ERROR_TOAST });
            return;
        }
        if (workspace.terms_of_service_url === policies.terms_of_service_url) {
            setEditMode({ ...editMode, terms_of_service_editMode: false });
            return;
        }
        const formData = new FormData();
        if (workspace.terms_of_service_url !== policies.terms_of_service_url) formData.append('terms_of_service_url', policies.terms_of_service_url);
        try {
            await patchWorkspacePolicies({ workspace_id: workspace.id, body: formData });
            setEditMode({ ...editMode, terms_of_service_editMode: false });
            router.push(router.asPath, undefined);
            toast(t(toastMessage.updated).toString(), { type: 'success', toastId: ToastId.SUCCESS_TOAST });
        } catch (e) {
            toast(t(toastMessage.somethingWentWrong).toString(), { type: 'error', toastId: ToastId.ERROR_TOAST });
        }
    };

    return (
        <div className={`lg:w-2/3 mb-10 ${className}`}>
            <CardContainer className={childClassName}>
                <CardTitle title={t(localesGlobal.linkToPrivacyPolicy)} tooltipDesc={privacyPolicyTooltip} />
                <div className="flex items-center h-24 justify-between">
                    <StyledTextField>
                        <TextField
                            inputRef={privacyPolicyInputRef}
                            data-testid="privacy-policy"
                            error={!handleEmailValidation(policies.privacy_policy_url)}
                            onChange={handleChange}
                            size="medium"
                            InputLabelProps={{ shrink: false }}
                            disabled={!editMode.privacy_policy_editMode}
                            value={policies.privacy_policy_url}
                            name="privacy_policy_url"
                            placeholder={`Enter URL (e.g. ${environments.API_ENDPOINT_HOST}/legal/privacy-policy-2022.pdf )`}
                        />
                    </StyledTextField>
                    {!editMode.privacy_policy_editMode ? (
                        <IconContainer>
                            <ModeEditIcon data-testid="privacy-policy-edit-button" className="!w-5 !h-5 text-white" onClick={() => setEditMode({ ...editMode, privacy_policy_editMode: true })} />
                        </IconContainer>
                    ) : (
                        <IconContainer>
                            <SaveIcon data-testid="privacy-policy-save-button" className="!w-5 !h-5 text-white" onClick={handleSavePrivacyPolicy} />
                        </IconContainer>
                    )}
                </div>
            </CardContainer>

            <CardContainer className={childClassName}>
                <CardTitle title="Link to Terms of service" tooltipDesc={termsOfServiceTooltip} />
                <div className="flex items-center h-24 justify-between">
                    <StyledTextField>
                        <TextField
                            inputRef={termsOfServiceInputRef}
                            data-testid="terms-of-service"
                            error={!handleEmailValidation(policies.terms_of_service_url)}
                            onChange={handleChange}
                            InputLabelProps={{ shrink: false }}
                            size="medium"
                            disabled={!editMode.terms_of_service_editMode}
                            value={policies.terms_of_service_url}
                            name="terms_of_service_url"
                            placeholder={`Enter url (e.g. ${environments.API_ENDPOINT_HOST}/legal/terms-and-conditions-2022.pdf )`}
                        />
                    </StyledTextField>
                    {!editMode.terms_of_service_editMode ? (
                        <IconContainer>
                            <ModeEditIcon className="!w-5 !h-5 text-white" onClick={() => setEditMode({ ...editMode, terms_of_service_editMode: true })} />
                        </IconContainer>
                    ) : (
                        <IconContainer>
                            <SaveIcon className="!w-5 !h-5 text-white" onClick={handleSaveTermsOfService} />
                        </IconContainer>
                    )}
                </div>
            </CardContainer>
        </div>
    );
}

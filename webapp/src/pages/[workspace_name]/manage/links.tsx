import { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import { toast } from 'react-toastify';

import BetterInput from '@app/components/Common/input';
import ManageWorkspaceLayout from '@app/components/layout/manage-workspace';
import SettingsCard from '@app/components/settings/card';
import Button from '@app/components/ui/button';
import { buttonConstant } from '@app/constants/locales/buttons';
import { localesGlobal } from '@app/constants/locales/global';
import { placeHolder } from '@app/constants/locales/placeholder';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { useAppSelector } from '@app/store/hooks';
import { usePatchWorkspacePoliciesMutation } from '@app/store/workspaces/api';

export default function ManageLinks() {
    const [policies, setPolicies] = useState({ privacy_policy_url: '', terms_of_service_url: '' });
    const workspace = useAppSelector((state) => state.workspace);
    const [patchWorkspacePolicies, { isLoading }] = usePatchWorkspacePoliciesMutation();
    const { t } = useTranslation();

    const handleURLValidation = (str: string) => {
        if (!str) return false;
        const testRegex = /(^(https:\/\/www\.|https:\/\/)?[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?$)/;
        return testRegex.test(str);
    };

    useEffect(() => {
        const domain = 'https://bettercollected.com';
        const privacyPolicyUrl = workspace.privacy_policy_url || ``;
        const termsAndConditionsUrl = workspace.terms_of_service_url || ``;
        setPolicies({ privacy_policy_url: privacyPolicyUrl, terms_of_service_url: termsAndConditionsUrl });
    }, []);

    const handleSubmit = async (e: any) => {
        e.preventDefault();
        const formData = new FormData();
        if (workspace.privacy_policy_url !== policies.privacy_policy_url) formData.append('privacy_policy_url', policies.privacy_policy_url);
        if (workspace.terms_of_service_url !== policies.terms_of_service_url) formData.append('terms_of_service_url', policies.terms_of_service_url);

        const response: any = await patchWorkspacePolicies({ workspace_id: workspace.id, body: formData });
        if (response?.data) {
            toast(t(toastMessage.updated).toString(), { type: 'success', toastId: ToastId.SUCCESS_TOAST });
        } else if (response.error) {
            toast(t(toastMessage.somethingWentWrong).toString(), { type: 'error', toastId: ToastId.ERROR_TOAST });
        }
    };

    const handleChange = (e: any) => {
        setPolicies({ ...policies, [e.target.name]: e.target.value });
    };
    const saveButtonDisabled = () => {
        return !handleURLValidation(policies.privacy_policy_url) || !handleURLValidation(policies.terms_of_service_url);
    };

    return (
        <ManageWorkspaceLayout>
            <SettingsCard>
                <form onSubmit={handleSubmit}>
                    <div className="body1">{t(localesGlobal.linkToPrivacyPolicy)}</div>
                    <div>
                        <BetterInput value={policies.privacy_policy_url} onChange={handleChange} name="privacy_policy_url" error={!handleURLValidation(policies.privacy_policy_url)} placeholder={t(placeHolder.privacyPolicyLink)} />
                    </div>
                    <div className="body1">{t(localesGlobal.linkToTermsOfServices)}</div>
                    <div>
                        <BetterInput onChange={handleChange} value={policies.terms_of_service_url} name="terms_of_service_url" error={!handleURLValidation(policies.terms_of_service_url)} placeholder={t(placeHolder.termsOfServicesLink)} />
                    </div>
                    <div>
                        <Button disabled={saveButtonDisabled()} size="small">
                            {t(buttonConstant.save)}
                        </Button>
                    </div>
                </form>
            </SettingsCard>
        </ManageWorkspaceLayout>
    );
}

export { getServerSidePropsForWorkspaceAdmin as getServerSideProps } from '@app/lib/serverSideProps';

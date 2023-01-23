import { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import TextField from '@mui/material/TextField';
import { toast } from 'react-toastify';

import Button from '@app/components/ui/button';
import environments from '@app/configs/environments';
import { ToastId } from '@app/constants/toastId';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchWorkspacePoliciesMutation } from '@app/store/workspaces/api';

export default function Settingsprivacy() {
    const [policies, setPolicies] = useState({ privacy_policy_url: '', terms_of_service_url: '' });

    const workspace = useAppSelector((state) => state.workspace);

    const [patchWorkspacePolicies, { isLoading }] = usePatchWorkspacePoliciesMutation();

    const dispatch = useAppDispatch();

    const router = useRouter();

    useEffect(() => {
        const domain = 'https://bettercollected.com';
        const privacyPolicyUrl = workspace.privacy_profile_url ? workspace.privacy_profile_url : `${domain}${environments.PRIVACY_POLICY}`;
        const termsAndConditionsUrl = workspace.terms_of_service_url ? workspace.terms_of_service_url : `${domain}${environments.TERMS_AND_CONDITIONS}`;
        setPolicies({ privacy_policy_url: privacyPolicyUrl, terms_of_service_url: termsAndConditionsUrl });
    }, []);

    const handleEmailValidation = (str: string) => {
        if (!str) return;
        const testRegex = /(^(https:\/\/www\.|https:\/\/)?[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?$)/;
        const result = testRegex.test(str);
        return result;
    };

    const handleChange = (e: any) => {
        setPolicies({ ...policies, [e.target.name]: e.target.value });
    };

    const handleSubmit = async () => {
        if (!policies.privacy_policy_url && !policies.terms_of_service_url) return;
        const formData = new FormData();
        Object.keys(policies).forEach((key) => {
            if (workspace[key] !== policies[key] && !!policies[key]) formData.append(key, policies[key]);
        });

        try {
            await patchWorkspacePolicies({ workspace_id: workspace.id, body: formData });
            router.push(router.asPath, undefined);
            toast('Policies updated!!!', { type: 'success', toastId: ToastId.SUCCESS_TOAST });
        } catch (e) {
            toast('Something went wrong.', { type: 'error', toastId: ToastId.ERROR_TOAST });
        }
    };

    return (
        <div className="lg:w-2/3 mb-10">
            <div className="w-full lg:w-2/3">
                <div className="pb-6">
                    <h1 className="text-lg">Privacy policy</h1>
                    <div className="flex flex-col justify-between w-full">
                        <TextField
                            error={!handleEmailValidation(policies.privacy_policy_url)}
                            onChange={handleChange}
                            helperText={!handleEmailValidation(policies.privacy_policy_url) ? 'Invalid url' : ''}
                            size="medium"
                            value={policies.privacy_policy_url}
                            name="privacy_policy_url"
                            placeholder={`Enter url (e.g. ${environments.API_ENDPOINT_HOST}/legal/privacy-policy-2022.pdf )`}
                            className={`w-full`}
                        />
                    </div>
                </div>
                <div className="pb-6">
                    <h1 className="text-lg">Terms of services</h1>
                    <div className="flex flex-col justify-between w-full">
                        <TextField
                            error={!handleEmailValidation(policies.terms_of_service_url)}
                            onChange={handleChange}
                            value={policies.terms_of_service_url}
                            helperText={!handleEmailValidation(policies.terms_of_service_url) ? 'Invalid url' : ''}
                            size="medium"
                            name="terms_of_service_url"
                            placeholder={`Enter url (e.g. ${environments.API_ENDPOINT_HOST}/legal/terms-and-conditions-2022.pdf )`}
                            className={`w-full`}
                        />
                    </div>
                </div>
            </div>
            <Button isLoading={isLoading} type={'submit'} className="w-full md:w-auto !rounded-xl !bg-blue-600 h-[50px] mb-10" onClick={handleSubmit}>
                Update policies
            </Button>
        </div>
    );
}

import { toast } from 'react-toastify';

import environments from '@app/configs/environments';
import { ButtonSize } from '@app/models/enums/button';
import { Button } from '@app/shadcn/components/ui/button';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import useWorkspace from '@app/store/jotai/workspace';

export default function FormPublishedModal(props: any) {
    const { workspace } = useWorkspace();
    const { standardForm } = useStandardForm();
    return (
        <div>
            <div className="border-b border-b-black-300 p-4">Form Published</div>
            <div className="flex w-full flex-col items-center gap-6 px-5 py-6">
                <svg
                    width="76"
                    height="76"
                    viewBox="0 0 76 76"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                >
                    <circle cx="38" cy="38" r="38" fill="#D7FFF6" />
                    <rect x="14" y="14" width="48" height="48" rx="24" fill="#2DBB7F" />
                    <path
                        d="M31 39.8421L35.0137 43L45 33"
                        stroke="white"
                        stroke-width="2"
                        stroke-linecap="round"
                    />
                </svg>
                <div className="flex gap-2">
                    🎉
                    <span className="h3-new font-bold">
                        Your form has been published
                    </span>
                </div>
                <div className="flex items-center justify-between">
                    <div className="max-w-[360px] break-all rounded-md px-4 py-3 text-black-700">
                        https://forms.bettercollected.io/{workspace.workspaceName}
                        /forms/
                        <span className="text-pink-500">
                            {standardForm.settings?.customUrl}
                        </span>
                    </div>
                    <Button
                        variant={'secondary'}
                        onClick={() => {
                            navigator.clipboard.writeText(
                                `${environments.NEXT_PUBLIC_HTTP_SCHEME}://${environments.NEXT_PUBLIC_V2_CLIENT_ENDPOINT_DOMAIN}/${workspace.workspaceName}/forms/${standardForm.formId}`
                            );
                            toast('Copied!');
                        }}
                    >
                        Copy
                    </Button>
                </div>
                <div className="p2-new mt-5">
                    To customize your form link,{' '}
                    <a
                        href={`${environments.NEXT_PUBLIC_HTTP_SCHEME}://${environments.NEXT_PUBLIC_DASHBOARD_DOMAIN}/${workspace.workspaceName}/dashboard/forms/${standardForm.formId}?view=FormLinks`}
                        className="text-blue-500"
                    >
                        Go to form settings
                    </a>
                </div>
                <div className="mb-5 mt-5">
                    <a
                        href={`${environments.NEXT_PUBLIC_HTTP_SCHEME}://${environments.NEXT_PUBLIC_DASHBOARD_DOMAIN}/${workspace.workspaceName}/dashboard`}
                    >
                        <Button size={ButtonSize.Medium}>Go to dashboard</Button>
                    </a>
                </div>
            </div>
        </div>
    );
}

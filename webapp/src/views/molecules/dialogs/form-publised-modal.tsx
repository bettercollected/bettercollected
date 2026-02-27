"use client";
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { Button } from '@app/shadcn/components/ui/button';
import { selectAuth } from '@app/store/auth/slice';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import getFormShareURL from '@app/utils/form-utils';
import GreenCheckedCircle from '@Components/icons/green-checked-circle';

export default function FormPublishedModal(props: any) {
    const { toast } = useToast();
    const workspace = useAppSelector(selectWorkspace);

    const standardForm = useAppSelector(selectForm);
    const authState = useAppSelector(selectAuth);

    return (
        <div className="w-full">
            <div className="border-b-black-300 text-black-700 border-b p-4 text-xs">Form Published</div>
            <div className="flex w-full flex-col items-center gap-6 px-5 py-6">
                <GreenCheckedCircle />
                <div className="flex flex-col items-center gap-1">
                    <div className="flex items-center gap-2 text-[32px]">
                        🎉
                        <span className="h2-new font-bold">Your form has been published</span>
                    </div>
                    <span className="p4-new text-black-700">Anyone with the link can fill your form</span>
                </div>
                <div className="flex items-center  gap-2">
                    <div className="text-black-700 p4-new bg-black-100 rounded-md px-3 py-2">
                        {window.PUBLIC_CONFIG?.HTTP_SCHEME}
                        {window.PUBLIC_CONFIG?.FORM_DOMAIN}/{workspace.workspaceName}
                        /forms/
                        <span className="text-pink-500">{standardForm.settings?.customUrl}</span>
                    </div>
                    <Button
                        data-umami-event={'PublishModal Copy Button'}
                        data-umami-event-email={authState.email}
                        variant={'v2Button'}
                        onClick={() => {
                            navigator.clipboard.writeText(getFormShareURL(standardForm, workspace));
                            toast({ description: 'Copied!' });
                        }}
                    >
                        Copy
                    </Button>
                </div>
                <div className="p2-new mt-5 flex flex-col items-center gap-2 md:w-[250px]">
                    <span className="h5-new">What’s Next?</span>
                    <span className="p4-new break-words text-center">
                        Add your custom domain, add integration or change form privacy,{' '}
                        <button data-umami-event={'PublishModal Goto Settings Link'} data-umami-event-email={authState.email}>
                            <a href={`${window.PUBLIC_CONFIG?.HTTP_SCHEME}${window.PUBLIC_CONFIG?.DASHBOARD_DOMAIN}/${workspace.workspaceName}/dashboard/forms/${standardForm.formId}?view=FormLinks`} className="text-blue-500">
                                Go to form settings
                            </a>
                        </button>
                    </span>
                </div>
                <div className="mb-5 mt-5">
                    <button data-umami-event={'PublishModal Goto Dashboard Link'} data-umami-event-email={authState.email}>
                        <a href={`${window.PUBLIC_CONFIG?.HTTP_SCHEME}${window.PUBLIC_CONFIG?.DASHBOARD_DOMAIN}/${workspace.workspaceName}/dashboard/forms`}>
                            <Button size="medium">Done! Go to dashboard</Button>
                        </a>
                    </button>
                </div>
            </div>
        </div>
    );
}

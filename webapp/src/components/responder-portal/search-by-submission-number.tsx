"use client";
import { FormEvent, useState } from 'react';

import { useRouter } from 'next/navigation';

import InfoIcon from '@Components/icons/info.icon';

import { SearchIcon } from '@app/components/icons/search';
import { AppInput } from '@app/shadcn/components/ui/input';
import { useAppSelector } from '@app/store/hooks';
import { useLazyGetWorkspaceSubmissionByUUIDQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

const SearchBySubmissionNumber = ({ className }: { className?: string }) => {
    const workspace = useAppSelector(selectWorkspace);
    const [submissionNumber, setSubmissionNumber] = useState('');
    const [getSubmissionByUUID, { isLoading }] = useLazyGetWorkspaceSubmissionByUUIDQuery();
    const isCustomDomain = window?.location?.host !== window.PUBLIC_CONFIG?.FORM_DOMAIN;

    const [error, setError] = useState(false);

    const router = useRouter();

    const handleSubmit = async (event: FormEvent) => {
        event.preventDefault();
        if (!submissionNumber) return;
        const response = await getSubmissionByUUID({
            workspace_id: workspace.id,
            submissionUUID: submissionNumber
        });
        if (response.data) {
            const submissionUrl = isCustomDomain ? `/submissions/uuid/${submissionNumber}` : `/${workspace.workspaceName}/submissions/uuid/${submissionNumber}`;
            router.push(submissionUrl);
        }
        if (response.error) {
            setError(true);
        }
    };

    return (
        <form onSubmit={handleSubmit} className={className}>
            <div className="flex w-full max-w-[367px] flex-col items-center justify-center rounded-xl bg-white px-6 py-8 xl:w-[367px]">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#E9EFFC]" aria-hidden="true">
                    <SearchIcon className="text-[#2456CC]" width={22} height={22} strokeWidth={2} />
                </div>

                <div className="mt-4">
                    <div className="h4-new text-new-black-800 text-center font-medium">Find a response by its number</div>
                    <div className="p2-new text-black-700 mt-2 !text-center">Every submission gets a receipt number — enter it to view (or request deletion of) that response.</div>
                </div>
                <div className="mt-4 flex w-full gap-4">
                    <AppInput
                        required={true}
                        value={submissionNumber}
                        onChange={(event) => {
                            setError(false);
                            setSubmissionNumber(event.target.value);
                        }}
                        placeholder="Enter submission number"
                        aria-label="Submission number"
                        className="w-full flex-1"
                    />

                    <button type="submit" aria-label="Search" className="flex items-center justify-center rounded bg-[#2456CC] p-3 hover:bg-[#1E49AD]">
                        <SearchIcon className="text-white" width={16} height={16} strokeWidth={2} />
                    </button>
                </div>
                <div className="mt-2 text-xs text-[#C43D3D]">
                    {error && (
                        <div className="flex gap-2">
                            {' '}
                            <span>
                                <InfoIcon className="text-[#C43D3D]" width={16} height={16} />
                            </span>
                            The submission number does not match with any form responses
                        </div>
                    )}
                </div>
            </div>
        </form>
    );
};

export default SearchBySubmissionNumber;

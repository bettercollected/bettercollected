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
            const submissionUrl = isCustomDomain ? `/submissions/uuid/${submissionNumber}/form` : `/${workspace.workspaceName}/submissions/uuid/${submissionNumber}/form`;
            router.push(submissionUrl);
        }
        if (response.error) {
            setError(true);
        }
    };

    return (
        <form onSubmit={handleSubmit} className={className}>
            {/* Fluid width — the parent column (sidebar) decides how wide. */}
            <div className="flex w-full flex-col items-center justify-center rounded bg-white px-6 py-8">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-100" aria-hidden="true">
                    <SearchIcon className="text-brand-500" width={22} height={22} strokeWidth={2} />
                </div>

                <div className="mt-4">
                    <div className="h4-new text-black-800 text-center font-medium">Find a response by its number</div>
                    <div className="p2-new text-black-700 mt-2 text-center!">Every submission gets a receipt number — enter it to view (or request deletion of) that response.</div>
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

                    <button type="submit" aria-label="Search" className="flex items-center justify-center rounded bg-action p-3 hover:bg-action-hover active:bg-action-pressed key-edge [--key-edge:var(--color-action-pressed)]">
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

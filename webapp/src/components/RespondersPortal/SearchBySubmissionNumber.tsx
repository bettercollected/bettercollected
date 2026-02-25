"use client";
import { FormEvent, useState } from 'react';

import Image from 'next/legacy/image';
import { useRouter } from 'next/navigation';

import InfoIcon from '@Components/Common/Icons/FormBuilder/infoIcon';

import { SearchIcon } from '@app/Components/icons/search';
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
                <Image src={'/images/search_submission.png'} alt="Seacch by sub number" height={62} width={77} />

                <div className="mt-4">
                    <div className="h4-new text-new-black-800 text-center font-medium">Search by submission number</div>
                    <div className="p2-new text-black-700 mt-2 !text-center">Enter your submission number to see your form response.</div>
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
                        className="w-full flex-1"
                    />

                    <button type="submit" className=" active:bg-black-300 bg-black-200 flex items-center justify-center rounded p-3">
                        <SearchIcon className="text-black-700" width={16} height={16} strokeWidth={2} />
                    </button>
                </div>
                <div className="mt-2 text-xs text-red-500">
                    {error && (
                        <div className="flex gap-2">
                            {' '}
                            <span>
                                <InfoIcon className="text-red-500" width={16} height={16} />
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

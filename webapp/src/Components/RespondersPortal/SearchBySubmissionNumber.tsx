import React, { FormEvent, useState } from 'react';

import Image from "next/legacy/image";
import { useRouter } from 'next/router';

import InfoIcon from '@Components/Common/Icons/FormBuilder/infoIcon';
import AppTextField from '@Components/Common/Input/AppTextField';

import { SearchIcon } from '@app/Components/icons/search';
import environments from '@app/configs/environments';
import { useAppSelector } from '@app/store/hooks';
import { useLazyGetWorkspaceSubmissionByUUIDQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

const SearchBySubmissionNumber = ({ className }: { className?: string }) => {
    const workspace = useAppSelector(selectWorkspace);
    const [submissionNumber, setSubmissionNumber] = useState('');
    const [getSubmissionByUUID, { isLoading }] = useLazyGetWorkspaceSubmissionByUUIDQuery();
    const isCustomDomain = window?.location?.host !== environments.CLIENT_DOMAIN;

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
            <div className="w-full flex flex-col items-center justify-center max-w-[367px] xl:w-[367px] px-6 py-8 bg-white rounded-xl">
                <Image src={'/images/search_submission.png'} alt="Seacch by sub number" height={62} width={77} />

                <div className="mt-4">
                    <div className="h4-new font-medium text-center text-new-black-800">Search by submission number</div>
                    <div className="p2-new mt-2 !text-center text-black-700">Enter your submission number to see your form response.</div>
                </div>
                <div className="flex gap-4 mt-4 w-full">
                    <AppTextField
                        required={true}
                        isError={error}
                        value={submissionNumber}
                        onChange={(event) => {
                            setError(false);
                            setSubmissionNumber(event.target.value);
                        }}
                        placeholder="Enter submission number"
                        className="w-full"
                    />

                    <button type="submit" className=" rounded p-3 flex items-center justify-center active:bg-black-300 bg-black-200">
                        <SearchIcon className="text-black-700" width={24} height={24} strokeWidth={2} />
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

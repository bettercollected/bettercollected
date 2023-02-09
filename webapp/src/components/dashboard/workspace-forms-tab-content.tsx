import React, { useEffect, useMemo, useState } from 'react';

import { debounce, escapeRegExp } from 'lodash';

import styled from '@emotion/styled';
import { IconButton, InputAdornment } from '@mui/material';
import TextField from '@mui/material/TextField';

import EmptyTray from '@app/assets/svgs/empty-tray.svg';
import FormCards from '@app/components/dashboard/form-cards';
import { SearchIcon } from '@app/components/icons/search';
import Image from '@app/components/ui/image';
import Loader from '@app/components/ui/loader';
import { StandardFormDto } from '@app/models/dtos/form';
import { useGetWorkspaceFormsQuery, useSearchWorkspaceFormsMutation } from '@app/store/workspaces/api';

interface IFormCard {
    workspaceId: string;
}

const StyledTextField = styled.div`
    .MuiFormControl-root {
        background: white;
        border-radius: 14px;
        outline: none;
    }

    .MuiOutlinedInput-notchedOutline {
        border-radius: 14px;
        border-width: 0.5px;
    }

    @media screen and (max-width: 640px) {
        .MuiFormControl-root {
            width: 100%;
        }
    }
`;

export default function WorkspaceFormsTabContent({ workspace }: any) {
    const workspaceId = workspace.id;
    const query = {
        workspace_id: workspaceId
    };
    const { isLoading, data, isError } = useGetWorkspaceFormsQuery(query, { pollingInterval: 30000 });
    const [searchWorkspaceForms] = useSearchWorkspaceFormsMutation();
    const [pinnedForms, setPinnedForms] = useState<any>([]);
    const [unpinnedForms, setUnpinnedForms] = useState<any>([]);
    const [showUnpinnedForms, setShowUnpinnedForms] = useState(false);

    useEffect(() => {
        if (!!data) {
            const pinnedForms = data.payload.content.filter((form) => form.settings.pinned);
            const unpinnedForms = data.payload.content.filter((form) => !form.settings.pinned);
            setPinnedForms(pinnedForms);
            setUnpinnedForms(unpinnedForms);
            setShowUnpinnedForms(unpinnedForms.length > 0);
        }
    }, [data]);

    const handleSearch = async (event: any) => {
        const response: any = await searchWorkspaceForms({
            workspace_id: workspaceId,
            query: escapeRegExp(event.target.value)
        });
        if (event.target.value) {
            setUnpinnedForms(response?.data?.payload?.content);
        } else {
            setUnpinnedForms(response?.data?.payload?.content.filter((form: any) => !form.settings.pinned) || []);
        }
    };
    const debouncedResults = useMemo(() => {
        return debounce(handleSearch, 500);
    }, []);

    useEffect(() => {
        debouncedResults.cancel();
    }, []);

    if (isLoading)
        return (
            <div className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                <Loader />
            </div>
        );

    if ((data?.payload?.content && Array.isArray(data?.payload?.content) && data?.payload?.content?.length === 0) || isError)
        return (
            <div className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                <Image src={EmptyTray} width={40} height={40} alt="Empty Tray" />
                <p className="mt-4 p-0">0 forms</p>
            </div>
        );

    const forms: Array<StandardFormDto> = data?.payload?.content ?? [];

    return (
        <>
            {forms.length === 0 && (
                <div className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                    <Image src={EmptyTray} width={40} height={40} alt="Empty Tray" />
                    <p className="mt-4 p-0">0 forms</p>
                </div>
            )}
            {pinnedForms.length !== 0 && <FormCards title="Pinned Forms" workspace={workspace} formsArray={pinnedForms} />}
            {showUnpinnedForms && (
                <>
                    {pinnedForms.length !== 0 && <hr className="mb-6" />}
                    {pinnedForms.length !== 0 && <h1 className=" text-gray-700 font-semibold text-md md:text-lg mb-4">All Forms</h1>}
                    <div className={`w-full md:w-[30%] ${!pinnedForms ? 'mt-6' : 'mt-0'} mb-6`}>
                        <StyledTextField>
                            <TextField
                                size="small"
                                name="search-input"
                                placeholder="Search forms..."
                                onChange={debouncedResults}
                                className={'w-full'}
                                InputProps={{
                                    endAdornment: (
                                        <InputAdornment position="end">
                                            <IconButton>
                                                <SearchIcon />
                                            </IconButton>
                                        </InputAdornment>
                                    )
                                }}
                            />
                        </StyledTextField>
                    </div>
                </>
            )}
            {unpinnedForms.length !== 0 && <FormCards title="" formsArray={unpinnedForms} workspace={workspace} />}
        </>
    );
}

import React, { useEffect, useMemo, useState } from 'react';

import { debounce, escapeRegExp } from 'lodash';

import styled from '@emotion/styled';
import { IconButton, InputAdornment } from '@mui/material';
import TextField from '@mui/material/TextField';

import EmptyFormsView from '@app/components/dashboard/empty-form';
import FormCards from '@app/components/dashboard/form-cards';
import { SearchIcon } from '@app/components/icons/search';
import Loader from '@app/components/ui/loader';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetWorkspaceFormsQuery, useSearchWorkspaceFormsMutation } from '@app/store/workspaces/api';

interface IWorkspaceFormsTabContentProps {
    workspace: WorkspaceDto;
    isFormCreator?: boolean;
}

const StyledTextField = styled.div`
    .MuiFormControl-root {
        background: white;
        border-radius: 4px;
        outline: none;
    }

    .MuiOutlinedInput-notchedOutline {
        border-radius: 4px;
        border-width: 0.5px;
    }

    @media screen and (max-width: 640px) {
        .MuiFormControl-root {
            width: 100%;
        }
    }
`;

export default function WorkspaceFormsTabContent({ workspace, isFormCreator = false }: IWorkspaceFormsTabContentProps) {
    const workspaceId = workspace.id;
    const query = {
        workspace_id: workspaceId
    };
    const { isLoading, data, isError } = useGetWorkspaceFormsQuery(query, { pollingInterval: 30000 });
    const [searchWorkspaceForms] = useSearchWorkspaceFormsMutation();
    const [pinnedForms, setPinnedForms] = useState<any>([]);
    const [unpinnedForms, setUnpinnedForms] = useState<any>([]);
    const [showUnpinnedForms, setShowUnpinnedForms] = useState(false);

    const handleSearch = async (event: any) => {
        const response: any = await searchWorkspaceForms({
            workspace_id: workspaceId,
            query: escapeRegExp(event.target.value)
        });
        if (event.target.value) {
            setUnpinnedForms(response?.data);
        } else {
            setUnpinnedForms(response?.data.filter((form: any) => !form.settings.pinned) || []);
        }
    };
    const debouncedResults = useMemo(() => {
        return debounce(handleSearch, 500);
    }, []);

    useEffect(() => {
        debouncedResults.cancel();
    }, []);

    useEffect(() => {
        if (!!data) {
            const pinnedForms = data.items.filter((form) => form.settings?.pinned);
            const unpinnedForms = data.items.filter((form) => !form.settings?.pinned);
            setPinnedForms(pinnedForms);
            setUnpinnedForms(unpinnedForms);
            setShowUnpinnedForms(unpinnedForms.length > 0);
        }
    }, [data]);

    if (isLoading)
        return (
            <div data-testid="loader" className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                <Loader />
            </div>
        );
    const forms: Array<StandardFormDto> = data?.items ?? [];

    if ((data && Array.isArray(data) && data.length === 0) || isError || forms.length === 0) return <EmptyFormsView />;

    return (
        <div className="py-6 px-5 lg:px-10 xl:px-20 flex flex-col gap-6">
            {pinnedForms.length !== 0 && <FormCards title="Pinned Forms" isFormCreator={isFormCreator} workspace={workspace} formsArray={pinnedForms} />}
            {showUnpinnedForms && (
                <>
                    {pinnedForms.length !== 0 && <hr />}
                    {pinnedForms.length !== 0 && <h1 className=" text-gray-700 font-semibold text-md md:text-lg">All Forms</h1>}
                    <div className={`w-full md:w-[30%]`}>
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
            {unpinnedForms.length !== 0 && <FormCards title="" isFormCreator={isFormCreator} formsArray={unpinnedForms} workspace={workspace} />}
        </div>
    );
}

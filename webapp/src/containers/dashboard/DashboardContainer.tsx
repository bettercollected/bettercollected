import React, { useMemo } from 'react';

import styled from '@emotion/styled';
import { IconButton, InputAdornment } from '@mui/material';
import TextField from '@mui/material/TextField';
import { useDispatch } from 'react-redux';

import { SearchIcon } from '@app/components/icons/search';
import SubmissionTabContainer from '@app/components/submissions-tab/submissions-tab-container';
import PublicWorkspaceLayout from '@app/layouts/_public-workspace-layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { authApi } from '@app/store/auth/api';
import { useAppSelector } from '@app/store/hooks';
import { setSearchInput } from '@app/store/search/searchSlice';

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

interface IDashboardContainer {
    workspace: WorkspaceDto;
}

export default function DashboardContainer({ workspace }: IDashboardContainer) {
    const statusQuerySelect = useMemo(() => authApi.endpoints.getStatus.select('status'), []);
    const selectGetStatus = useAppSelector(statusQuerySelect);
    const dispatch = useDispatch();

    const searchText = useAppSelector((state) => state.search.searchInput);

    const handleSearch = (event: any) => {
        dispatch(setSearchInput(event.target.value.toLowerCase()));
    };

    return (
        <PublicWorkspaceLayout workspace={workspace}>
            <div className="w-full md:flex md:justify-end">
                <StyledTextField>
                    <TextField
                        size="small"
                        name="search-input"
                        placeholder="Search forms..."
                        value={searchText}
                        onChange={handleSearch}
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
            <SubmissionTabContainer workspaceId={workspace.id} showResponseBar={!!selectGetStatus.error} />
        </PublicWorkspaceLayout>
    );
}

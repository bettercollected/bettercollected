import React, { useEffect, useMemo, useState } from 'react';

import { useTranslation } from 'next-i18next';

import { debounce, escapeRegExp } from 'lodash';

import Divider from '@Components/Common/DataDisplay/Divider';
import ZeroElement from '@Components/Common/DataDisplay/Empty/ZeroElement';
import SearchInput from '@Components/Common/Search/SearchInput';
import styled from '@emotion/styled';
import { InputAdornment } from '@mui/material';
import TextField from '@mui/material/TextField';

import FormCards from '@app/components/dashboard/form-cards';
import { SearchIcon } from '@app/components/icons/search';
import Loader from '@app/components/ui/loader';
import { formConstant } from '@app/constants/locales/form';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetWorkspaceFormsQuery, useSearchWorkspaceFormsMutation } from '@app/store/workspaces/api';

interface IWorkspaceFormsTabContentProps {
    workspace: WorkspaceDto;
    isFormCreator?: boolean;
}

export const StyledTextField = styled.div`
    .MuiFormControl-root {
        background: white;
        border-radius: 4px;
        outline: none;
    }

    .MuiOutlinedInput-notchedOutline {
        border-radius: 4px;
        border: 1px solid #ced4da;
    }

    .MuiInputBase-input,
    .MuiOutlinedInput-root {
        height: 46px;
    }

    .MuiInputBase-input,
    .MuiOutlinedInput-input,
    .MuiInputBase-inputSizeSmall,
    .MuiInputBase-inputAdornedEnd {
        padding: 0;
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
    const { t } = useTranslation();

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

    if ((data && Array.isArray(data) && data.length === 0) || isError || forms.length === 0) return <ZeroElement title={t(workspaceConstant.preview.emptyFormTitle)} description={t(workspaceConstant.preview.emptyFormDescription)} className="!pb-[20px]" />;

    return (
        <div className="py-6 px-5 lg:px-10 xl:px-20 flex flex-col gap-6">
            <div className={`w-full md:w-[282px]`}>
                <SearchInput handleSearch={handleSearch} />
            </div>
            {pinnedForms.length !== 0 && <FormCards title={t(formConstant.pinnedforms)} isFormCreator={isFormCreator} workspace={workspace} formsArray={pinnedForms} />}
            {showUnpinnedForms && pinnedForms.length !== 0 && <Divider />}
            {unpinnedForms.length !== 0 && <FormCards title={pinnedForms.length !== 0 ? t(formConstant.all) : ''} isFormCreator={isFormCreator} formsArray={unpinnedForms} workspace={workspace} />}
        </div>
    );
}

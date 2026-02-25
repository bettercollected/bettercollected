import { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import { escapeRegExp } from 'lodash';

import Divider from '@Components/Common/divider';
import SearchInput from '@Components/Common/search-input';
import ZeroElement from '@Components/Common/zero-elament';

import FormCards from '@app/components/dashboard/form-cards';
import Loader from '@app/components/ui/loader';
import { formConstant } from '@app/constants/locales/form';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useGetWorkspaceFormsQuery, useLazySearchWorkspaceFormsQuery } from '@app/store/workspaces/api';

interface IWorkspaceFormsTabContentProps {
    workspace: WorkspaceDto;
    isFormCreator?: boolean;
}

export default function WorkspaceFormsTabContent({ workspace, isFormCreator = false }: IWorkspaceFormsTabContentProps) {
    const workspaceId = workspace.id;
    const query = {
        workspace_id: workspaceId,
        published: true
    };
    const { isLoading, data, isError } = useGetWorkspaceFormsQuery(query, { pollingInterval: 30000 });

    const pinnedFormsQuery = {
        workspace_id: workspaceId,
        published: true,
        pinned_only: true
    };

    const pinnedFormsResponse = useGetWorkspaceFormsQuery(pinnedFormsQuery);
    const pinnedForms = pinnedFormsResponse?.data;

    const [searchWorkspaceForms] = useLazySearchWorkspaceFormsQuery();
    const [allForms, setAllForms] = useState<any>([]);
    const { t } = useTranslation();

    const handleSearch = async (event: any) => {
        const response: any = await searchWorkspaceForms({
            workspace_id: workspaceId,
            query: escapeRegExp(event.target.value),
            published: true
        });

        if (event.target.value && response.data) {
            setAllForms(response?.data);
        } else {
            setAllForms(data?.items || []);
        }
    };

    useEffect(() => {
        if (!!data) {
            setTimeout(() => {
                setAllForms(data.items);
            }, 0);
        }
    }, [data]);

    if (isLoading)
        return (
            <div data-testid="loader" className="text-darkGrey flex min-h-[30vh] w-full flex-col items-center justify-center">
                <Loader />
            </div>
        );
    const forms: Array<StandardFormDto> = data?.items ?? [];

    if ((data && Array.isArray(data) && data.length === 0) || isError || forms.length === 0)
        return (
            // <SearchByUUIDWrapper>
            <ZeroElement title={t(workspaceConstant.preview.emptyFormTitle)} description={t(workspaceConstant.preview.emptyFormDescription)} className="!pb-[20px]" />
            // </SearchByUUIDWrapper>
        );

    return (
        // <SearchByUUIDWrapper>
        <div className="flex w-full flex-col gap-6">
            {pinnedForms?.items?.length !== 0 && <FormCards title={t(formConstant.pinnedforms)} showPinned={false} isFormCreator={isFormCreator} showVisibility={false} workspace={workspace} formsArray={pinnedForms?.items || []} />}
            {pinnedForms?.items?.length !== 0 && <Divider />}
            <div className={`w-full md:w-[282px]`}>
                <SearchInput handleSearch={handleSearch} />
            </div>
            {allForms.length !== 0 && <FormCards title={pinnedForms?.items?.length !== 0 ? t(formConstant.all) : ''} isFormCreator={isFormCreator} formsArray={allForms} workspace={workspace} />}
        </div>
        // </SearchByUUIDWrapper>
    );
}

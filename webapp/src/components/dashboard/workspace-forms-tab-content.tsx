import { useEffect, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { escapeRegExp } from 'lodash';

import Divider from '@Components/common/divider';
import SearchInput from '@Components/common/search-input';
import ZeroElement from '@Components/common/zero-elament';

import FormCards from '@app/components/dashboard/form-cards';
import Loader from '@app/components/ui/loader';
import { formConstant } from '@app/constants/locales/form';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { usePortalText } from '@app/lib/hooks/use-respondent-language';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { useGetWorkspaceFormsQuery, useLazySearchWorkspaceFormsQuery } from '@app/store/workspaces/api';

interface IWorkspaceFormsTabContentProps {
    workspace: WorkspaceDto;
    isFormCreator?: boolean;
    /** Set when rendered outside the public portal (the admin dashboard's
     *  Public Workspace preview) so form links point at the real portal. */
    publicBaseUrl?: string;
    /** The form search is in the respondent's language on the portal, in the
     *  app's on the team's dashboard (`team`). */
    audience?: 'respondent' | 'team';
}

export default function WorkspaceFormsTabContent({ workspace, isFormCreator = false, publicBaseUrl, audience = 'respondent' }: IWorkspaceFormsTabContentProps) {
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
    const searchText = usePortalText(audience);
    const searchLanguage = searchText.language;

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
            <div lang={searchLanguage}>
                <ZeroElement
                    title={audience === 'team' ? t(workspaceConstant.preview.emptyFormTitle) : searchText.t('PORTAL.NO_FORMS_TITLE')}
                    description={audience === 'team' ? t(workspaceConstant.preview.emptyFormDescription) : searchText.t('PORTAL.NO_FORMS_TEXT')}
                    className="pb-[20px]!"
                    headingLevel={2}
                />
            </div>
            // </SearchByUUIDWrapper>
        );

    return (
        // <SearchByUUIDWrapper>
        <div className="flex w-full flex-col gap-6">
            {pinnedForms?.items?.length !== 0 && <FormCards title={audience === 'team' ? t(formConstant.pinnedforms) : searchText.t('PORTAL.PINNED_FORMS')} showPinned={false} isFormCreator={isFormCreator} showVisibility={false} workspace={workspace} formsArray={pinnedForms?.items || []} publicBaseUrl={publicBaseUrl} audience={audience} />}
            {pinnedForms?.items?.length !== 0 && <Divider />}
            <div className={`w-full md:w-[282px]`} lang={searchLanguage}>
                <SearchInput placeholder={searchText.t('PORTAL.SEARCH_FORMS')} handleSearch={handleSearch} />
            </div>
            {/* Without pinned forms the list's heading is for screen readers only. */}
            {allForms.length !== 0 && <FormCards title={audience === 'team' ? t(formConstant.all) : searchText.t('PORTAL.ALL_FORMS')} hideTitle={pinnedForms?.items?.length === 0} isFormCreator={isFormCreator} formsArray={allForms} workspace={workspace} publicBaseUrl={publicBaseUrl} audience={audience} />}
        </div>
        // </SearchByUUIDWrapper>
    );
}

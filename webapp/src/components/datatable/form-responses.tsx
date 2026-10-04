import { useEffect, useState } from 'react';


import SearchInput from '@Components/common/search-input';
import TabularResponses from '@Components/form/tabular-responses';

import Loader from '@app/components/ui/loader';
import globalConstants from '@app/constants/global';
import { Button } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetFormsSubmissionsQuery, useLazyGetFormAllSubmissionsQuery } from '@app/store/workspaces/api';
import { IGetFormSubmissionsQuery } from '@app/store/workspaces/types';
import EmptyResponseIcon from '@Components/icons/expty-response-icon';
import { DownloadIcon } from 'lucide-react';
import ResponsesTable from './responses-table';
//@ts-ignore
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { selectAuth } from '@app/store/auth/slice';
import { buildResponsesExport, exportFileName, tableToCsv } from '@app/utils/response-export';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';

function downloadCsv(csv: string, fileName: string) {
    // BOM so spreadsheet apps read UTF-8 names correctly.
    const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function FormResponsesTable({ props }: any) {
    const form = useAppSelector(selectForm);
    const auth = useAppSelector(selectAuth);

    const { workspace, requestForDeletion, isSubmission = false } = props;
    const [page, setPage] = useState(1);
    const [query, setQuery] = useState<IGetFormSubmissionsQuery>({
        formId: form.formId,
        workspaceId: workspace?.id,
        requestedForDeletionOly: requestForDeletion,
        page: page,
        size: globalConstants.pageSize
    });
    useEffect(() => {
        setTimeout(() => {
            setQuery({ ...query, page });
        }, 0);
    }, [page]);

    const { data, isLoading } = useGetFormsSubmissionsQuery(query);
    const { can } = useWorkspacePermissions();
    const canExport = can(WorkspacePermission.RESPONSE_EXPORT);
    const [trigger, { isLoading: csvLoading }] = useLazyGetFormAllSubmissionsQuery();

    const handleSearch = (event: any) => {
        if (event.target.value) setQuery({ ...query, dataOwnerIdentifier: event.target.value });
        else {
            const { dataOwnerIdentifier, ...removedQuery } = query;
            setQuery(removedQuery);
        }
    };

    const handleClickExportCSV = () => {
        trigger({ formId: form.formId, workspaceId: workspace?.id }).then((result) => {
            // never a header-only file for a refused export
            if (result.isError) return;
            // One row per submission; repeating groups become columns per item,
            // or (large groups) a CSV of their own with one row per item.
            const { main, groupTables } = buildResponsesExport(form, (result.data ?? []) as Array<StandardFormResponseDto>);
            // Every file goes through tableToCsv, which neutralises formula-like cells.
            downloadCsv(tableToCsv(main), exportFileName(form.title));
            groupTables.forEach((table) => downloadCsv(tableToCsv(table), exportFileName(form.title, table.name)));
        });
    };

    if (isLoading)
        return (
            <div className=" flex w-full justify-center py-10">
                <Loader />
            </div>
        );

    return (
        <div>
            <div className={`mb-6 flex flex-col gap-2 lg:flex-row lg:justify-between`}>
                <div className="flex w-full flex-row justify-between">
                    {(isSubmission && form.responses) || (!isSubmission && form.deletionRequests) ? (
                        <div className="flex w-full flex-row items-center gap-4 ">
                            <SearchInput handleSearch={handleSearch} placeholder={'Search responses'} className="md:w-[282px]" />
                        </div>
                    ) : (
                        <></>
                    )}
                    {isSubmission && canExport && (
                        <Button data-umami-event="Export CSV Button" data-umami-event-email={auth.email} isLoading={csvLoading} variant="v2Button" icon={<DownloadIcon className="h-4 w-4" />} onClick={handleClickExportCSV} className={''}>
                            Export CSV
                        </Button>
                    )}
                </div>
            </div>
            {data && Array.isArray(data.items) && data.items.length ? (
                <>{data && requestForDeletion ? <ResponsesTable formId={form.formId} requestForDeletion={requestForDeletion} page={page} setPage={setPage} submissions={data} /> : <TabularResponses form={form} />}</>
            ) : (
                <EmptyTabularResponseComponent requestForDeletion={requestForDeletion} />
            )}
        </div>
    );
}

const EmptyTabularResponseComponent = ({ requestForDeletion }: { requestForDeletion?: boolean }) => {
    // Deletion requests are a GDPR feature — the empty state should teach that,
    // not borrow the responses copy (which can be factually wrong here).
    if (requestForDeletion) {
        return (
            <div className={'flex flex-col items-center gap-2 py-10'}>
                <EmptyResponseIcon />
                <span className={'p3-new text-black'}>No deletion requests</span>
                <span className={'p4-new text-black-600 max-w-[420px] text-center'}>When a responder asks for their response to be deleted, it shows up here for you to act on.</span>
            </div>
        );
    }
    return (
        <div className={'flex flex-col items-center gap-2 py-10'}>
            <EmptyResponseIcon />
            <span className={'p3-new text-black'}>No responses yet</span>
            <span className={'p4-new text-black-600'}>Responses appear here as soon as someone fills out your form.</span>
        </div>
    );
};

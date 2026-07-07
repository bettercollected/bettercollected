"use client";

import { useTranslation } from 'next-i18next';

import StyledPagination from '@Components/common/pagination';
import { cn } from '@app/shadcn/util/lib';
import DataTable from 'react-data-table-component';

import { dataTableCustomStyles } from '@Components/datatable/datatable-styles';
import StatusBadge from '@app/components/badge/status-badge';
import { ChevronForward } from '@app/components/icons/chevron-forward';
import EmptyResponse from '@app/components/ui/empty-response';
import AnchorLink from '@app/components/ui/links/anchor-link';
import globalConstants from '@app/constants/global';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { Page } from '@app/models/dtos/page';
import { Button } from '@app/shadcn/components/ui/button';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { utcToLocalDateTIme } from '@app/utils/date-utils';

const responseTableStyles = {
    ...dataTableCustomStyles,
    rows: {
        style: {
            ...dataTableCustomStyles.rows.style,
            borderColor: '#E2E8F2 !important',
            '&:hover': {
                cursor: 'pointer',
                background: '#F6F8FC'
            }
        }
    }
};

interface IResponsetableProps {
    requestForDeletion: boolean;
    submissions: Page<StandardFormResponseDto>;
    formId?: string;
    page: number;
    setPage: (page: number) => void;
}

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { useLazyGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { getFormFields } from '@app/utils/form-builder-block-utils';

const ResponsesTable = ({ requestForDeletion, submissions, formId, page, setPage }: IResponsetableProps) => {
    const { openModal } = useFullScreenModal();
    const { openModal: openConfirmModal } = useModal();
    const [triggerSingleResponse] = useLazyGetWorkspaceSubmissionQuery();

    const user = useAppSelector(selectAuth);
    const workspace = useAppSelector(selectWorkspace);
    const googleFormHostUrl = 'https://docs.google.com/';
    const typeFormHostUrl = 'https://admin.typeform.com/';
    const handlePageChange = (e: any, page: number) => {
        setPage(page);
    };
    const { t } = useTranslation();
    const onRowClicked = (response: StandardFormResponseDto) => {
        if (!requestForDeletion) {
            triggerSingleResponse({
                workspace_id: workspace?.id ?? '',
                submission_id: response.responseId
            }).then((result: any) => {
                openModal('VIEW_RESPONSE', { response: result.data.response, formFields: getFormFields(result.data.form), form: result.data.form, formId: result.data.form.formId, workspaceId: workspace.id });
            });
        }
    };
    const responseDataOwnerField = (response: StandardFormResponseDto) => (
        <div aria-hidden className="w-fit">
            <div className={cn('!text-black-900 body3 truncate', !requestForDeletion && 'hover:!text-brand-500 cursor-pointer hover:underline')}>
                {!requestForDeletion && <span onClick={() => onRowClicked(response)}>{response?.dataOwnerIdentifier ?? 'Anonymous'}</span>}
                {requestForDeletion && (response?.dataOwnerIdentifier ?? 'Anonymous')}
            </div>
            {/* The receipt number is the only handle a responder (especially an
                anonymous one) has on their submission — showing it lets the
                owner match a request against what the responder quotes. The
                cell is too narrow for all 36 chars; the title carries the rest. */}
            {requestForDeletion && response?.submissionUuid && (
                <div title={response.submissionUuid} className="text-black-600 mt-0.5 font-mono text-[11px]">
                    #{response.submissionUuid.split('-')[0]}…
                </div>
            )}
        </div>
    );
    const responseFormTitle = (response: StandardFormResponseDto) => (
        <div aria-hidden className="w-fit">
            <div className="!text-black-900 body3 truncate">
                {response?.formTitle ?? 'Untitled'}
            </div>
        </div>
    );

    const getResponseUrl = (response: StandardFormResponseDto) => {
        switch (response.provider) {
            case 'google':
                return `${googleFormHostUrl}forms/d/${response.formId}/edit?pli=1#response=${response.responseId}`;
            case 'typeform':
                return `${typeFormHostUrl}form /${response.formId}/results#responses`;
            default:
                return `/${workspace.workspaceName}/dashboard/forms/${response.formId}?view=Responses&sub_id=${response.responseId}`;
        }
    };

    const Status = ({ status }: { status: string }) => <StatusBadge status={status} />;

    const DeletedOn = ({ status, response }: { status: string; response: StandardFormResponseDto }) => {
        // "Not deleted yet" restated the Pending chip one column over; a quiet
        // dash keeps the column for the fact it actually holds — the date.
        return (
            <div className="flex items-center gap-10 md:gap-20 xl:gap-40">
                {status.toLowerCase() === 'pending' ? <span className="text-black-500 text-sm">—</span> : <span className="text-black-700 text-sm font-medium">{utcToLocalDateTIme(response.updatedAt)}</span>}
            </div>
        );
    };

    // A deletion request is a task for the workspace owner, so a pending row
    // carries the action that completes it — deleting the response — next to
    // a quiet way to review what would be deleted first. The delete goes
    // through the DELETE_RESPONSE confirmation; it is permanent.
    const RequestActions = ({ status, response }: { status: string; response: StandardFormResponseDto }) => {
        const isSelf = response.provider === 'self' || response.formImportedBy === user.id;

        if (status.toLowerCase() !== 'pending' || !isSelf) return <></>;

        if (requestForDeletion && response.provider === 'self') {
            return (
                <div className="flex items-center gap-1">
                    <Button
                        variant="ghost"
                        className="!px-2"
                        onClick={() => {
                            triggerSingleResponse({
                                workspace_id: workspace?.id ?? '',
                                submission_id: response.responseId
                            }).then((result: any) => {
                                openModal('VIEW_RESPONSE', { response: result.data.response, formFields: getFormFields(result.data.form), form: result.data.form, formId: result.data.form.formId, workspaceId: workspace.id });
                            });
                        }}
                    >
                        View
                    </Button>
                    <Button variant="dangerGhost" className="!px-2" onClick={() => openConfirmModal('DELETE_RESPONSE', { workspace, formId: response.formId, responseId: response.responseId })}>
                        Delete response
                    </Button>
                </div>
            );
        }

        return (
            <div className="truncate">
                <AnchorLink target={response.provider !== 'self' ? '_blank' : '_self'} href={getResponseUrl(response)}>
                    <Button variant="ghost" className="!p-0">
                        {t(localesCommon.goToResponse)}
                        <ChevronForward className={'text-brand-500 h-6 w-6 ml-2'} />
                    </Button>
                </AnchorLink>
            </div>
        );
    };

    const dataTableResponseColumns: any = [
        {
            name: requestForDeletion ? t(formConstant.requestedBy) : t(formConstant.responder),
            selector: (response: StandardFormResponseDto) => responseDataOwnerField(response),
            style: {
                color: 'rgba(77, 77, 77, 1)',
                paddingLeft: '8px',
                fontSize: '14px',
                lineheight: '21px',
                paddingRight: '8px',
                fontWeight: '500'
            }
        },
        {
            name: requestForDeletion ? t(formConstant.requestedOn) : t(formConstant.respondedOn),
            selector: (row: StandardFormResponseDto) => (!!row?.createdAt ? `${utcToLocalDateTIme(row.createdAt)}` : ''),
            style: {
                color: 'rgba(77, 77, 77, 1)',
                paddingLeft: '8px',
                fontSize: '14px',
                lineheight: '21px',
                paddingRight: '8px',
                fontWeight: '500'
            }
        }
    ];

    if (requestForDeletion) {
        const statusToAdd = [
            {
                name: t(localesCommon.status),
                selector: (row: StandardFormResponseDto) =>
                    Status({
                        status: row?.status || t(formConstant.status.pending)
                    }),
                style: {
                    color: '#3A465A',
                    paddingLeft: '8px',
                    paddingRight: '8px'
                }
            },
            {
                name: t('DELETED_ON'),
                selector: (row: StandardFormResponseDto) =>
                    DeletedOn({
                        status: row?.status || t(formConstant.status.pending),
                        response: row
                    }),
                style: {
                    color: '#3A465A',
                    paddingLeft: '8px',
                    paddingRight: '8px'
                }
            },
            {
                name: '',
                minWidth: '250px',
                selector: (row: StandardFormResponseDto) =>
                    RequestActions({
                        status: row?.status || t(formConstant.status.pending),
                        response: row
                    }),
                style: {
                    color: '#3A465A',
                    paddingLeft: '8px',
                    paddingRight: '8px'
                }
            }
        ];
        dataTableResponseColumns.splice(3, 0, ...statusToAdd);
    }
    if (!formId) {
        const formToAdd = [
            {
                name: t(formConstant.default),
                selector: (response: StandardFormResponseDto) => responseFormTitle(response),
                style: {
                    color: '#101826',
                    fontSize: '14px',
                    fontWeight: 500,
                    paddingLeft: '8px',
                    paddingRight: '8px'
                }
            }
        ];
        dataTableResponseColumns.splice(1, 0, ...formToAdd);
    }

    const Response: any = () => {
        if (submissions.items && submissions.items.length > 0)
            return (
                <>
                    <DataTable
                        // className="p-0 mt-2 h-full !overflow-auto"
                        columns={dataTableResponseColumns}
                        data={submissions.items || []}
                        customStyles={requestForDeletion ? dataTableCustomStyles : responseTableStyles}
                        highlightOnHover={false}
                        pointerOnHover={false}
                        onRowClicked={onRowClicked}
                    />
                    {Array.isArray(submissions?.items) && submissions?.total > globalConstants.pageSize && (
                        <div className="mt-8 flex justify-center">
                            <StyledPagination shape="rounded" count={submissions?.pages || 0} page={page} onChange={handlePageChange} />
                        </div>
                    )}
                </>
            );
        return (
            <EmptyResponse
                title={t(requestForDeletion ? formConstant.empty.deletionRequest.title : formConstant.empty.response.title)}
                description={t(requestForDeletion ? formConstant.empty.deletionRequest.description : formConstant.empty.response.description)}
            />
        );
    };

    return Response();
};

export default ResponsesTable;

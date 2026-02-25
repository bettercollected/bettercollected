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
            borderColor: '#EEEEEE !important',
            // border: '1px solid transparent',
            '&:hover': {
                cursor: 'pointer',
                background: '#EEEEEE'
                // border: '1px solid #0764EB'
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

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { useLazyGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { getFormFields } from '@app/utils/form-builder-block-utils';

const ResponsesTable = ({ requestForDeletion, submissions, formId, page, setPage }: IResponsetableProps) => {
    const { openModal } = useFullScreenModal();
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
                openModal('VIEW_RESPONSE', { response: result.data.response, formFields: getFormFields(result.data.form), formId: result.data.form.formId, workspaceId: workspace.id });
            });
        }
    };
    const responseDataOwnerField = (response: StandardFormResponseDto) => (
        <div aria-hidden className="w-fit">
            <div className={cn('!text-black-900 body3 truncate', !requestForDeletion && 'hover:!text-brand-500 cursor-pointer hover:underline')}>
                {!requestForDeletion && <span onClick={() => onRowClicked(response)}>{response?.dataOwnerIdentifier ?? 'Anonymous'}</span>}
                {requestForDeletion && (response?.dataOwnerIdentifier ?? 'Anonymous')}
            </div>
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
        return (
            <div className="flex items-center gap-10 md:gap-20 xl:gap-40">
                <span className="text-black-700 text-sm font-medium">{status.toLowerCase() === 'pending' ? t('NOT_DELETED_YET') : utcToLocalDateTIme(response.updatedAt)}</span>
            </div>
        );
    };

    const GoToResponse = ({ status, response }: { status: string; response: StandardFormResponseDto }) => {
        const isSelf = response.provider === 'self' || response.formImportedBy === user.id;

        if (status.toLowerCase() !== 'pending' || !isSelf) return <></>;

        if (requestForDeletion && response.provider === 'self') {
            return (
                <div className="truncate">
                    <div
                        className="cursor-pointer inline-flex"
                        onClick={() => {
                            triggerSingleResponse({
                                workspace_id: workspace?.id ?? '',
                                submission_id: response.responseId
                            }).then((result: any) => {
                                openModal('VIEW_RESPONSE', { response: result.data.response, formFields: getFormFields(result.data.form), formId: result.data.form.formId, workspaceId: workspace.id });
                            });
                        }}
                    >
                        <Button variant="ghost" className="!p-0">
                            {t(localesCommon.goToResponse)}
                            <ChevronForward className={'text-brand-500 h-6 w-6 ml-2'} />
                        </Button>
                    </div>
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
                    color: 'rgba(0,0,0,.54)',
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
                    color: 'rgba(0,0,0,.54)',
                    paddingLeft: '8px',
                    paddingRight: '8px'
                }
            },
            {
                name: '',
                selector: (row: StandardFormResponseDto) =>
                    GoToResponse({
                        status: row?.status || t(formConstant.status.pending),
                        response: row
                    }),
                style: {
                    color: 'rgba(0,0,0,.54)',
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
                    color: '#202124',
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

import React, { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import _ from 'lodash';

import Checkbox from '@mui/material/Checkbox';
import FormControlLabel from '@mui/material/FormControlLabel';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell, { tableCellClasses } from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TablePagination from '@mui/material/TablePagination';
import TableRow from '@mui/material/TableRow';
import { styled } from '@mui/material/styles';
import { toast } from 'react-toastify';

import RequestForDeletionBadge from '@app/components/badge/request-for-deletion-badge';
import environments from '@app/configs/environments';
import { ToastId } from '@app/constants/toastId';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { useLazyGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { IGetWorkspaceSubmissionQuery } from '@app/store/workspaces/types';
import { toMonthDateYearStr } from '@app/utils/dateUtils';
import { toEndDottedStr } from '@app/utils/stringUtils';
import { requestForDeletionProps } from '@app/utils/validationUtils';

import BreadcrumbsRenderer from '../form/renderer/breadcrumbs-renderer';
import FormRenderer from '../form/renderer/form-renderer';
import { HomeIcon } from '../icons/home';
import FullScreenLoader from '../ui/fullscreen-loader';
import EmptyFormsView from './empty-form';

const StyledTableCell = styled(TableCell)(({ theme }) => ({
    [`&.${tableCellClasses.head}`]: {
        backgroundColor: '#f5f9ff',
        color: '#6B6DBA'
    },
    [`&.${tableCellClasses.body}`]: {
        fontSize: 14,
        color: '#6b6b6b !important'
    }
}));

const StyledTableContainer = styled(TableContainer)(({ theme }) => ({
    '.MuiTableCell-root': {
        borderColor: '#eaeaea !important'
    }
}));

const StyledTableRow = styled(TableRow)(({ theme }) => ({
    '&:hover': {
        backgroundColor: '#f5f9ff !important',
        cursor: 'pointer'
    }
}));

function DashboardResponsesTabContent({ workspaceId, formId }: any) {
    const router = useRouter();
    const breakpoint = useBreakpoint();

    const [trigger, { isLoading, isError, error }] = useLazyGetWorkspaceSubmissionQuery();

    if (isError) {
        // @ts-ignore
        toast.error(!!error?.error ? error?.error : 'Something went wrong', { toastId: ToastId.ERROR_TOAST });
    }

    const [form, setForm] = useState<any>([]);

    const [page, setPage] = useState(0);

    let submissionId: string = (router?.query?.sub_id as string) ?? '';

    const [responses, setResponses] = useState<Array<any>>([]);
    const [requestedForDeletion, setRequestedForDeletion] = useState(false);

    useEffect(() => {
        if (!!submissionId) {
            const submissionQuery: IGetWorkspaceSubmissionQuery = {
                workspace_id: workspaceId,
                submission_id: submissionId
            };
            trigger(submissionQuery)
                .then((d) => {
                    setForm(d.data);
                })
                .catch((e) => {
                    toast.error('Error fetching submission data.', { toastId: 'errorToast' });
                });
        }
    }, [submissionId]);

    useEffect(() => {
        if (!!formId && !!workspaceId) {
            fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${workspaceId}/forms/${formId}/submissions?request_for_deletion=${requestedForDeletion}`, {
                credentials: 'include',
                headers: {
                    'Access-Control-Allow-origin': environments.API_ENDPOINT_HOST
                }
            })
                .then((data) => {
                    data.json().then((d) => {
                        setResponses(d);
                    });
                })
                .catch((e) => console.log(e));
        }
    }, [formId, workspaceId, requestedForDeletion]);

    const handleSubmissionClick = (responseId: any) => {
        router.push({
            pathname: router.pathname,
            query: {
                ...router.query,
                sub_id: responseId
            }
        });
    };

    const handleRemoveSubmissionId = () => {
        const updatedQuery = { ...router.query };
        delete updatedQuery.sub_id;
        router.push({
            pathname: router.pathname,
            query: updatedQuery
        });
    };

    const handlePageChange = () => {
        //TODO: fetch api to call the next page
        console.log('hello');
    };

    const breadcrumbsItem = [
        {
            title: 'Responses',
            icon: <HomeIcon className="w-4 h-4 mr-2" />,
            onClick: handleRemoveSubmissionId
        },
        {
            title: ['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(submissionId, 10) : submissionId
        }
    ];

    const AllSubmissionsRenderer = () => {
        return (
            <>
                <div className="flex flex-col md:flex-row justify-between w-full">
                    <h1 data-testid="all-submissions-renderer" className="text-2xl font-extrabold mb-4">
                        Total Submissions ({responses.length})
                    </h1>

                    <FormControlLabel
                        control={
                            <Checkbox
                                checked={requestedForDeletion}
                                onChange={() => {
                                    setRequestedForDeletion(!requestedForDeletion);
                                }}
                            />
                        }
                        label="Show deletion requests"
                    />
                </div>

                {responses.length === 0 && <EmptyFormsView />}
                {responses.length !== 0 && Array.isArray(responses) && (
                    <>
                        <TableContainer component={Paper}>
                            <StyledTableContainer>
                                <Table aria-label="customized table">
                                    <TableHead>
                                        <TableRow>
                                            <StyledTableCell>Data owner</StyledTableCell>
                                            {requestedForDeletion && <StyledTableCell>Status</StyledTableCell>}
                                            <StyledTableCell align="right">Submission date</StyledTableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {responses.map((row: any) => {
                                            return (
                                                <StyledTableRow key={row.responseId} onClick={() => handleSubmissionClick(row?.responseId)}>
                                                    <StyledTableCell component="th" scope="row">
                                                        {!row.dataOwnerIdentifier ? 'Anonymous' : row.dataOwnerIdentifier}
                                                    </StyledTableCell>
                                                    {requestedForDeletion && (
                                                        <StyledTableCell>
                                                            <RequestForDeletionBadge deletionStatus={row?.deletionStatus} />
                                                        </StyledTableCell>
                                                    )}
                                                    <StyledTableCell align="right">{toMonthDateYearStr(new Date(row.createdAt))}</StyledTableCell>
                                                </StyledTableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            </StyledTableContainer>
                        </TableContainer>
                        <TablePagination component="div" rowsPerPageOptions={[]} rowsPerPage={7} count={responses.length} page={page} onPageChange={handlePageChange} />
                    </>
                )}
            </>
        );
    };

    if (isLoading) return <FullScreenLoader />;

    return (
        <>
            {!!submissionId && <BreadcrumbsRenderer breadcrumbsItem={breadcrumbsItem} />}
            {!submissionId && <AllSubmissionsRenderer />}
            {!!form && !!submissionId && <FormRenderer form={form.form} response={form.response} />}
        </>
    );
}

export default React.memo(DashboardResponsesTabContent);

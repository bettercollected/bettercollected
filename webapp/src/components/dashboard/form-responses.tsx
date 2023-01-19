import React, { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

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

import environments from '@app/configs/environments';
import { ToastId } from '@app/constants/toastId';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { useLazyGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { IGetWorkspaceSubmissionQuery } from '@app/store/workspaces/types';
import { toMonthDateYearStr } from '@app/utils/dateUtils';
import { toEndDottedStr } from '@app/utils/stringUtils';

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

function FormSubmissionsTab({ workspaceId, formId, workspaceName, workspace }: any) {
    const router = useRouter();
    const breakpoint = useBreakpoint();

    const [trigger, { isLoading, isError, data, error }] = useLazyGetWorkspaceSubmissionQuery();

    if (isError) {
        toast.error(!!error.error ? error.error : 'Something went wrong', { toastId: ToastId.ERROR_TOAST });
    }

    const [form, setForm] = useState([]);

    const [page, setPage] = useState(0);

    const submissionId = router?.query?.sub_id ?? '';

    const [responses, setResponses] = useState<Array<any>>([]);

    useEffect(() => {
        if (!!submissionId) {
            const submissionQuery: IGetWorkspaceSubmissionQuery = {
                workspace_id: workspaceId,
                submission_id: submissionId
            };
            trigger(submissionQuery)
                .then((d) => {
                    setForm(d.data?.payload?.content);
                })
                .catch((e) => {
                    toast.error('Error fetching submission data.', { toastId: 'errorToast' });
                });
        } else return;
    }, [submissionId]);

    useEffect(() => {
        if (!!formId && !!workspaceId) {
            fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${workspaceId}/forms/${formId}/submissions`, {
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
    }, [formId, workspaceId]);

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
                <h1 className="text-2xl font-extrabold mb-4">Total Submissions ({responses.length})</h1>
                {responses.length === 0 && <EmptyFormsView />}
                {responses.length !== 0 && (
                    <>
                        <TableContainer component={Paper}>
                            <StyledTableContainer>
                                <Table aria-label="customized table">
                                    <TableHead>
                                        <TableRow>
                                            <StyledTableCell>Data owner</StyledTableCell>
                                            <StyledTableCell align="right">Submission date</StyledTableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {responses.map((row: any) => (
                                            <StyledTableRow key={row.responseId} onClick={() => handleSubmissionClick(row?.responseId)}>
                                                <StyledTableCell component="th" scope="row">
                                                    {!row.dataOwnerIdentifier ? 'Anonymous' : row.dataOwnerIdentifier}
                                                </StyledTableCell>
                                                <StyledTableCell align="right">{toMonthDateYearStr(new Date(row.createdAt))}</StyledTableCell>
                                            </StyledTableRow>
                                        ))}
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
            {!!form && !!submissionId && <FormRenderer form={form} />}
        </>
    );
}

export default React.memo(FormSubmissionsTab);

import React, { useEffect, useState } from 'react';

import { Router, useRouter } from 'next/router';

import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell, { tableCellClasses } from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import { styled } from '@mui/material/styles';
import { toast } from 'react-toastify';

import environments from '@app/configs/environments';
import { useLazyGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { toMonthDateYearStr } from '@app/utils/dateUtils';

import FormRenderer from '../form-renderer/FormRenderer';
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

    const [trigger, { isLoading, isError, data }] = useLazyGetWorkspaceSubmissionQuery();

    if (isError) {
        toast.error('something went wrong!');
    }

    const [form, setForm] = useState([]);

    const submissionId = router?.query?.sub_id ?? '';

    const [responses, setResponses] = useState([]);

    useEffect(() => {
        if (!!submissionId) {
            const submissionQuery = {
                workspace_id: workspaceId,
                submission_id: submissionId
            };
            trigger(submissionQuery)
                .then((d) => {
                    setForm(d.data?.payload?.content);
                })
                .catch((e) => {
                    toast.error('Error fetching submission data.');
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
                        console.log('submissions data: ', d);
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

    const RenderSubmissionForm = () => {
        if (isLoading) {
            return <FullScreenLoader />;
        } else {
            return <FormRenderer form={form} />;
        }
    };

    const handleRemoveSubmissionId = () => {
        const updatedQuery = { ...router.query };
        delete updatedQuery.sub_id;
        router.push({
            pathname: router.pathname,
            query: updatedQuery
        });
    };

    const BreadCrumbRenderer = () => {
        return (
            <div className="max-h-[100vh] overflow-auto mb-4">
                <nav className="flex mt-3 px-0 md:px-0" aria-label="Breadcrumb">
                    <ol className="inline-flex items-center space-x-1 md:space-x-3">
                        <li className="inline-flex items-center">
                            <span aria-hidden onClick={handleRemoveSubmissionId} className="cursor-pointer inline-flex items-center text-sm font-medium text-gray-700 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
                                <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z"></path>
                                </svg>
                                Responses
                            </span>
                        </li>
                        <li aria-current="page">
                            <div className="flex items-center">
                                <svg className="w-6 h-6 text-gray-400" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                    <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"></path>
                                </svg>
                                {!!submissionId && <span className="ml-1 text-sm font-medium text-gray-500 md:ml-2 dark:text-gray-400">{submissionId}</span>}
                            </div>
                        </li>
                    </ol>
                </nav>
            </div>
        );
    };

    const AllSubmissionsRenderer = () => {
        return (
            <>
                <h1 className="text-2xl font-extrabold mb-4">Total Submissions ({responses.length})</h1>
                {responses.length === 0 && <EmptyFormsView />}
                {responses.length !== 0 && (
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
                                    {responses.map((row) => (
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
                        {/* <TablePagination className="flex justify-center" count={rows.length} rowsPerPage={5} page={page} onPageChange={handleChangePage} /> */}
                    </TableContainer>
                )}
            </>
        );
    };

    if (isLoading) return <FullScreenLoader />;

    return (
        <>
            {!!submissionId && <BreadCrumbRenderer />}
            {!submissionId && <AllSubmissionsRenderer />}
            {!!form && !!submissionId && <FormRenderer form={form} />}
        </>
    );
}

export default React.memo(FormSubmissionsTab);

import React, { useEffect, useState } from 'react';

import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell, { tableCellClasses } from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TablePagination from '@mui/material/TablePagination';
import TableRow from '@mui/material/TableRow';
import { styled } from '@mui/material/styles';

import environments from '@app/configs/environments';
import { toMonthDateYearStr } from '@app/utils/dateUtils';

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

function createData(name: string, calories: number, fat: number, carbs: number, protein: number) {
    return { name, calories, fat, carbs, protein };
}

const rows = [createData('Frozen yoghurt', 159, 6.0, 24, 4.0), createData('Ice cream sandwich', 237, 9.0, 37, 4.3), createData('Eclair', 262, 16.0, 24, 6.0), createData('Cupcake', 305, 3.7, 67, 4.3), createData('Gingerbread', 356, 16.0, 49, 3.9)];

export default function FormSubmissionsTab({ workspaceId, formId }: any) {
    const [page, setPage] = useState(1);
    const handleChangePage = (event: unknown, newPage: number) => {
        setPage(newPage);
    };

    const [responses, setResponses] = useState([]);

    useEffect(() => {
        //TODO: fetch all the responses of the given form
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
        console.log(responseId);
    };

    return (
        <div>
            <h1 className="text-2xl font-extrabold mb-4">Total Submissions ({responses.length})</h1>
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
                                    <StyledTableRow key={row.responseId} onClick={() => handleSubmissionClick(row.responseId)}>
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
        </div>
    );
}

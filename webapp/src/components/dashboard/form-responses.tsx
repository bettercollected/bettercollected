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
        backgroundColor: '#f5fff7 !important',
        cursor: 'pointer'
    }
}));

function createData(name: string, calories: number, fat: number, carbs: number, protein: number) {
    return { name, calories, fat, carbs, protein };
}

const rows = [createData('Frozen yoghurt', 159, 6.0, 24, 4.0), createData('Ice cream sandwich', 237, 9.0, 37, 4.3), createData('Eclair', 262, 16.0, 24, 6.0), createData('Cupcake', 305, 3.7, 67, 4.3), createData('Gingerbread', 356, 16.0, 49, 3.9)];

export default function FormSubmissionsTab() {
    const [page, setPage] = useState(1);
    const handleChangePage = (event: unknown, newPage: number) => {
        setPage(newPage);
    };

    useEffect(() => {
        //TODO: fetch all the responses of the given form
        fetch(`${environments.API_ENDPOINT_HOST}/forms/1-CQgKC3Ms-PqCuJNXDEkjlRP1MR4NscStXhz5rhkddk/submissions`, {
            credentials: 'include',
            headers: {
                'Access-Control-Allow-origin': environments.API_ENDPOINT_HOST
            }
        }).then((data) => {
            data.json().then((d) => {
                console.log('data: ', d);
            });
        });
    }, []);

    return (
        <div>
            <h1 className="text-2xl font-extrabold mb-4">Total Submissions (5)</h1>
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
                            {rows.map((row) => (
                                <StyledTableRow key={row.name}>
                                    <StyledTableCell component="th" scope="row">
                                        {row.name}
                                    </StyledTableCell>
                                    <StyledTableCell align="right">{row.calories}</StyledTableCell>
                                </StyledTableRow>
                            ))}
                        </TableBody>
                    </Table>
                </StyledTableContainer>
                <TablePagination className="flex justify-center" count={rows.length} rowsPerPage={5} page={page} onPageChange={handleChangePage} />
            </TableContainer>
        </div>
    );
}

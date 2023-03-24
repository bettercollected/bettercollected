import React from 'react';

import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell, { tableCellClasses } from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import { styled } from '@mui/material/styles';

import RequestForDeletionBadge from '@app/components/badge/request-for-deletion-badge';
import SubmissionCard from '@app/components/cards/submission-card';
import EmptyFormsView from '@app/components/dashboard/empty-form';
import { StandardFormResponseDto } from '@app/models/dtos/form';
import { toHourMinStr, toLocaleString } from '@app/utils/dateUtils';

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

const SubmissionsGrid = ({ responses, requestedForDeletionOnly }: any) => {
    const handleSubmissionCLick = (responseId: string) => {};

    return (
        <TableContainer component={Paper}>
            <StyledTableContainer>
                <Table aria-label="customized table w-full">
                    <TableHead className="!rounded-b-none">
                        <TableRow>
                            <StyledTableCell>Data owner</StyledTableCell>
                            <StyledTableCell>Form Title</StyledTableCell>
                            {requestedForDeletionOnly && <StyledTableCell>Response ID</StyledTableCell>}
                            {requestedForDeletionOnly && <StyledTableCell>Status</StyledTableCell>}
                            <StyledTableCell align="right">{requestedForDeletionOnly ? 'Requested date' : 'Submission date'}</StyledTableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody className="w-full">
                        {Array.isArray(responses) &&
                            responses.map((response: StandardFormResponseDto, idx: number) => (
                                <TableRow
                                    className={`${!requestedForDeletionOnly && 'hover:cursor-pointer hover:bg-[#f5f9ff]'}`}
                                    key={response.responseId + idx}
                                    onClick={() => {
                                        handleSubmissionCLick(response.responseId);
                                    }}
                                >
                                    <StyledTableCell component="th" scope="row">
                                        {response.dataOwnerIdentifier || 'Anonymous'}
                                    </StyledTableCell>

                                    <StyledTableCell>{response.formTitle}</StyledTableCell>
                                    {requestedForDeletionOnly && <StyledTableCell>{response.responseId}</StyledTableCell>}
                                    {requestedForDeletionOnly && (
                                        <StyledTableCell>
                                            <RequestForDeletionBadge deletionStatus={response.deletionStatus || 'pending'} />
                                        </StyledTableCell>
                                    )}

                                    <StyledTableCell align="right">{response.createdAt && toLocaleString(new Date(response.createdAt))}</StyledTableCell>
                                </TableRow>
                            ))}
                    </TableBody>
                </Table>
            </StyledTableContainer>
        </TableContainer>
    );
};

export default SubmissionsGrid;

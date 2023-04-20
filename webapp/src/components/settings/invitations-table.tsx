import { useEffect, useState } from 'react';

import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';

import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceMembersInvitationsQuery, useGetWorkspaceMembersQuery } from '@app/store/workspaces/members-n-invitations-api';
import { toLocaleString, toLocaleStringFromDateString } from '@app/utils/dateUtils';
import { getFullNameFromUser } from '@app/utils/userUtils';

export default function InvitationsTable() {
    const workspace = useAppSelector((state) => state.workspace);
    const { data, isLoading } = useGetWorkspaceMembersInvitationsQuery({ workspaceId: workspace.id });
    const [invitations, setInvitations] = useState<Array<any>>([]);

    useEffect(() => {
        if (data && data.items && Array.isArray(data.items)) setInvitations(data.items);
    }, [data]);

    return (
        <TableContainer component={Paper}>
            <Table sx={{ minWidth: 650 }} aria-label="simple table">
                <TableHead>
                    <TableRow>
                        <TableCell>Member</TableCell>
                        <TableCell align="right">Role</TableCell>
                        <TableCell align="right">Status</TableCell>
                        <TableCell align="right">Invitation Date</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {invitations.map((invitation: any) => (
                        <TableRow key={invitation.email} sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
                            <TableCell component="th" scope="row">
                                {invitation.email}
                            </TableCell>
                            <TableCell align="right">{invitation.role}</TableCell>
                            <TableCell align="right">{invitation.invitation_status}</TableCell>
                            <TableCell align="right">{toLocaleStringFromDateString(invitation.created_at)}</TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </TableContainer>
    );
}

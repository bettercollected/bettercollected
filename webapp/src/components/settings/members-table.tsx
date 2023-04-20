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
import { useGetWorkspaceMembersQuery } from '@app/store/workspaces/members-n-invitations-api';
import { toLocaleString, toLocaleStringFromDateString } from '@app/utils/dateUtils';
import { getFullNameFromUser } from '@app/utils/userUtils';

export default function MembersTable() {
    const workspace = useAppSelector((state) => state.workspace);
    const { data, isLoading } = useGetWorkspaceMembersQuery({ workspaceId: workspace.id });
    const [members, setMembers] = useState<Array<any>>([]);

    useEffect(() => {
        if (data && Array.isArray(data)) setMembers(data);
    }, [data]);

    return (
        <TableContainer component={Paper}>
            <Table sx={{ minWidth: 650 }} aria-label="simple table">
                <TableHead>
                    <TableRow>
                        <TableCell>Member</TableCell>
                        <TableCell align="right">Role</TableCell>
                        <TableCell align="right">Joined</TableCell>
                        <TableCell align="right"></TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {members.map((member: any) => (
                        <TableRow key={member.email} sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
                            <TableCell component="th" scope="row">
                                <div className="flex space-x-4">
                                    <AuthAccountProfileImage image={member.profile_image} name={getFullNameFromUser(member)} size={40} />
                                    <div className="flex flex-col">
                                        <div className="!body3">{getFullNameFromUser(member)}</div>
                                        <div className="!body5 text-gray-500">{member.email}</div>
                                    </div>
                                </div>
                            </TableCell>
                            <TableCell align="right">{member.roles}</TableCell>
                            <TableCell align="right">{toLocaleStringFromDateString(member.joined)}</TableCell>
                            <TableCell align="right"></TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </TableContainer>
    );
}

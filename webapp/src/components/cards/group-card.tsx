import React from 'react';

import EllipsisOption from '@Components/Common/Icons/EllipsisOption';
import { Typography } from '@mui/material';

import AuthAccountProfileImage from '../auth/account-profile-image';
import { Telegram } from '../icons/brands/telegram';
import Button from '../ui/button/button';

interface ResponderGroupDto {
    id: string;
    name: string;
    description: string;
    emails: Array<emailDto>;
}
interface emailDto {
    identifier: string;
}

export default function GroupCard({ responderGroup }: { responderGroup: ResponderGroupDto }) {
    return (
        <div className="flex flex-col bg-white items-start p-4 rounded-[8px] relative">
            <EllipsisOption className="rotate-90 absolute top-[23px] right-5" />
            <div className="flex gap-8 items-center">
                <div className="px-[6px] p-1 bg-black-500 rounded">
                    <Typography className="sh1 !text-white">{responderGroup.name[0].toUpperCase()}</Typography>
                </div>
                <Typography>{responderGroup.name}</Typography>
            </div>
            <p className="body4 text-black-800 mt-4 mb-10">{responderGroup.description}</p>
            <p>Members ({responderGroup.emails.length})</p>
            <div className="flex flex-wrap gap-2 mt-4 mb-10">
                {responderGroup.emails.map((email) => {
                    return <p key={email.identifier}>{email.identifier},</p>;
                })}
            </div>
            <Button variant="ghost" size="medium">
                <div className="flex items-center  gap-[5px]">
                    <Telegram className="h-[20px] w-[20px] stroke-black-900" />
                    <Typography>Send Form</Typography>
                </div>
            </Button>
        </div>
    );
}

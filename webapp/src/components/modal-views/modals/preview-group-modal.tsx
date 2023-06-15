import React from 'react';

import { useTranslation } from 'next-i18next';

import { Close } from '@mui/icons-material';

import { useModal } from '@app/components/modal-views/context';
import { members } from '@app/constants/locales/members';
import { Plans, UserDto } from '@app/models/dtos/UserDto';
import { ResponderGroupDto } from '@app/models/dtos/groups';

export default function PreviewGroup({ responderGroup }: { responderGroup: ResponderGroupDto }) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    return (
        <div className="p-7 bg-brand-100 relative rounded-[8px] md:w-[670px]">
            <Close
                className="absolute top-5 right-5 cursor-pointer"
                onClick={() => {
                    closeModal();
                }}
            />
            <p className="h4 !leading-none">{responderGroup.name}</p>
            <p className="body4 leading-none mt-5 mb-10 !text-black-700 break-all">{responderGroup.description}</p>
            {/* <div className="flex items-center mt-12 gap-[18px]">
                <p className="body4 leading-none !text-black-700">{t(groupConstant.createdBy)}:</p>
                <UserDetails user={user} />
            </div>
            <div className="flex mt-6 gap-4">
                <p className="body4 leading-none !text-black-700">{t(groupConstant.createdOn)}:</p>
                <p className="body4">03 Apr, 2023</p>
            </div> */}
            <p className="body1 mt-12 mb-4">
                {responderGroup.emails.length > 1 ? t(members.default) : t(members.member)}({responderGroup?.emails?.length})
            </p>
            <div className="flex flex-col gap-2">
                {responderGroup.emails.map((email) => {
                    return (
                        <p key={email} className="body4 bg-white px-2  rounded py-5 !text-black-800">
                            {email}
                        </p>
                    );
                })}
            </div>
        </div>
    );
}

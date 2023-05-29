import React, { useState } from 'react';

import { Close } from '@mui/icons-material';
import cn from 'classnames';

import BetterInput from '@app/components/Common/input';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button/button';
import { GroupInfoDto } from '@app/models/dtos/createGroups';

export default function CreateGroupModal() {
    const { closeModal } = useModal();
    const [groupInfo, setGroupInfo] = useState<GroupInfoDto>({
        name: '',
        description: '',
        email: '',
        emails: []
    });
    const handleInput = (event: any) => {
        setGroupInfo({
            ...groupInfo,
            [event.target.id]: event.target.value
        });
    };
    console.log(groupInfo);
    const addEmail = (email: string) => {
        let emails = groupInfo.emails;
        emails.push(email);

        setGroupInfo({
            ...groupInfo,
            email: '',
            emails: emails
        });
    };
    return (
        <div className="p-7 bg-white relative rounded-[8px] md:max-w-[670px]">
            <Close
                className="absolute top-5 right-5 cursor-pointer"
                onClick={() => {
                    closeModal();
                }}
            />
            <h4 className="h4 !leading-none">Create New Group</h4>
            <p className="body4 leading-none mt-5 mb-10 text-black-700">Create a group to send forms to entire groups, streamlining the process and saving time.</p>
            <p className="body4 leading-none mb-2">
                Group Name<span className="text-red-800">*</span>
            </p>
            <BetterInput className="!mb-0" inputProps={{ className: '!py-3' }} id="name" placeholder="Enter group name" onChange={handleInput} />
            <p className="body4 leading-none mt-6 mb-2">Description</p>
            <BetterInput className="!mb-0" id="description" placeholder="Add description" rows={3} multiline onChange={handleInput} />
            <p className="mt-10 leading-none mb-2 body1">Members(3)</p>
            <p className="text-black-700 leading-none body4">Only these members can see your form in your workspace. </p>
            <div className="flex gap-2 mt-4 md:w-[350px]">
                <BetterInput value={groupInfo.email} inputProps={{ className: '!py-3 ' }} id="email" placeholder="Enter member email" onChange={handleInput} />
                <Button
                    size="medium"
                    disabled={!groupInfo.email}
                    className={cn('bg-black-800 hover:!bg-black-900', !groupInfo.email && 'opacity-30')}
                    onClick={() => {
                        addEmail(groupInfo.email);
                    }}
                >
                    Add
                </Button>
            </div>
            {groupInfo.emails.length !== 0 && (
                <div>
                    <p className="mt-6 leading-none mb-4 body5">Member email</p>
                    <div className="items-center  w-full   gap-4 flex flex-wrap ">
                        {groupInfo.emails.map((email) => {
                            return (
                                <div className="p-2 rounded flex items-center gap-2 bg-blue-200 body5 !text-brand-500" key={email}>
                                    <span className="leading-none">{email}</span>
                                    <Close
                                        className="h-4 w-4 cursor-pointer"
                                        onClick={() => {
                                            setGroupInfo({
                                                ...groupInfo,
                                                emails: groupInfo.emails.filter((item) => item !== email)
                                            });
                                        }}
                                    />
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
            <div className="flex justify-end mt-10">
                <Button size="medium" disabled={!groupInfo.name || groupInfo.emails.length === 0}>
                    <span className="body1 !text-blue-100"> Create Group </span>
                </Button>
            </div>
        </div>
    );
}

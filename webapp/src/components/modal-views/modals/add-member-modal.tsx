import { useState } from 'react';

import { useTranslation } from 'next-i18next';

import BetterInput from '@app/components/Common/input';
import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import SettingsCard from '@app/components/settings/card';
import Button from '@app/components/ui/button';
import { buttonConstant } from '@app/constants/locales/button';
import { localesGlobal } from '@app/constants/locales/global';
import { groupConstant } from '@app/constants/locales/group';
import { useGroupMember } from '@app/lib/hooks/use-group-members';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { useAppSelector } from '@app/store/hooks';

export default function AddMemberModal({ group }: { group: ResponderGroupDto }) {
    const { addMemberOnGroup, addMemberResponse } = useGroupMember();
    const workspace = useAppSelector((state) => state.workspace);

    const { t } = useTranslation();
    const [member, setmember] = useState('');
    const { closeModal } = useModal();
    return (
        <>
            <SettingsCard className="!space-y-0 relative">
                <Close onClick={closeModal} className="absolute top-2 right-2 cursor-pointer p-2 h-8 w-8" />
                <div className="sh1 !leading-none">{t(groupConstant.addMember.default)}</div>
                <div className="body4 pt-6 !leading-none ">{t(groupConstant.addMember.description)}</div>
                <form
                    onSubmit={(e) => {
                        e.preventDefault();
                        addMemberOnGroup({ email: member, group, workspaceId: workspace.id });
                    }}
                    className="flex pt-8  flex-col justify-start"
                >
                    <div className="body1 mb-3 !leading-none">{t(localesGlobal.enterEmail)}</div>
                    <BetterInput
                        disabled={addMemberResponse.isLoading}
                        data-testid="otp-input"
                        spellCheck={false}
                        value={member}
                        type="email"
                        className="!mb-0"
                        placeholder={t(localesGlobal.enterEmail)}
                        onChange={(event) => {
                            setmember(event.target.value);
                        }}
                    />
                    <div className="flex w-full mt-8 justify-end">
                        <Button disabled={!member} isLoading={addMemberResponse.isLoading} size="small" type="submit">
                            {t(buttonConstant.addMember)}
                        </Button>
                    </div>
                </form>
            </SettingsCard>
        </>
    );
}

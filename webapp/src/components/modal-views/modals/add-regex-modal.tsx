import { useState } from 'react';

import { useTranslation } from 'react-i18next';

import HeaderModalWrapper from '@Components/modals/modal-wrapper/header-modal-wrapper';
import { Button } from '@app/shadcn/components/ui/button';

import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { groupConstant } from '@app/constants/locales/group';
import { handleRegexType } from '@app/models/enums/group-regex';
import { AppInput } from '@app/shadcn/components/ui/input';
import { isEmptyString } from '@app/utils/string-utils';
import { Label } from '@radix-ui/react-label';


export default function AddRegexModal({ handleRegex }: { handleRegex: (regex: string, type: handleRegexType) => void }) {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const [regex, setRegex] = useState<string>('');
    const handleInput = (event: any) => {
        setRegex(event.target.value);
    };

    const handleSubmit = (event: any) => {
        event.preventDefault();
        if (!isEmptyString(regex)) {
            handleRegex(regex, handleRegexType.ADD);
        }
    };

    return (
        <HeaderModalWrapper headerTitle={t('BUTTON.ADD_REGEX')}>
            <form onSubmit={handleSubmit}>
                <h4 className="h4-new">{t(groupConstant.regex.modal.title)}</h4>
                <p className="my-2">
                    <span className="!text-black-700 p2-new text-sm !font-normal">
                        Use <span className="text-pink-500">*@yourcompany.com</span> to add all employees with email addresses ending in &apos;@yourcompany.com&apos;.{' '}
                    </span>
                </p>
                <Label className="h4-new mb-2 !font-medium" htmlFor="regex">
                    {t(groupConstant.regex.modal.label)}
                </Label>
                <div className="pt-2">
                    <AppInput className="w-full" onChange={handleInput} placeholder="*@example.com" />
                </div>
                <div className="flex justify-end mt-4">
                    <Button size="medium" className={'w-full'} disabled={!regex}>
                        {t(buttonConstant.addRegex)}
                    </Button>
                </div>
            </form>
        </HeaderModalWrapper>
    );
}
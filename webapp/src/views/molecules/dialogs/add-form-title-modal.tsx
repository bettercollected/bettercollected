'use client';

import { useState } from 'react';

import { useTranslation } from 'react-i18next';
import { useDialogModal } from '@app/lib/hooks/use-dialog-modal';
import { Button } from '@app/shadcn/components/ui/button';
import { Input } from '@app/shadcn/components/ui/input';
import { useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';

export default function AddFormTitleModal() {
    const { t } = useTranslation('builder');
    const { formState, setFormState } = useFormState();

    const [title, setTitle] = useState(t('NEW_FORM_MODAL.DEFAULT_TITLE'));
    const { formFields } = useFormFieldsAtom();
    const { setActiveSlideComponent } = useActiveSlideComponent();

    const { closeDialogModal } = useDialogModal();
    return (
        <form
            onSubmit={(event) => {
                event.preventDefault();
                // Naming a new form completes loading it: no undo step.
                setFormState(
                    {
                        ...formState,
                        title,
                        welcomePage: { ...formState.welcomePage, title }
                    },
                    { undoable: false }
                );
                setTimeout(() => {
                    setActiveSlideComponent({
                        id: formFields?.[0]?.id,
                        index: 0
                    });
                }, 300);
                closeDialogModal();
            }}
        >
            <div className="p2-new border-b-black-300 border-b p-4 ">{t('NEW_FORM_MODAL.HEADING')}</div>
            <div className="px-10 py-6">
                <div className="tex-black-800 text-normal font-semibold">{t('NEW_FORM_MODAL.NAME_IT')}</div>
                <div className="text-black-700 mb-2 text-xs">{t('NEW_FORM_MODAL.CHANGE_LATER')}</div>
                <Input
                    type="text"
                    value={title}
                    className="text-brand-500 placeholder-brand-500/20"
                    placeholder={t('NEW_FORM_MODAL.PLACEHOLDER')}
                    onChange={(event) => {
                        setTitle(event.target.value);
                    }}
                />
                <div className="flex justify-end pt-10">
                    <Button variant={'primary'} type="submit">
                        {t('NEW_FORM_MODAL.CONTINUE')}
                    </Button>
                </div>
            </div>
        </form>
    );
}

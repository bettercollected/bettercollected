'use client';

import { useState } from 'react';

import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { Button } from '@app/shadcn/components/ui/button';
import { Input } from '@app/shadcn/components/ui/input';
import { useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';

export default function AddFormTitleModal() {
    const { formState, setFormState } = useFormState();

    const [title, setTitle] = useState('New Form');
    const { formFields } = useFormFieldsAtom();
    const { setActiveSlideComponent } = useActiveSlideComponent();

    const { closeDialogModal } = useDialogModal();
    return (
        <form
            onSubmit={(event) => {
                event.preventDefault();
                setFormState({
                    ...formState,
                    title,
                    welcomePage: { ...formState.welcomePage, title }
                });
                setTimeout(() => {
                    setActiveSlideComponent({
                        id: formFields?.[0]?.id,
                        index: 0
                    });
                }, 300);
                closeDialogModal();
            }}
        >
            <div className="p2-new border-b-black-300 border-b p-4 ">Create New Form</div>
            <div className="px-10 py-6">
                <div className="tex-black-800 text-normal font-semibold">Give name to your form</div>
                <div className="text-black-700 mb-2 text-xs">You can always change it later.</div>
                <Input
                    type="text"
                    value={title}
                    className="text-brand-500 placeholder-brand-500 placeholder-opacity-20"
                    placeholder="Form Title"
                    onChange={(event) => {
                        setTitle(event.target.value);
                    }}
                />
                <div className="flex justify-end pt-10">
                    <Button variant={'primary'} type="submit">
                        Continue
                    </Button>
                </div>
            </div>
        </form>
    );
}

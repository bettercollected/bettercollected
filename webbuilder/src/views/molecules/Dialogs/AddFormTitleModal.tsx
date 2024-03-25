'use client';

import { useState } from 'react';

import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { Button } from '@app/shadcn/components/ui/button';
import { Input } from '@app/shadcn/components/ui/input';
import { useFormState } from '@app/store/jotai/form';

export default function AddFormTitleModal() {
    const { setFormState, formState, setFormTitle, setWelcomeTitle } = useFormState();

    const [title, setTitle] = useState('');

    const { closeDialogModal } = useDialogModal();
    return (
        <form
            onSubmit={(event) => {
                event.preventDefault();
                setFormTitle(title);
                setWelcomeTitle(title);
                closeDialogModal();
            }}
        >
            <div className="p2-new border-b border-b-black-300 p-4 ">
                Create New Form
            </div>
            <div className="px-10 py-6">
                <div className="tex-black-800 text-normal font-semibold">
                    Give name to your form
                </div>
                <div className="p2-new text-black-700">
                    You can always change it later.
                </div>
                <Input
                    type="text"
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

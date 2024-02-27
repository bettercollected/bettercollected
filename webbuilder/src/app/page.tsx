'use client';

import { useRouter } from 'next/navigation';

import { v4 } from 'uuid';

import { FormField } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import useFormBuilderAtom from '@app/store/jotai/fieldSelector';

export default function HomePage() {
    const { dispatchLocalStorageFields } = useFormBuilderAtom();
    const forms = JSON.parse(localStorage.getItem('forms') || '{}');
    const router = useRouter();

    const handleCreateForm = () => {
        router.push(`/forms/create`);
    };

    return (
        <div className="flex h-screen flex-col items-center justify-center gap-4 bg-brand-200">
            <Button size="lg" onClick={handleCreateForm}>
                Create Form
            </Button>
            <div className="flex flex-col gap-4">
                {Object.values(forms) && Object.values(forms).length ? (
                    Object.values(forms).map((form: any, index) => {
                        return (
                            <div
                                className=" cursor-pointer bg-brand-300 p-2 hover:bg-brand-400"
                                key={index}
                                onClick={() => {
                                    if (form?.id) router.push(`/${form?.id}`);
                                }}
                            >
                                <h1>Form with id {form?.id}</h1>
                            </div>
                        );
                    })
                ) : (
                    <>No forms to display</>
                )}
            </div>
        </div>
    );
}

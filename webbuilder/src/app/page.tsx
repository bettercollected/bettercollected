'use client';

import { useRouter } from 'next/navigation';

import { Button } from '@app/shadcn/components/ui/button';

export default function HomePage() {
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
                                    if (form?.formId) router.push(`/${form?.formId}`);
                                }}
                            >
                                <h1>Form with id {form?.formId}</h1>
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

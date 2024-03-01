'use client';

import { useRouter } from 'next/navigation';

import { ButtonVariant } from '@app/models/enums/button';
import { Button } from '@app/shadcn/components/ui/button';

export default function HomePage() {
    const forms = JSON.parse(localStorage.getItem('forms') || '{}');
    const router = useRouter();

    const handleCreateForm = () => {
        router.push(`/test/dashboard/forms/create`);
    };

    return (
        <div className="flex h-screen flex-col items-center justify-center gap-4 bg-brand-100">
            <Button
                size="lg"
                variant={ButtonVariant.Primary}
                onClick={handleCreateForm}
            >
                Create Form
            </Button>
            <div className="flex flex-col gap-4">
                {Object.values(forms) && Object.values(forms).length ? (
                    Object.values(forms).map((form: any, index) => {
                        return (
                            <div
                                key={index}
                                className="flex w-full justify-between gap-6 rounded border bg-white p-3 shadow-lg"
                            >
                                <div className=" w-full cursor-pointer rounded p-2">
                                    <h1>Form with id {form?.formId}</h1>
                                </div>
                                <Button
                                    onClick={() => {
                                        if (form?.formId)
                                            router.push(
                                                `/test/dashboard/forms/${form?.formId}/edit`
                                            );
                                    }}
                                >
                                    {' '}
                                    Edit Form
                                </Button>

                                <Button
                                    variant={ButtonVariant.Secondary}
                                    onClick={() => {
                                        if (form?.formId)
                                            router.push(`/test/forms/${form?.formId}`);
                                    }}
                                >
                                    {' '}
                                    View Form
                                </Button>
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

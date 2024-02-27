import { Button } from '@app/shadcn/components/ui/button';
import { Input } from '@app/shadcn/components/ui/input';

export default function AddFormTitleModal() {
    return (
        <div>
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
                />
                <div className="flex justify-end pt-10">
                    <Button variant={'primary'}>Continue</Button>
                </div>
            </div>
        </div>
    );
}




import { Loader2 } from 'lucide-react';

import { StandardFormDto } from '@app/models/dtos/form';
import GreenCheckedCircle from '@Components/icons/green-checked-circle';

export default function ImportSuccessfulComponent({ form }: { form: StandardFormDto }) {
    return (
        <div className="flex w-full flex-col items-center px-5 pb-5 pt-5 lg:w-[867px] lg:px-12 lg:pt-10">
            <GreenCheckedCircle />
            <div className="h3-new mt-6 !text-[#7248BC]"> {form?.title}</div>
            <div className="h3-new">Imported Successfully!</div>
            <div className="p4-new text-black-700">now appearing more beautiful</div>
            <div className="mb-6 mt-12 flex flex-row items-center gap-2">
                <Loader2 className="animate-spin text-primary" size={16} />
                <span>Opening</span>
            </div>
        </div>
    );
}

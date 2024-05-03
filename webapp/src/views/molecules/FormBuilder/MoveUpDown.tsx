import Divider from '@Components/Common/DataDisplay/Divider';
import { ChevronDown, ChevronUp } from 'lucide-react';

export default function MoveUpDown() {
    return (
        <div className="border-black-500 flex flex-col rounded border ">
            <ChevronUp />
            <Divider />
            <ChevronDown />
        </div>
    );
}

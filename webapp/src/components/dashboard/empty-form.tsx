import Image from 'next/image';

import EmptyTray from '@app/assets/svgs/empty-tray.svg';

export default function EmptyFormsView() {
    return (
        <div className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
            <Image src={EmptyTray} width={40} height={40} alt="Empty Tray" />
            <p className="mt-4 p-0">0 forms</p>
        </div>
    );
}

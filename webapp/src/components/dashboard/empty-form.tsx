import Image from 'next/image';

import EmptyTray from '@app/assets/svgs/empty-tray.svg';

export default function EmptyFormsView(props: any) {
    return (
        <div className={`w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey ${props?.className ? props?.className : ''}`}>
            <Image data-testid="empty-forms-view-image" src={EmptyTray} width={40} height={40} alt="Empty Tray" />
            <p className="mt-4 p-0">{props?.description || '0 Forms'}</p>
        </div>
    );
}

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import ShareView from '@app/components/ui/share-view';

interface Props {
    url: string;
    title?: string;
    showCopy?: boolean;
}

export default function ShareModalView({ url, title, showCopy }: Props) {
    const { closeModal } = useModal();
    return (
        <div className="rounded-[4px] relative bg-white md:p-10 p-5  dark:border-gray-700 dark:bg-light-dark">
            <Close onClick={closeModal} className="absolute top-2 right-2 cursor-pointer p-2 h-8 w-8" />
            <ShareView url={url} title={title} showCopy={showCopy} />
        </div>
    );
}

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import ShareView from '@app/components/ui/share-view';

interface Props {
    url: string;
    title?: string;
    showCopy?: boolean;

    [props: string]: any;
}

export default function ShareModalView({ url, title, showCopy, ...props }: Props) {
    const { closeModal } = useModal();
    return (
        <div className="border-black-200 relative w-[calc(100vw-2rem)] max-w-[460px] rounded-2xl border bg-white p-6 text-left shadow-xl sm:w-[460px] sm:p-8">
            <button
                onClick={closeModal}
                aria-label="Close"
                className="text-black-500 hover:bg-black-100 hover:text-black-800 absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-md transition-colors"
            >
                <Close className="h-4 w-4" />
            </button>
            <ShareView url={url} title={title} showCopy={showCopy} {...props} />
        </div>
    );
}
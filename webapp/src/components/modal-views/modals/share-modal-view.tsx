import ShareView from '@app/components/ui/share-view';

interface Props {
    url: string;
    title?: string;
    showCopy?: boolean;
}

export default function ShareModalView({ url, title, showCopy }: Props) {
    return (
        <div className="rounded-[4px] bg-white pt-5 pb-7 px-7 lg:px-5 dark:border-gray-700 dark:bg-light-dark sm:pb-8 sm:pt-6">
            <ShareView url={url} title={title} showCopy={showCopy} />
        </div>
    );
}


import EmptyFormIcon from '@Components/icons/empty-form';

interface IZeroElementProps {
    title: string;
    description: string;
    className?: string;
    /** The title's heading level; pages that already have an h1 pass 2. */
    headingLevel?: 1 | 2 | 3;
}

export default function ZeroElement({ title, description, className = '', headingLevel = 1 }: IZeroElementProps) {
    const Heading = `h${headingLevel}` as 'h1' | 'h2' | 'h3';
    return (
        <div className={`flex flex-col w-full h-full items-center justify-center min-h-[290px] text-center py-[60px] bg-white rounded px-13 gap-4 ${className}`}>
            <EmptyFormIcon />
            <div>
                <Heading className="h4-new mt-2">{title}</Heading>
                <p className="p2-new mt-1 max-w-[290px] md:max-w-[316px] text-black-700!">{description}</p>
            </div>
        </div>
    );
}

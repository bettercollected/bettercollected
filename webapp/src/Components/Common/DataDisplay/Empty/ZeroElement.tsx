import Empty from '@Components/Common/Icons/Common/Empty';

interface IZeroElementProps {
    title: string;
    description: string;
    className?: string;
}

export default function ZeroElement({ title, description, className = '' }: IZeroElementProps) {
    return (
        <div className={`flex flex-col w-full h-full items-center justify-center text-center py-[60px] px-13 gap-4 ${className}`}>
            <Empty />
            <h1 className="sh1 !leading-none mt-[14px]">{title}</h1>
            <p className="body4 !leading-none max-w-[290px] md:max-w-[500px] !text-black-700">{description}</p>
        </div>
    );
}

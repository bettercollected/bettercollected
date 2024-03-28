
import Back from '@app/views/atoms/Icons/Back';

export default function BackButton({ handleClick }: { handleClick: () => void }) {
    const handleBackClick = async () => {
        await handleClick();
    };
    return (
        <div
            className="paragraph flex cursor-pointer items-center gap-1 py-4 text-black-900 hover:text-brand-500 hover:underline"
            onClick={handleBackClick}
        >
            <Back />
            <span>Back</span>
        </div>
    );
}

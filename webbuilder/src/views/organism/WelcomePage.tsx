import Image from 'next/image';



import RectangleImage from '@app/assets/image/rectangle.png';
import { Button } from '@app/shadcn/components/ui/button';
import { Input } from '@app/shadcn/components/ui/input';


const WelcomeSlide = ({ disabled }: { disabled?: boolean }) => {
    return (
        <div
            className={`flex aspect-video h-min w-full bg-blue-100  ${disabled ? 'pointer-events-none overflow-hidden' : ''}`}
        >
            <div className=" flex basis-1/2 flex-col items-start justify-center gap-12 px-12">
                <input
                    type="text"
                    placeholder="Form Title"
                    className="border-0 px-0 text-[40px] font-bold"
                />
                <Button size={'medium'}>Start</Button>
            </div>
            <Image
                objectFit="cover"
                className="basis-1/2"
                src={RectangleImage}
                alt="LayoutImage"
            />
        </div>
    );
};

export default WelcomeSlide;
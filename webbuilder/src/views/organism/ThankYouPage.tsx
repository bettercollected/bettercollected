import Image from 'next/image';

import RectangleImage from '@app/assets/image/rectangle.png';
import { Button } from '@app/shadcn/components/ui/button';
import { Input } from '@app/shadcn/components/ui/input';

const ThankYouSlide = ({ disabled }: { disabled?: boolean }) => {
    return (
        <div
            className={`flex aspect-video h-min w-full bg-blue-100  ${disabled ? 'pointer-events-none overflow-hidden' : ''}`}
        >
            <div className=" flex basis-1/2 flex-col items-start justify-center gap-12 px-12">
                <div className="flex w-full flex-col">
                    <h1 className="text-2xl font-semibold">Thank You!</h1>
                    <input
                        type="text"
                        value="Your response has been successfully submitted"
                        className="border-0 px-0"
                    />
                </div>
                <Button size={'medium'}>Try bettercollected</Button>
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

export default ThankYouSlide;

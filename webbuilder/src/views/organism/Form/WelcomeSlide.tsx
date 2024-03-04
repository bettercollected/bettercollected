import { useState } from 'react';

import Image from 'next/image';
import Link from 'next/link';

import { PopoverContent } from '@radix-ui/react-popover';
import { ChevronDown, Globe, Lock, UserRoundPlus } from 'lucide-react';

import DemoImage from '@app/assets/image/rectangle.png';
import { Button } from '@app/shadcn/components/ui/button';
import { Popover, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { cn } from '@app/shadcn/util/lib';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';

export default function WelcomeSlide() {
    const { standardForm } = useStandardForm();
    const { nextSlide } = useFormResponse();

    const [popOverOpen, setPopoverOpen] = useState(false);

    return (
        <div className="grid h-full w-full grid-cols-2">
            <div className=" relative flex h-full flex-col justify-center px-20">
                <Popover open={popOverOpen} onOpenChange={setPopoverOpen}>
                    <PopoverTrigger className="absolute right-10 top-4">
                        <div className="flex cursor-pointer  items-center rounded-full bg-black-400 p-1">
                            <UserRoundPlus className="rounded-full bg-black-500 p-1 text-white" />
                            <ChevronDown
                                className={cn(
                                    ' pt-1 text-black-600 transition',
                                    popOverOpen && 'rotate-180'
                                )}
                            />
                        </div>
                    </PopoverTrigger>
                    <PopoverContent className="p2-new shadow-blue-hue z-[10] mt-2 max-w-[235px] rounded-lg bg-white p-4 text-black-700">
                        Do you wish to track your form response for future reference?
                    </PopoverContent>
                </Popover>

                <div className="text-[40px] font-bold leading-[48px]">
                    {standardForm.title}
                </div>
                {standardForm?.description && (
                    <div className="mt-4 text-black-700 ">
                        {standardForm?.description}
                    </div>
                )}
                <div className="mt-16 flex max-w-[421px] flex-col rounded-lg bg-white p-4">
                    <div className="flex items-center gap-2">
                        {standardForm?.settings?.requireVerifiedIdentity ? (
                            <>
                                <div className="rounded-full bg-red-100 p-[5px]">
                                    <Lock color="#EA400E" />
                                </div>
                                <span>This form is private</span>
                            </>
                        ) : (
                            <>
                                <div className="rounded-full bg-green-100 p-[5px]">
                                    <Globe color="#2DBB7F" />
                                </div>
                                <span>This form is public</span>
                            </>
                        )}
                    </div>
                    <div className="mt-2 text-xs text-black-700">
                        {standardForm?.settings?.requireVerifiedIdentity ? (
                            <>
                                The form you are trying to access is limited to certain
                                groups. Please verify your account to get access.
                            </>
                        ) : (
                            <>
                                The form you are trying to access is public, but you can
                                always sign in to view your response later.{' '}
                                <span>
                                    <Link href={'/login'} className="text-blue-500 ">
                                        {' '}
                                        Verify Account
                                    </Link>
                                </span>
                            </>
                        )}
                    </div>
                </div>
                <div className="mt-6">
                    <Button
                        onClick={() => {
                            if (!standardForm?.settings?.requireVerifiedIdentity) {
                                nextSlide();
                                return;
                            }
                        }}
                    >
                        {standardForm?.settings?.requireVerifiedIdentity
                            ? 'Verify Now'
                            : 'Start'}
                    </Button>
                </div>
            </div>
            <div className="relative h-full w-full">
                <Image
                    src={DemoImage}
                    alt="Demo Image"
                    fill
                    style={{
                        objectFit: 'cover'
                    }}
                    priority
                    sizes="(min-w: 0px) 100%"
                />
            </div>
        </div>
    );
}

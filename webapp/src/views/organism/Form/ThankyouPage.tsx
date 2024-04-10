import Link from 'next/link';

import { ButtonSize } from '@app/models/enums/button';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import UserAvatarDropDown from '@app/views/molecules/UserAvatarDropdown';

export default function ThankyouPage({ isPreviewMode }: { isPreviewMode: boolean }) {
    const { standardForm } = useStandardForm();
    return (
        <div
            className={cn(
                'flex h-full w-full flex-col justify-center',
                standardForm?.thankyouPage![0]?.layout ===
                    FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN
                    ? 'items-start'
                    : 'items-center'
            )}
            style={{ background: standardForm.theme?.accent }}
        >
            <UserAvatarDropDown disabled />
            <div className=" flex h-full w-full max-w-[800px] flex-col justify-center">
                <div className="">
                    <div className="flex">
                        <span className="text-[40px] font-bold leading-[48px]">
                            Thank You! 🎉
                        </span>
                    </div>
                    <div className="p2-new mt-4 text-black-700">
                        {standardForm?.thankyouPage?.[0]?.message ||
                            'Your response is successfully submitted anonymously.'}
                    </div>
                    {/* <Button
                        style={{ background: standardForm.theme?.secondary }}
                        className="mt-14"
                        size={ButtonSize.Medium}
                    >
                        <Link
                            href={
                                isPreviewMode
                                    ? ''
                                    : standardForm?.buttonLink ||
                                      'https://bettercollected.com'
                            }
                            target="_blank"
                            referrerPolicy="no-referrer"
                        >
                            {standardForm?.buttonText || 'Try Bettercollected'}
                        </Link>
                    </Button> */}
                    <div className="p2-new mt-10 max-w-[400px] rounded-lg bg-white p-4">
                        <div className=" text-black-700">
                            You can view or request deletion of this response.
                        </div>
                        <div>
                            <Link
                                href={isPreviewMode ? '' : 'https://youtube.com'}
                                className="text-blue-500"
                            >
                                See all your submissions
                            </Link>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
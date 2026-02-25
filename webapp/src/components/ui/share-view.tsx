import { ReactNode } from 'react';

import cn from 'classnames';
import { FacebookShareButton, LinkedinShareButton, TwitterShareButton } from 'react-share';

import { Facebook } from '@app/Components/icons/brands/facebook';
import { Linkedin } from '@app/Components/icons/brands/linkedin';
import { Twitter } from '@app/Components/icons/brands/twitter';
import LinkView from '@app/Components/ui/link-view';

type SizeNames = 'large' | 'small';

interface Props {
    url: string;
    title?: string;
    showCopy?: boolean;
    iconSize?: SizeNames;
    className?: string;
}

const sizes: Record<SizeNames, string> = {
    large: 'h-9 w-9 mr-5',
    small: 'h-[26px] w-[26px] mr-2'
};

interface IconWrapperProps {
    children: ReactNode;
    showBorder?: boolean;
    className?: string;
}

export const IconWrapper = ({ children, className = '' }: IconWrapperProps) => <span className={`text-md flex items-center justify-center p-[2px]  ${className}`}>{children}</span>;

export default function ShareView({ url, title, showCopy = true, iconSize = 'large', className }: Props) {
    return (
        <div className={className}>
            <p className={cn('!leading-none -tracking-wide text-gray-900 ltr:text-left rtl:text-right  dark:text-white', showCopy ? 'sh1' : 'body1')}>{title}</p>
            <div className="flex flex-col gap-5 md:gap-10">
                <div className="product-share mt-6 flex flex-shrink-0 flex-wrap items-center ">
                    <TwitterShareButton url={url}>
                        <IconWrapper>
                            <Twitter className={sizes[iconSize]} />
                        </IconWrapper>
                    </TwitterShareButton>
                    <FacebookShareButton url={url}>
                        <IconWrapper>
                            <Facebook className={sizes[iconSize]} />
                        </IconWrapper>
                    </FacebookShareButton>
                    <LinkedinShareButton url={url}>
                        <IconWrapper>
                            <Linkedin className={sizes[iconSize]} />
                        </IconWrapper>
                    </LinkedinShareButton>
                </div>
                {showCopy && <LinkView className="flex flex-col items-center md:flex-row " buttonClassName="!h-[46px]  sh3 !font-medium !bg-brand-500 hover:!bg-brand-600 !text-white !px-8 !py-2" url={url} toastMessage={'Copied'}></LinkView>}
            </div>
        </div>
    );
}

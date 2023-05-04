import React, { ReactNode, useState } from 'react';

import { FacebookShareButton, LinkedinShareButton, TelegramShareButton, TwitterShareButton } from 'react-share';
import { useCopyToClipboard } from 'react-use';

import { Facebook } from '@app/components/icons/brands/facebook';
import { Linkedin } from '@app/components/icons/brands/linkedin';
import { Telegram } from '@app/components/icons/brands/telegram';
import { Twitter } from '@app/components/icons/brands/twitter';
import { Copy } from '@app/components/icons/copy';

type SizeNames = 'large' | 'small';
interface Props {
    url: string;
    title?: string;
    showCopy?: boolean;
    showBorder?: boolean;
    iconSize?: SizeNames;
}

const sizes: Record<SizeNames, string> = {
    large: 'h-9 w-9 pr-5',
    small: 'h-[26px] w-[26px] pr-2'
};

ShareView.defaultProps = {
    title: '',
    showCopy: true,
    showBorder: true
};

interface IconWrapperProps {
    children: ReactNode;
    showBorder?: boolean;
    className?: string;
}

export const IconWrapper = ({ children, showBorder, className = '' }: IconWrapperProps) => <span className={`text-md flex items-center p-[2px] justify-center  ${className}`}>{children}</span>;

IconWrapper.defaultProps = {
    showBorder: true
};
export default function ShareView({ url, title, showCopy, showBorder, iconSize = 'large' }: Props) {
    let [copyButtonStatus, setCopyButtonStatus] = useState('Copy');
    let [_, copyToClipboard] = useCopyToClipboard();
    const handleCopyToClipboard = () => {
        copyToClipboard(url);
        setCopyButtonStatus('Copied!');
        setTimeout(() => {
            setCopyButtonStatus(copyButtonStatus);
        }, 1000);
    };
    return (
        <div>
            <div className="-tracking-wide text-gray-900 ltr:text-left rtl:text-right dark:text-white body1 !leading-none">Share {title}</div>
            <div className="flex flex-wrap gap-3 pt-4 md:gap-4 xl:pt-[18px]">
                <div className="product-share flex flex-shrink-0 flex-wrap items-center gap-3 md:gap-4">
                    <TwitterShareButton url={url}>
                        <IconWrapper>
                            <Twitter className={sizes[iconSize]} />
                        </IconWrapper>
                    </TwitterShareButton>
                    <FacebookShareButton url={url}>
                        <IconWrapper>
                            <Facebook className={iconSize} />
                        </IconWrapper>
                    </FacebookShareButton>
                    <LinkedinShareButton url={url}>
                        <IconWrapper>
                            <Linkedin className={iconSize} />
                        </IconWrapper>
                    </LinkedinShareButton>
                    <TelegramShareButton url={url}>
                        <IconWrapper>
                            <Telegram className={iconSize} />
                        </IconWrapper>
                    </TelegramShareButton>
                </div>
            </div>
        </div>
    );
}

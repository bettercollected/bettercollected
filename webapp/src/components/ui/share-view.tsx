import React, { ReactNode } from 'react';

import cn from 'classnames';
import { FacebookShareButton, LinkedinShareButton, TelegramShareButton, TwitterShareButton } from 'react-share';

import { Facebook } from '@app/components/icons/brands/facebook';
import { Linkedin } from '@app/components/icons/brands/linkedin';
import { Telegram } from '@app/components/icons/brands/telegram';
import { Twitter } from '@app/components/icons/brands/twitter';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import LinkView from '@app/components/ui/link-view';
import environments from '@app/configs/environments';
import { workspaceCustomizeLink } from '@app/constants/Customize-domain';

type SizeNames = 'large' | 'small';
interface Props {
    url: string;
    title?: string;
    showCopy?: boolean;
    iconSize?: SizeNames;
}

const sizes: Record<SizeNames, string> = {
    large: 'h-9 w-9 mr-5',
    small: 'h-[26px] w-[26px] mr-2'
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

export const IconWrapper = ({ children, className = '' }: IconWrapperProps) => <span className={`text-md flex items-center p-[2px] justify-center  ${className}`}>{children}</span>;

export default function ShareView({ url, title, showCopy, iconSize = 'large' }: Props) {
    const { openModal } = useModal();
    return (
        <div>
            <p className={cn('-tracking-wide text-gray-900 ltr:text-left rtl:text-right dark:text-white  !leading-none', showCopy ? 'sh1' : 'body1')}>Share {title}</p>
            <div className="flex flex-col gap-5 flex-wrap md:gap-10">
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
                    <TelegramShareButton url={url}>
                        <IconWrapper>
                            <Telegram className={sizes[iconSize]} />
                        </IconWrapper>
                    </TelegramShareButton>
                </div>
                {showCopy && <LinkView buttonSize="medium" className="flex md:flex-row flex-col items-center " url={url} toastMessage="Copied!" buttonVarient="solid"></LinkView>}
                {/* {showCopy && (
                    <div>
                        <Button variant="transparent" className="!text-brand-500" onClick={() => openModal('CUSTOMIZE_URL', { description: workspaceCustomizeLink.description, url: environments.CLIENT_DOMAIN })}>
                            Customize your link
                        </Button>
                    </div>
                )} */}
            </div>
        </div>
    );
}

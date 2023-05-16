import React, { ReactNode } from 'react';

import { useTranslation } from 'next-i18next';

import cn from 'classnames';
import { FacebookShareButton, LinkedinShareButton, TelegramShareButton, TwitterShareButton } from 'react-share';

import { Facebook } from '@app/components/icons/brands/facebook';
import { Linkedin } from '@app/components/icons/brands/linkedin';
import { Telegram } from '@app/components/icons/brands/telegram';
import { Twitter } from '@app/components/icons/brands/twitter';
import { useModal } from '@app/components/modal-views/context';
import LinkView from '@app/components/ui/link-view';
import { localesGlobal } from '@app/constants/locales/global';
import { toastMessage } from '@app/constants/locales/toast-message';

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
    const { t } = useTranslation();
    return (
        <div>
            <p className={cn('-tracking-wide text-gray-900 ltr:text-left rtl:text-right dark:text-white  !leading-none', showCopy ? 'sh1' : 'body1')}>{title}</p>
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
                {showCopy && <LinkView className="flex md:flex-row flex-col items-center " buttonClassName="!h-[46px] sh3 !font-medium !bg-brand-500 hover:!bg-brand-600 !text-white !px-8 !py-2" url={url} toastMessage={t(toastMessage.copied)}></LinkView>}
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

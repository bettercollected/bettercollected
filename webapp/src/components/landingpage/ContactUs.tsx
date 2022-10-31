import { useState } from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';

import Iframe from '@app/components/landingpage/Iframe';
import LandingPageSectionContainer from '@app/components/landingpage/LandingPageSectionContainer';
import FormInput from '@app/components/ui/FormInput';
import FormRenderer from '@app/components/ui/FormRenderer';
import HeadingRenderer from '@app/components/ui/HeadingRenderer';
import environments from '@app/configs/environments';
import useDimension from '@app/hooks/useDimension';

import ContactImage from '../../../public/contact_us.svg';

/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 15:04
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

export default function ContactUs() {
    const { t } = useTranslation();

    const dimensions = useDimension();

    const [formFields, setFormFields] = useState({
        fullname: '',
        email: '',
        message: ''
    });

    const [showIframe, setShowIframe] = useState(false);

    //TODO api call
    const handleSubmit = (e: any) => {
        e.preventDefault();
        setShowIframe(true);
        console.log('submit:', formFields);
    };

    const handleAllFieldChanges = (id: string, value: any) => {
        setFormFields({ ...formFields, [id]: value });
    };

    return (
        <>
            {showIframe && <Iframe formUrl={`${environments.CONTACT_US_URL}&emailAddress=${formFields.email}&entry.44753521=${formFields.fullname}&entry.1588378982=${formFields.message}`} handleClose={() => setShowIframe(false)} />}
            <LandingPageSectionContainer sectionId={'contact'}>
                <HeadingRenderer description={t('CONTACT_US_DESCRIPTION')}>{t('CONTACT_US')}</HeadingRenderer>
                <div className={'lg:flex lg:items-center shadow-md'}>
                    {dimensions.width <= 1024 ? (
                        <></>
                    ) : (
                        <div className={"h-full w-full p-4 bg-[url('/contact_us.svg')] bg-no-repeat bg-center bg-cover"}>
                            <h2 className={'text-white font-semibold text-sm md:text-md lg:text-2xl text-center'}>Leave us a message!</h2>
                        </div>
                    )}

                    <div className={'m-auto lg:flex-shrink-0 lg:flex-grow-0 lg:basis-[50%]'}>
                        <FormRenderer handleSubmit={handleSubmit}>
                            <h2 className={'text-roboto font-semibold text-xl md:text-2xl lg:text-3xl text-center'}>Enter your information</h2>
                            <FormInput label={'Your Name'} placeholder={'Your full name'} id={'fullname'} handleChange={handleAllFieldChanges} />
                            <FormInput label={'Email Address'} placeholder={'Enter your email address'} id={'email'} handleChange={handleAllFieldChanges} />
                            <div className={'flex flex-col mb-3'}>
                                <label className={'block text-gray-700 text-sm font-normal mb-2'} htmlFor={'message'}>
                                    Message
                                </label>
                                <textarea id={'message'} className="resize rounded-md pl-2 border h-[100px]" placeholder={'Enter your message'} onChange={(e) => handleAllFieldChanges(e.currentTarget.id, e.target.value)}></textarea>
                            </div>
                        </FormRenderer>
                    </div>
                </div>
            </LandingPageSectionContainer>
        </>
    );
}

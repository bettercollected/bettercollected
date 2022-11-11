/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 13:25
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import { useState } from 'react';

import { useTranslation } from 'next-i18next';
import Image from 'next/image';

import BannerImage from '@app/assets/svgs/BannerImage.svg';
import LandingPageSectionContainer from '@app/components/landingpage/LandingPageSectionContainer';
import DialogRenderer from '@app/components/ui/DialogRenderer';
import FormInput from '@app/components/ui/FormInput';
import FormRenderer from '@app/components/ui/FormRenderer';
import HeadingRenderer from '@app/components/ui/HeadingRenderer';
import environments from '@app/configs/environments';
import FlexRowContainer from '@app/containers/landingpage/FlexRowContainer';

export default function WaitlistForm() {
    const { t } = useTranslation();

    const [openDialog, setOpenDialog] = useState(false);

    const [formFields, setFormFields] = useState({
        firstname: '',
        lastname: '',
        email: ''
    });

    const handleSubmit = async (e: any) => {
        e.preventDefault();
        const bodyContent = {
            first_name: formFields.firstname,
            last_name: formFields.lastname,
            email: formFields.email
        };

        try {
            const res = await fetch(`http://localhost:8000/users/waitlist`, {
                method: 'POST',
                mode: 'cors',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(bodyContent)
            });
            setOpenDialog(true);
        } catch (e: any) {
            alert('Something went wrong!');
        }
    };

    const handleAllFieldChanges = (id: string, value: any, validateInput: any) => {
        setFormFields({ ...formFields, [id]: value });
    };

    const closeDialog = () => setOpenDialog(false);

    const shouldSubmitButtonDisable = () => {
        const pattern = /^\w+@[a-zA-Z_]+?\.[a-zA-Z]{2,3}$/;
        return !formFields.email.match(pattern);
    };

    function FormDescription() {
        return (
            <>
                <div className={'font-semibold text-3xl text-blue-500 mb-2'}>Get early access!</div>
                <div className={'font-medium font-roboto font-display text-gray-400 text-xl mb-5'}>
                    Be one of the first to create a profile and claim a basic plan for <b>free</b>.
                </div>
            </>
        );
    }

    return (
        <LandingPageSectionContainer sectionId={'waitlist'}>
            <HeadingRenderer>Waitlist</HeadingRenderer>
            {openDialog && <DialogRenderer title={'Confirmation'} description={'Message is sent successfully'} handleClose={closeDialog} />}
            <FlexRowContainer>
                <div>
                    <Image src={BannerImage} alt={'Forms'} />
                </div>
                <FormRenderer handleSubmit={handleSubmit} shouldButtonDisable={shouldSubmitButtonDisable()}>
                    <FormDescription />
                    <div className={'flex mb-4 gap-3'}>
                        <FormInput label={'Your First Name'} placeholder={'Enter your first name'} id={'firstname'} handleChange={handleAllFieldChanges} />
                        <FormInput label={'Your Last Name'} placeholder={'Enter your last name'} id={'lastname'} handleChange={handleAllFieldChanges} />
                    </div>
                    <FormInput label={'Email Address'} placeholder={'Enter your email address'} id={'email'} handleChange={handleAllFieldChanges} />
                </FormRenderer>
            </FlexRowContainer>
        </LandingPageSectionContainer>
    );
}

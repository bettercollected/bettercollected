import { useState } from 'react';

import Image from 'next/image';

import styled from '@emotion/styled';
import TextField from '@mui/material/TextField';

import Button from '@app/components/ui/button';

import { useModal } from './modal-views/context';

const StyledTextField = styled.div`
    .MuiFormControl-root {
        background: white;
    }
`;

function OtpRenderer() {
    return (
        <form
            // onSubmit={event => {
            //   event.preventDefault();
            //   onSubmit();
            // }}
            className={'mr-10 flex flex-col space-y-sm'}
        >
            <div className={'font-semibold text-darkGrey rounded-md text-xl'}>Enter Verification code</div>

            <div className={' text-sm text-gray-600 md:text-base'}>
                {' '}
                We have just send the verification code to
                <br />
                {/* <span className="font-semibold">{' ' + verifyEmail}.</span> */}
            </div>
            <div className={`border-gray-900'} flex   w-full flex-row items-center rounded  border px-base  py-xs`}>
                <input
                    id={'otp_input'}
                    placeholder="Enter OTP code"
                    className="border-none  p-1 outline-none focus:bg-white"
                    // onChange={validationOtp}
                    // value={otpCode}
                />
            </div>
            <button
                //   disabled={loading}
                className={`flex w-full items-center justify-center rounded bg-green_btn px-base py-sm pl-lg font-semibold text-white ${true && 'cursor-not-allowed opacity-40'}`}
                //   onClick={() => onSubmit()}
            >
                <span className={'mr-sm'}>Verify</span>
                <div className={'flex w-5 items-center'}>
                    {/* {loading && (
                  <Image
                    src={'/gifs/spinner.gif'}
                    alt="loading"
                    width={'20px'}
                    height={'20px'}
                  />
                )} */}
                </div>
            </button>
            <div className={'text-md align flex cursor-pointer  items-center justify-center text-primary hover:text-blue-500 hover:underline'}>
                {/* <span>
                <Button
                  type="text"
                  disabled={showCountDown}
                  onClick={() => {
                    ApiOps.sendOtpToMail(verifyEmail);
                    setCountDown(Date.now() + 60 * 1000);
                    // setShowCountdown(true);
                  }}
                >
                  Resend code
                </Button>
              </span>{' '} */}
                <div>Resend code</div>
                {/* {showCountDown ? (
                <Countdown
                  valueStyle={{ fontSize: 'medium' }}
                  format={'mm:ss'}
                  value={countDown}
                  onFinish={() => {
                    setShowCountdown(false);
                  }}
                />
              ) : (
                <div className={'w-10'}></div>
              )} */}
            </div>
        </form>
    );
}

function LoginForm() {
    const [emailInput, setEmailInput] = useState('');
    return (
        <div className="flex flex-col justify-center">
            <div className={'font-semibold text-darkGrey rounded-md text-2xl'}>Login</div>
            <StyledTextField>
                <TextField size="small" name="email-input" placeholder="Enter your email" value={emailInput} onChange={(e) => setEmailInput(e.target.value)} />
            </StyledTextField>
            <Button variant="solid" className="mt-2 mb-0" onClick={() => console.log(emailInput)}>
                Send
            </Button>
        </div>
    );
}

function ImageRender() {
    return (
        <div className="max-w-full lg:max-w-[200px]">
            <Image src={'/otp.svg'} width={'200px'} height={'200px'} />
        </div>
    );
}

function LoginContainer() {
    const { closeModal } = useModal();
    return (
        <div className=" m-auto max-w-[500px] items-start justify-between rounded-lg bg-white lg:scale-150">
            <div className="flex flex-row gap-8 items-center justify-between p-10">
                {/* <LoginForm/> */}
                <OtpRenderer />
                <ImageRender />
            </div>
            <div className="cursor-pointer absolute top-3 right-3 text-gray-600 hover:text-black" onClick={() => closeModal()}>
                X
            </div>
        </div>
    );
}

export default function LoginView({ ...props }) {
    return (
        <div className="relative z-50 mx-auto max-w-full min-w-full md:max-w-[600px] lg:max-w-[600px]" {...props}>
            <LoginContainer />
        </div>
    );
}

import React from 'react';

import BackButtonMenuBar from '@Components/Common/BackButtonMenuBar';
import AppTextField from '@Components/Common/Input/AppTextField';
import UploadLogo from '@Components/Common/UploadLogo';

export default function OnBoardingPage() {
    return (
        <div className="bg-white h-screen">
            <BackButtonMenuBar text="Back" />
            <div className="pt-10 w-full h-full flex flex-col items-center">
                <div className="flex flex-col items-start">
                    <div className="h3-new">Add Your Organization</div>
                    <UploadLogo className="mt-12" />
                    <form className="mt-8 w-[541px] space-y-10">
                        <AppTextField required title="Organization Name" placeholder="Enter name of your workspace" />
                        <AppTextField required title="Handle Name" placeholder="Enter workspace handle name">
                            <AppTextField.Description>Use smallcase for your handle name (eg: abc)</AppTextField.Description>
                        </AppTextField>
                        <AppTextField required title="Add Your Organization Description" placeholder="Write Description" multiline />
                    </form>
                </div>
            </div>
        </div>
    );
}

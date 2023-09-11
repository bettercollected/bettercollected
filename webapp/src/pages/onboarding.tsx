import React from 'react';

import BackButtonMenuBar from '@Components/Common/BackButtonMenuBar';
import { FormLogoComponent } from '@Components/FormBuilder/Header';

export default function OnBoardingPage() {
    return (
        <div>
            <BackButtonMenuBar text="Back" />
            <div>
                <div className="h3-new">Add Your Organization</div>
                <FormLogoComponent className="mt-12" setIsLogoClicked={() => {}} imagesRemoved={} setImagesRemoved={() => {}} />
            </div>
        </div>
    );
}

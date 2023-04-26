import React, { useEffect } from 'react';

import FormDrawer from '@app/components/sidebar/form-drawer';
import MuiDrawer from '@app/components/sidebar/mui-drawer';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import { initialFormState, setForm } from '@app/store/forms/slice';
import { useAppDispatch } from '@app/store/hooks';

export default function FormPageLayout(props: any) {
    const { form } = props;
    const dispatch = useAppDispatch();

    useEffect(() => {
        dispatch(setForm(form));
        return () => {
            dispatch(setForm(initialFormState));
        };
    }, []);

    return (
        <SidebarLayout DrawerComponent={FormDrawer}>
            <div className="relative">
                <div className="absolute lg:left-[-40px] px-5 lg:px-10 pb-10 top-0 w-full py-6 xl:max-w-289-calc-289">{props.children}</div>
                <MuiDrawer drawer={<></>} anchor="right" handleDrawerToggle={() => {}} />
            </div>
        </SidebarLayout>
    );
}

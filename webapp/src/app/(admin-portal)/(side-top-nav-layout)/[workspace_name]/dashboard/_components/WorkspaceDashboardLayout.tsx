"use client";

import SidebarLayoutApp from '@Components/sidebar/SidebarLayoutApp';
import React from 'react';



const WorkspaceDashboardLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {

    return (
        <SidebarLayoutApp boxClassName="px-5 lg:px-10 pt-10">
            {children}
        </SidebarLayoutApp>
    );

};

export default WorkspaceDashboardLayout;
import React from 'react';

import SidebarExpandable from './_expandable';
import Aside from './aside';

export default function Layout(props: any) {
    const children = props.children;
    return (
        <div className={`relative flex flex-1 flex-col md:flex-row`}>
            <div className="absolute z-0 overflow-hidden inset-0">
                <div className="absolute top-[60%] left-[-100px] w-[359px] h-[153px] bg-gradient-to-r from-orange-200 via-orange-300 to-orange-400 rotate-90 blur-dashboardBackground opacity-[20%]" />
                <div className="absolute top-[35%] left-[65%] w-[765px] h-[765px] bg-gradient-to-r from-cyan-300 via-sky-300 to-cyan-400 blur-dashboardBackground opacity-[15%]" />
                <div className="absolute bottom-0 left-[50%] w-[599px] h-[388px] bg-gradient-to-r from-rose-200 via-rose-300 to-rose-400 rotate-180 blur-dashboardBackground opacity-[20%]" />
            </div>
            <aside className="border-r-[1px] border-solid border-r-[#eaeaea] z-20 hidden w-[calc(3.75rem)] h-screen hover:max-h-[100vh] hov:min-h-[100vh] overflow-auto md:block md:w-[300px]">
                <Aside />
            </aside>
            <main className={`rem-screen-main relative top-0 flex-1 overflow-auto px-10 py-10 md:px-10`}>{children}</main>
        </div>
    );
}

// export default function Layout(props: any) {
//     const children = props.children;
//     return (
//         <div className="ltr:xl:pl-24 rtl:xl:pr-24 ltr:2xl:pl-28 rtl:2xl:pr-28">
//             <SidebarExpandable />
//         </div>
//     );
// }

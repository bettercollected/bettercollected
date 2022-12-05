// import { useEffect, useState } from 'react';

// import { useRouter } from 'next/router';

// export default function AuthHoc(props: any) {
//     const router = useRouter();

//     const [postStatus, statusResponse] = usePostStatusMutation();

//     useEffect(() => {
//         authCheck();
//     }, [router.asPath]);

//     async function authCheck() {
//         try {
//             const result = await postStatus().unwrap();
//             console.log('response: ', statusResponse);
//         } catch (e) {
//             console.log('failed: ', e);
//         }
//     }

//     return <>{props.children}</>;
// }

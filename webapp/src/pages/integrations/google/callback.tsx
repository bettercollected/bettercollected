import {useEffect} from "react";

const OAuthCallback = (props: any) => {
    useEffect(() => {
        const parentWindow = window.opener
        if (parentWindow) {
            // Send a message to the parent window
            parentWindow.postMessage(props.query, '*');
        } else {
            console.error('Parent window reference is not available.');
        }
        window.close();
    }, [props.query]);


    return <></>
}

export async function getServerSideProps(context: any) {
    const {query} = context;
    return {
        props: {
            query,
        },
    };
}

export default OAuthCallback
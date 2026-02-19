import React from 'react';
import { notFound } from 'next/navigation';
import MembersLayoutClient from './_components/MembersLayoutClient';

export default async function Layout(
    props: { children: React.ReactNode; params: Promise<{ workspace_name: string }> }
) {
    const params = await props.params;

    const {
        children
    } = props;

    return (
        <MembersLayoutClient children={children} params={params} />
    );
}

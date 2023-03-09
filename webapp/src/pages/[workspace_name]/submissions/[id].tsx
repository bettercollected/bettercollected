import React from 'react';

import Submission from '@app/pages/submissions/[id]';

export default Submission;

export { getServerSidePropsInClientHostWithWorkspaceName as getServerSideProps } from '@app/utils/serverSidePropsUtils';

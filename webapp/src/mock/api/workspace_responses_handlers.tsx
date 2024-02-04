import { rest } from 'msw';

import { standardResponseMock } from '@app/mock/data/standard-response-mock';


export const workspace_responses_handlers = [
    rest.get('http://localhost:8080/workspaces/:workspace_id/submissions', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: [standardResponseMock]
                }
            })
        );
    }),
    rest.get('http://localhost:8080/workspaces/:workspace_id/allSubmissions', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: [standardResponseMock]
                }
            })
        );
    }),
    rest.get('http://localhost:8080/workspaces/:workspace_id/submissions/:submission_id', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: standardResponseMock
                }
            })
        );
    })
];
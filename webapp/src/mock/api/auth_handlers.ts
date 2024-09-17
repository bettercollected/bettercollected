import { rest } from 'msw';

export const auth_handlers = [
    rest.get('http://localhost:8000/auth/status', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: {
                        user: {
                            id: '63ca5518b613f81e118e3d8c',
                            sub: 'ankit.sapkota555@gmail.com',
                            roles: ['FORM_RESPONDER', 'FORM_CREATOR'],
                            services: ['typeform', 'google']
                        }
                    }
                }
            })
        );
    }),
    rest.post('http://localhost:8000/auth/otp/send', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: {
                        message: 'Email sent successfully.',
                        email: 'ankit.sapkota555@gmail.com'
                    }
                }
            })
        );
    }),
    rest.post('http://localhost:8000//workspaces/:workspace_id/auth/otp/send', (req, res, context) => {
        return res(
            context.json({
                payload: {
                    content: {
                        message: 'Email sent successfully.',
                        email: 'ankit.sapkota555@gmail.com'
                    }
                }
            })
        );
    }),
    rest.get('http://localhost:8000/auth/logout', (req, res, context) => {
        return res(context.json('success'));
    })
];
import asyncio
import csv
import json
import os
import re
from typing import List, Optional

import boto3
from fastapi_mail import ConnectionConfig, MessageSchema, FastMail, MessageType

import settings.application
from settings.application import settings
from wrappers.thread_pool_executor import thread_pool_executor


async def execute_csv_conversion(form: str, unconverted_responses: List[str]):
    form = json.loads(form)
    responses = []
    for response in unconverted_responses:
        responses.append(json.loads(response))

    def get_responses_answers(response, question_answers, fields):
        form_builder_tag_names = {
            'INPUT_RATING': 'input_rating',
            'INPUT_NUMBER': 'input_number',
            'INPUT_SHORT_TEXT': 'input_short_text',
            'INPUT_LONG_TEXT': 'input_long_text',
            'INPUT_LINK': 'input_link',
            'INPUT_EMAIL': 'input_email',
            'INPUT_DATE': 'input_date',
            'INPUT_MULTIPLE_CHOICE': 'input_multiple_choice',
            'INPUT_DROPDOWN': 'input_dropdown',
            'INPUT_CHECKBOXES': 'input_checkboxes',
            'INPUT_PHONE_NUMBER': 'input_phone_number',
            'INPUT_RANKING': 'input_ranking',
            'INPUT_FILE_UPLOAD': 'input_file_upload'
        }
        answers = []
        for question in question_answers:
            field_id = question.get('field_id')
            answer = response['answers'].get(field_id)
            question_type = question.get('type')
            if not answer:
                answers.append('')
            elif (question_type == form_builder_tag_names['INPUT_SHORT_TEXT'] or
                  question_type == form_builder_tag_names['INPUT_LONG_TEXT']):
                answers.append(answer.get('text'))
            elif question_type == form_builder_tag_names['INPUT_EMAIL']:
                answers.append(answer.get('email'))
            elif question_type == form_builder_tag_names['INPUT_FILE_UPLOAD']:
                answers.append(answer.get('file_metadata').get('name'))
            elif (question_type == form_builder_tag_names['INPUT_NUMBER'] or
                  question_type == form_builder_tag_names['INPUT_RATING']):
                answers.append(answer.get('number'))
            elif question.get('type') == form_builder_tag_names['INPUT_LINK']:
                answers.append(answer.get('url'))
            elif question_type == form_builder_tag_names['INPUT_DATE']:
                answers.append(answer.get('date'))
            elif question_type == form_builder_tag_names['INPUT_PHONE_NUMBER']:
                answers.append(answer.get('phone_number'))
            elif question_type == form_builder_tag_names['INPUT_CHECKBOXES']:
                answers.append(
                    get_choices_values(answer.get('choices').get('values'), get_current_field(field_id, fields)))
            elif question_type == form_builder_tag_names['INPUT_MULTIPLE_CHOICE']:
                answers.append(
                    get_choice_value(answer.get('choice').get('value'), get_current_field(field_id, fields)))
            elif question_type == form_builder_tag_names['INPUT_DROPDOWN']:
                answers.append(
                    get_choice_value(answer.get('choice').get('value'), get_current_field(field_id, fields)))
            elif question_type == form_builder_tag_names['INPUT_RANKING']:
                answers.append(get_values_for_ranking(answer.get('choices').get('values')))
            else:
                answers.append('')
        return answers

    def get_values_for_ranking(rankings):
        return [ranking['value'] for ranking in rankings]

    def get_choice_value(choice_id, field):
        if matches_uuid_pattern(choice_id):
            for choice in field['properties']['choices']:
                if str(choice['id']) == choice_id:
                    return choice['value']
        else:
            return choice_id

    def get_choices_values(choices, field):
        choices_value = []
        for choice_id in choices:
            choices_value.append(get_choice_value(choice_id, field))
        return choices_value

    def matches_uuid_pattern(string):
        pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        return bool(re.match(pattern, string))

    def get_current_field(field_id, fields):
        for field in fields:
            if field['id'] == field_id:
                return field

    def get_simple_form_responses(form, responses):
        field_lists = list(form['fields'])
        question_answers = []
        question_csv = []
        answer_csv = []
        for question_index, field in enumerate(form['fields']):
            if field['type'].startswith('input_'):
                x = dict()
                x['field_id'] = field['id']
                x['text'] = field['properties']['placeholder']
                x['type'] = field['type']
                if field_lists[question_index - 1]['value']:
                    x['text'] = field_lists[question_index - 1]['value']
                question_answers.append(x)
                question_csv.append(x['text'])
        answer_csv.append(question_csv)
        for response in responses:
            answer_csv.append(get_responses_answers(response, question_answers, form['fields']))

        filename = f'{form["form_id"]}.csv'
        with open(filename, mode='w') as employee_file:
            employee_writer = csv.writer(employee_file, delimiter=',')
            for answer in answer_csv:
                employee_writer.writerow(answer)

        s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.region_name,
            endpoint_url=settings.endpoint_url
        )

        s3.put_object(
            Bucket=settings.bucket_name,
            Key=f"csv/{filename}",
            Body=open(filename, 'rb'),
            ACL="private"
        )

        presigned_csv_url = s3.generate_presigned_url(
            ClientMethod='get_object',
            Params={'Bucket': settings.bucket_name, 'Key': f"csv/{filename}"},
            ExpiresIn=settings.expiration_time
        )

        # for sending file as attachment
        # upload_file = UploadFile(filename=filename, file=open(filename, 'rb'))

        mail_config = config_mail(settings.smtp_username, settings.smtp_password, settings.smtp_sender,
                                  settings.smtp_port,
                                  settings.smtp_server)

        message = MessageSchema(
            subject="Responses CSV Attachment",
            recipients=["sitalnagarkoti123@gmail.com"],
            body=f"Please find the attached CSV file link below. <br> {presigned_csv_url} ",
            subtype=MessageType.html,
        )
        fast_mail = FastMail(mail_config)

        asyncio.run(fast_mail.send_message(message))

        # Delete the temporary CSV file after sending the email
        os.remove(filename)
        print("Done")
        return 'ok done'

    def config_mail(smtp_username: str,
                    smtp_password: str,
                    smtp_sender: str,
                    smtp_port: int,
                    smtp_server: str,
                    org_name: Optional[str] = "",
                    tls: Optional[bool] = True,
                    ssl: Optional[bool] = False,
                    use_credentials: Optional[bool] = True,
                    validate_certs: Optional[bool] = True):
        return ConnectionConfig(
            MAIL_USERNAME=smtp_username,
            MAIL_PASSWORD=smtp_password,
            MAIL_FROM=smtp_sender,
            MAIL_PORT=smtp_port,
            MAIL_SERVER=smtp_server,
            MAIL_FROM_NAME=org_name,
            MAIL_STARTTLS=tls,
            MAIL_SSL_TLS=ssl,
            USE_CREDENTIALS=use_credentials,
            VALIDATE_CERTS=validate_certs,
        )

    loop = asyncio.get_event_loop()
    result = await asyncio.wait_for(
        loop.run_in_executor(thread_pool_executor, get_simple_form_responses, form, responses), timeout=30)
    return result

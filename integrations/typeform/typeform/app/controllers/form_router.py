from fastapi import Depends, APIRouter

from common.models.user import User, Credential
from typeform.app.services import form_service
from typeform.app.services.user_service import get_user_credential

router = APIRouter(prefix="/typeform")


# TODO : Migrate to dependency injection instead of Depends

@router.get("/forms")
async def _import_forms(credential: Credential = Depends(get_user_credential)):
    return await form_service.import_forms(credential)


@router.get("/forms/{form_id}")
async def _import_single_form(form_id: str,
                              credential: Credential = Depends(get_user_credential)):
    return await form_service.import_single_form(form_id, credential)

import abc
from typing import List, TypeVar

from common.models.standard_form import StandardForm

FormDocumentType = TypeVar("FormDocumentType")
FormResponseDocumentType = TypeVar("FormResponseDocumentType")


class FormTransformerService(metaclass=abc.ABCMeta):
    """
    Abstract base class for form and form responses transformer for Google, Typeform
    """

    @abc.abstractmethod
    def transform_form(self, form: FormDocumentType) -> StandardForm:
        """
        Transforms single form into more usable format
        """
        raise NotImplementedError

    @abc.abstractmethod
    def transform_form_responses(self, responses: List[FormResponseDocumentType]):
        """
        Transforms all the imported form responses into more usable format
        """
        raise NotImplementedError

    @abc.abstractmethod
    def transform_single_form_response(self, response: FormResponseDocumentType):
        """
        Transforms single form response into more usable format
        """
        raise NotImplementedError

# flake8: noqa
from abc import abstractmethod, ABCMeta
from typing import Any, List, TypeVar

from common.enums.form_provider import FormProvider

T = TypeVar("T")
U = TypeVar("U")


class BaseRepository(metaclass=ABCMeta):
    """
    BaseRepository is an abstract class that provides a base implementation
    for CRUD operations on a repository.

    Attributes:
    None

    Methods:
        list(self) -> List[T]: Returns a list of items in the repository.
        get(self, item_id: str, provider: FormProvider) -> T: Returns the
            item with the specified item_id and provider.
        add(self, item: U | T) -> T: Adds the given item to the repository
            and returns it.
        update(self, item_id: str, item: U | T) -> T: Updates the item
            with the specified item_id and returns it.
        delete(self, item_id: str, provider: FormProvider): Deletes the item
            with the specified item_id and provider from the repository.
    """

    @abstractmethod
    async def list(self, **kwargs) -> List[T]:
        """
        Returns a list of items stored in the repository.

        Returns:
            A list of items of type T.
        """
        raise NotImplementedError

    @abstractmethod
    async def get(self, item_id: str, provider: FormProvider) -> T:
        """
        Retrieve an item from the repository.

        Parameters:
            item_id (str): The id of the item to retrieve.
            provider (FormProvider): The provider of the item.

        Returns:
            T: The item retrieved from the repository.
        """
        raise NotImplementedError

    @abstractmethod
    async def add(self, item: U | T) -> T:
        """
        Abstract method to create a new item in the repository.

        Args:
            item (U | T): Item to be added to the repository.

        Returns:
            T: The added item, with any changes made by the repository.
        """
        raise NotImplementedError

    @abstractmethod
    async def update(self, item_id: str, item: U | T) -> T:
        """
        Abstract method to update an item in the repository.

        Args:
            item_id (str): The id of the item to update.
            item (U | T): The updated item to save in the repository.

        Returns:
            T: The updated item, with any changes made by the repository.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, item_id: str, provider: FormProvider):
        """
        Abstract method to delete an item in the repository.

        Args:
            item_id (str): The id of the item to delete.
            provider (FormProvider): The provider of the item.

        Returns:
            Implement it as you need.
        """
        raise NotImplementedError


class AbstractOauthRepository(metaclass=ABCMeta):
    """
    AbstractOauthRepository is an abstract class that provides a
    base implementation for get and update operations on a repository.

    Attributes:
    None

    Methods:
        get(self, email: str, provider: FormProvider) -> T: Returns the
            item with the specified email and provider.
        update(self, item_id: str, item: U | T) -> T: Updates the item
            with the specified item_id and returns it.
    """

    @abstractmethod
    async def get(self, email: str, provider: FormProvider) -> T:
        """
        Retrieve an item from the repository.

        Parameters:
            email (str): The id of the item to retrieve.
            provider (FormProvider): The provider of the item.

        Returns:
            T: The item retrieved from the repository.
        """
        raise NotImplementedError

    @abstractmethod
    async def add(self, item_id: str, credentials: Any, item: U | T) -> T:
        """
        Abstract method to add an item in the repository.

        Args:
            item_id (str): The id of the item to update.
            credentials (Any): Credential object return from OAuth authorization.
            item (U | T): The updated item to save in the repository.

        Returns:
            T: The updated item, with any changes made by the repository.
        """
        raise NotImplementedError

    @abstractmethod
    async def update(self, item_id: str, item: U | T) -> T:
        """
        Abstract method to update an item in the repository.

        Args:
            item_id (str): The id of the item to update.
            item (U | T): The updated item to save in the repository.

        Returns:
            T: The updated item, with any changes made by the repository.
        """
        raise NotImplementedError

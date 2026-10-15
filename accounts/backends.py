from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    """Lets people sign in with either their e-mail address or their username.

    Both are stored lowercased, so the lookup lowercases the input too. The two
    can never be confused: usernames cannot contain "@" and e-mail addresses always do.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        identifier = username.strip().lower()
        user = UserModel._default_manager.filter(Q(email=identifier) | Q(username=identifier)).first()
        if user is None:
            # Run the hasher anyway so response time does not reveal whether the account exists.
            UserModel().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

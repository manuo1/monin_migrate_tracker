import factory
from django.contrib.auth import get_user_model

from tracker.choices import FeedbackType
from tracker.models import Feedback, VendorTicket


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    username = factory.Sequence(lambda n: f"user{n}")
    is_staff = False


class StaffFactory(UserFactory):
    is_staff = True


class FeedbackFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Feedback

    type = FeedbackType.BUG
    page = "Articles"
    description = "Something is wrong"
    author = factory.SubFactory(UserFactory)


class VendorTicketFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VendorTicket

    ref = factory.Sequence(lambda n: f"TEST-{n}")
    title = "A vendor ticket"

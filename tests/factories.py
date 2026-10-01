import factory

from simcc_admin.models import (
    Institution,
    Researcher,
    ResearcherInstitution,
    User,
    UserRole,
)


class UserFactory(factory.Factory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"test{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@test.com")
    password = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    role = UserRole.DEFAULT


class InstitutionFactory(factory.Factory):
    class Meta:
        model = Institution

    name = factory.Sequence(lambda n: f"Universidade Federal {n}")
    acronym = factory.Sequence(lambda n: f"UF{n}")


class ResearcherFactory(factory.Factory):
    class Meta:
        model = Researcher

    name = factory.Sequence(lambda n: f"Pesquisador {n}")
    lattes_id = factory.Sequence(lambda n: f"{n:016d}")


class ResearcherInstitutionFactory(factory.Factory):
    class Meta:
        model = ResearcherInstitution

    researcher_id = None
    institution_id = None

import factory

from simcc_admin.models import (
    Collection,
    Institution,
    Researcher,
    ResearcherCollection,
    ResearcherInstitution,
)


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


class CollectionFactory(factory.Factory):
    class Meta:
        model = Collection

    slug = factory.Sequence(lambda n: f"collection-{n}")
    name = factory.Sequence(lambda n: f"Coleção {n}")
    description = factory.Sequence(lambda n: f"Descrição da coleção {n}")
    refresh_interval_days = 1
    is_default = False


class ResearcherCollectionFactory(factory.Factory):
    class Meta:
        model = ResearcherCollection

    researcher_id = None
    collection_id = None
    attributes = factory.LazyFunction(dict)
